"""Assemble the runtime tool catalog from the 0811 graph plus local execution bindings.

The Neo4j graph is the 0811 delivery verbatim. It owns the facts a knowledge
graph should own: which tools exist (`:tool`), what semantic formats they consume
and produce (`input` / `output`), and how they connect (`next_tool`).

It deliberately does not carry slot names, WDL targets, builder params, input
variants or the tumor/normal role split. Those are execution-side contracts, not
knowledge-graph facts, and the data provider never modelled them. They live in
`data/csv/catalog/` and are merged in here, which is what keeps the graph
byte-identical to what she shipped.

Anything the two sides disagree about is reported in `divergence` rather than
silently resolved, so `health_check` can surface it.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parent
CATALOG_DIR = ROOT / "data" / "csv" / "catalog"
NEXT_CSV = ROOT / "data" / "csv" / "relations" / "tool_relationship.csv"

# multiqc is kept out of the atomic layer on purpose: it is a terminal QC
# aggregator that no analytic step consumes, and advertising it only produced
# fan-in chains that failed closed-set validation. Her graph does carry 12
# order edges into it; they are dropped here, which is a deliberate deviation.
EXCLUDED_TOOL_IDS = {"multiqc"}

_BOOL_COLUMNS = {"required", "is_generic", "exactly_one_variant"}


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _decode(key: str, value: str) -> Any:
    if key in _BOOL_COLUMNS:
        return str(value).strip().lower() == "true"
    return value


def _identity_value(identity: str) -> str:
    return identity.split(":", 1)[1] if ":" in identity else identity


def load_local_catalog(catalog_dir: Path = CATALOG_DIR, next_csv: Path = NEXT_CSV) -> Dict[str, Any]:
    """Load the execution-side catalog model that the graph cannot express."""
    tool_rows = _read_csv(catalog_dir / "tool_id.csv")
    slot_rows = _read_csv(catalog_dir / "io_slot.csv")
    relationship_rows = _read_csv(catalog_dir / "relationships.csv")

    artifacts_by_slot: Dict[str, List[str]] = defaultdict(list)
    formats_by_slot: Dict[str, List[str]] = defaultdict(list)
    pipeline_steps: List[Dict[str, Any]] = []
    for row in relationship_rows:
        rel_type = row.get("type") or ""
        start, end = row.get("start") or "", row.get("end") or ""
        if rel_type in {"REQUIRES", "PRODUCES"}:
            artifacts_by_slot[start].append(_identity_value(end))
        elif rel_type == "ALLOW_FORMAT":
            formats_by_slot[start].append(_identity_value(end))
        elif rel_type == "HAS_STEP":
            properties = json.loads(row.get("properties_json") or "{}")
            pipeline_steps.append({
                "pipeline_id": _identity_value(start),
                "tool_id": _identity_value(end),
                "step_id": properties.get("step_id"),
                "step_order": properties.get("order"),
                "depends_on": properties.get("depends_on") or [],
                "locked": properties.get("locked"),
                "source": properties.get("source"),
            })
    pipeline_steps.sort(key=lambda item: (item["pipeline_id"], item["step_order"] or 0))

    slots_by_tool: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
        lambda: {"inputs": [], "outputs": []}
    )
    for row in slot_rows:
        identity = row.get("identity") or ""
        slot = {
            key: _decode(key, value)
            for key, value in row.items()
            if key not in {"identity", "labels"}
        }
        slot["artifacts"] = sorted(set(artifacts_by_slot.get(identity, [])))
        slot["formats"] = sorted(set(formats_by_slot.get(identity, [])))
        bucket = "inputs" if slot.get("direction") == "input" else "outputs"
        slots_by_tool[str(slot.get("tool_id") or "")][bucket].append(slot)
    for buckets in slots_by_tool.values():
        for bucket in buckets.values():
            bucket.sort(key=lambda item: str(item.get("slot_id") or ""))

    tools_by_catalog_id: Dict[str, Dict[str, Any]] = {}
    for row in tool_rows:
        catalog_id = str(row.get("catalog_id") or "")
        tool_id = str(row.get("tool_id") or "")
        if not catalog_id or not tool_id:
            continue
        properties = {
            key: _decode(key, value)
            for key, value in row.items()
            if key not in {"identity", "labels"} and value != ""
        }
        buckets = slots_by_tool.get(tool_id, {"inputs": [], "outputs": []})
        tools_by_catalog_id[catalog_id] = {
            **properties,
            "inputs": list(buckets["inputs"]),
            "outputs": list(buckets["outputs"]),
        }

    next_bindings: Dict[tuple, List[Dict[str, str]]] = defaultdict(list)
    for row in _read_csv(next_csv):
        key = (str(row.get("tool_id") or ""), str(row.get("next_tool_id") or ""))
        next_bindings[key].append({
            "kind": row.get("kind") or "order",
            "output": row.get("output") or "",
            "input": row.get("input") or "",
        })

    return {
        "tools_by_catalog_id": tools_by_catalog_id,
        "next_bindings": next_bindings,
        "pipeline_steps": pipeline_steps,
    }


def merge_with_graph(
    local: Mapping[str, Any],
    graph_tools: Sequence[Mapping[str, Any]],
    graph_next: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Let the graph decide which tools exist and how they connect."""
    tools_by_catalog_id: Dict[str, Dict[str, Any]] = dict(local["tools_by_catalog_id"])
    next_bindings = local["next_bindings"]

    graph_ids = {str(row.get("catalog_id") or "") for row in graph_tools}
    graph_ids.discard("")

    divergence: Dict[str, Any] = {
        "tools_missing_from_graph": sorted(set(tools_by_catalog_id) - graph_ids),
        "tools_missing_local_model": [],
        "next_missing_local_binding": [],
        "next_missing_from_graph": [],
        "excluded_tool_ids": sorted(EXCLUDED_TOOL_IDS),
    }

    tools: List[Dict[str, Any]] = []
    runtime_id_by_catalog_id: Dict[str, str] = {}
    for row in graph_tools:
        catalog_id = str(row.get("catalog_id") or "")
        local_tool = tools_by_catalog_id.get(catalog_id)
        if local_tool is None:
            divergence["tools_missing_local_model"].append(catalog_id)
            continue
        runtime_id = str(local_tool.get("tool_id") or "")
        if runtime_id in EXCLUDED_TOOL_IDS:
            continue
        runtime_id_by_catalog_id[catalog_id] = runtime_id
        tools.append({
            **local_tool,
            "graph_tool_name": row.get("tool_name"),
            "graph_modals": row.get("modals") or [],
            "graph_semantic_inputs": row.get("semantic_inputs") or [],
            "graph_semantic_outputs": row.get("semantic_outputs") or [],
        })

    next_edges: List[Dict[str, Any]] = []
    seen_pairs = set()
    for row in graph_next:
        source_catalog_id = str(row.get("source_catalog_id") or "")
        target_catalog_id = str(row.get("target_catalog_id") or "")
        source = runtime_id_by_catalog_id.get(source_catalog_id)
        target = runtime_id_by_catalog_id.get(target_catalog_id)
        if not source or not target:
            # One end is excluded (multiqc) or unknown; nothing to emit.
            continue
        seen_pairs.add((source_catalog_id, target_catalog_id))
        bindings = next_bindings.get((source_catalog_id, target_catalog_id))
        if not bindings:
            divergence["next_missing_local_binding"].append(
                f"{source}->{target}"
            )
            bindings = [{"kind": row.get("kind") or "order", "output": "", "input": ""}]
        for binding in bindings:
            next_edges.append({
                "source_tool_id": source,
                "target_tool_id": target,
                "source_catalog_id": source_catalog_id,
                "target_catalog_id": target_catalog_id,
                "kind": binding["kind"],
                "output": binding["output"],
                "input": binding["input"],
            })

    for pair in next_bindings:
        if pair in seen_pairs:
            continue
        source = runtime_id_by_catalog_id.get(pair[0], pair[0])
        target = runtime_id_by_catalog_id.get(pair[1], pair[1])
        divergence["next_missing_from_graph"].append(f"{source}->{target}")
    divergence["next_missing_from_graph"].sort()

    known_runtime_ids = {str(tool.get("tool_id") or "") for tool in tools}
    pipeline_steps = [
        step for step in local["pipeline_steps"]
        if step["pipeline_id"] in known_runtime_ids
        and step["tool_id"] not in EXCLUDED_TOOL_IDS
    ]

    return {
        "tools": tools,
        "next_edges": next_edges,
        "pipeline_steps": pipeline_steps,
        "divergence": divergence,
    }


def runtime_to_catalog_id(local: Mapping[str, Any]) -> Dict[str, str]:
    return {
        str(tool.get("tool_id")): catalog_id
        for catalog_id, tool in local["tools_by_catalog_id"].items()
        if tool.get("tool_id")
    }
