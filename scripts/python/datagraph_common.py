#!/usr/bin/env python3
"""Shared deterministic data model for data-graph import and verification."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = "datagraph/v1"
IMPORTER_VERSION = "1.0.0"

DATAGRAPH_LABEL_KEYS: Dict[str, str] = {
    "project": "project_accession",
    "study": "study_accession",
    "individual": "individual_accession",
    "sample": "sample_accession",
    "run": "run_accession",
    "t1": "files",
    "t2": "t2_id",
    "data_format": "format",
    "data_format_row": "format_row_id",
    "data_level": "level",
    "cohort": "status",
    "data_modal": "modal",
}

TOOL_LABELS = {
    "Tool",
    "tool_id",
    "IOSlot",
    "io_slot",
    "ArtifactType",
    "artifact_type",
    "Function",
    "function",
    "Format",
    "format",
}

T1_COLUMN_MAP = {
    "studyAccession": "study_accession",
    "individualAccession": "individual_accession",
    "individualName": "individual_name",
    "sampleAccession": "sample_accession",
    "sampleDescription": "sample_description",
    "sampleName": "sample_name",
    "gender": "gender",
    "runAccession": "run_accession",
    "dataName": "files",
    "experimentAccession": "experiment_accession",
    "platform": "platform",
    "strategy": "strategy",
}

DATA_RELATION_FILES = {
    "relations/T1_in_format.csv",
    "relations/T1_in_level.csv",
    "relations/T1_in_run.csv",
    "relations/T1_in_study.csv",
    "relations/T2_in_format.csv",
    "relations/T2_in_level.csv",
    "relations/T2_in_study.csv",
    "relations/individual_in_study.csv",
    "relations/run_in_sample.csv",
    "relations/sample_in_individual.csv",
    "relations/study_in_project.csv",
}

IMPORTED_ENTITY_FILES = {
    "entities/T1.csv",
    "entities/T2.csv",
    "entities/individual.csv",
    "entities/project.csv",
    "entities/sample.csv",
    "entities/study.csv",
}

IMPORTED_REFERENCE_FILES = {
    "reference/cohort_subclass.csv",
    "reference/cohorts.csv",
    "reference/data_level.csv",
    "reference/formats.csv",
    "reference/multimodal.csv",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def clean_t1_name(value: str) -> str:
    return re.sub(r"\s*\(\d+\s+bytes\)\s*$", "", value or "")


def infer_physical_format(name: str) -> str:
    lowered = (name or "").lower()
    for suffix in ("fastq.gz", "fq.gz", "xlsx", "xls", "tsv", "csv", "maf", "vcf", "bam", "h5"):
        if lowered.endswith(suffix):
            return suffix
    return ""


def infer_read_pair(name: str) -> str:
    lowered = (name or "").lower()
    if re.search(r"(_r?1|_f1|read1)", lowered):
        return "R1"
    if re.search(r"(_r?2|_f2|read2)", lowered):
        return "R2"
    return ""


def read_csv_table(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [{key: (value if value is not None else "") for key, value in row.items()} for row in reader]
    return headers, rows


def source_row_json(headers: Sequence[str], row: Mapping[str, str]) -> str:
    return json.dumps({header: row.get(header, "") for header in headers}, ensure_ascii=False, separators=(",", ":"))


def source_role(relative_path: str) -> str:
    if relative_path in IMPORTED_ENTITY_FILES or relative_path in IMPORTED_REFERENCE_FILES or relative_path in DATA_RELATION_FILES:
        return "imported"
    if relative_path == "T11.csv":
        return "enrichment_and_scope_source"
    if relative_path in {"project.csv", "sample.csv", "study.csv"}:
        return "excluded_duplicate"
    if relative_path == "T2.1csv":
        return "excluded_legacy"
    if relative_path.startswith("entities/tool") or relative_path.startswith("relations/tool_"):
        return "excluded_tool_catalog"
    if relative_path in {"reference/function.csv", "reference/tool_types.csv"}:
        return "excluded_tool_catalog"
    return "excluded_not_datagraph"


def inventory_sources(csv_dir: Path) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for path in sorted(item for item in csv_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(csv_dir).as_posix()
        headers, rows = read_csv_table(path)
        output.append(
            {
                "path": relative,
                "sha256": sha256_bytes(path.read_bytes()),
                "row_count": len(rows),
                "columns": headers,
                "role": source_role(relative),
            }
        )
    return output


@dataclass
class GraphSpec:
    snapshot_id: str
    scope: str
    source_inventory: List[Dict[str, Any]]
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    dangling_fk: List[Dict[str, Any]] = field(default_factory=list)
    roundtrip_expected: Dict[str, List[str]] = field(default_factory=dict)
    excluded_scope_rows: Dict[str, int] = field(default_factory=dict)

    def node_id(self, label: str, key_value: str) -> str:
        return f"{label}:{key_value}"

    def add_expected_row(self, table: str, row_json: str) -> None:
        self.roundtrip_expected.setdefault(table, []).append(row_json)

    def add_node(
        self,
        label: str,
        key_value: str,
        properties: Mapping[str, Any],
    ) -> str:
        key_name = DATAGRAPH_LABEL_KEYS[label]
        if not str(key_value):
            raise ValueError(f"empty primary key for label {label}")
        node_id = self.node_id(label, str(key_value))
        if node_id in self.nodes:
            raise ValueError(f"duplicate node identity: {node_id}")
        props = dict(properties)
        props[key_name] = str(key_value)
        props["datagraph_managed"] = True
        props["snapshot_id"] = self.snapshot_id
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "key_name": key_name,
            "key_value": str(key_value),
            "properties": props,
        }
        return node_id

    def add_relation(
        self,
        rel_type: str,
        start_label: str,
        start_key: str,
        end_label: str,
        end_key: str,
        source_table: str,
        source_headers: Sequence[str],
        source_row: Mapping[str, str],
        source_row_number: int,
        derived: bool = False,
    ) -> None:
        row_json = source_row_json(source_headers, source_row)
        if not derived:
            self.add_expected_row(source_table, row_json)
        start_id = self.node_id(start_label, str(start_key))
        end_id = self.node_id(end_label, str(end_key))
        missing: List[str] = []
        if start_id not in self.nodes:
            missing.append("start")
        if end_id not in self.nodes:
            missing.append("end")
        if missing:
            self.dangling_fk.append(
                {
                    "source_table": source_table,
                    "source_row_number": source_row_number,
                    "relationship_type": rel_type,
                    "start": {"label": start_label, "key": str(start_key)},
                    "end": {"label": end_label, "key": str(end_key)},
                    "missing": missing,
                    "source_row_json": row_json,
                }
            )
            return
        rel_id = f"{rel_type}|{start_id}|{end_id}"
        if rel_id in self.relationships:
            raise ValueError(f"duplicate relationship identity: {rel_id}")
        props: Dict[str, Any] = {
            "datagraph_managed": True,
            "snapshot_id": self.snapshot_id,
            "source_table": source_table,
            "source_row_number": source_row_number,
            "source_row_hash": sha256_text(row_json),
            "source_row_json": row_json,
            "derived": bool(derived),
        }
        self.relationships[rel_id] = {
            "id": rel_id,
            "type": rel_type,
            "start_id": start_id,
            "start_label": start_label,
            "start_key_name": DATAGRAPH_LABEL_KEYS[start_label],
            "start_key_value": str(start_key),
            "end_id": end_id,
            "end_label": end_label,
            "end_key_name": DATAGRAPH_LABEL_KEYS[end_label],
            "end_key_value": str(end_key),
            "properties": props,
        }

    def stable_payload(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "scope": self.scope,
            "snapshot_id": self.snapshot_id,
            "sources": self.source_inventory,
            "nodes": [self.nodes[key] for key in sorted(self.nodes)],
            "relationships": [self.relationships[key] for key in sorted(self.relationships)],
            "dangling_fk": sorted(
                self.dangling_fk,
                key=lambda row: (row["source_table"], row["source_row_number"], row["relationship_type"]),
            ),
            "excluded_scope_rows": dict(sorted(self.excluded_scope_rows.items())),
        }

    def graph_fingerprint(self) -> str:
        graph_only = {
            "nodes": [self.nodes[key] for key in sorted(self.nodes)],
            "relationships": [self.relationships[key] for key in sorted(self.relationships)],
        }
        return sha256_text(canonical_json(graph_only))

    def counts(self) -> Dict[str, Dict[str, int]]:
        labels: Dict[str, int] = {}
        rels: Dict[str, int] = {}
        for node in self.nodes.values():
            labels[node["label"]] = labels.get(node["label"], 0) + 1
        for rel in self.relationships.values():
            rels[rel["type"]] = rels.get(rel["type"], 0) + 1
        return {"labels": dict(sorted(labels.items())), "relationships": dict(sorted(rels.items()))}


def _snapshot_id(inventory: Sequence[Mapping[str, Any]], scope: str, custom_keys: Sequence[str]) -> str:
    relevant = [
        {"path": row["path"], "sha256": row["sha256"], "role": row["role"]}
        for row in inventory
        if row["role"] in {"imported", "enrichment_and_scope_source"}
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "scope": scope,
        "custom_keys": sorted(custom_keys),
        "sources": relevant,
    }
    return "dg-" + sha256_text(canonical_json(payload))[:24]


def _row_hash(headers: Sequence[str], row: Mapping[str, str]) -> str:
    return sha256_text(source_row_json(headers, row))


def _load_custom_keys(path: Optional[Path]) -> List[str]:
    if path is None:
        return []
    headers, rows = read_csv_table(path)
    key = "files" if "files" in headers else "dataName" if "dataName" in headers else ""
    if not key:
        raise ValueError("custom scope file must contain a 'files' or 'dataName' column")
    keys = sorted({clean_t1_name(row.get(key, "")) for row in rows if row.get(key, "")})
    if not keys:
        raise ValueError("custom scope file selected no T1 records")
    return keys


def build_graph_spec(csv_dir: Path, scope: str = "t1", custom_t1_file: Optional[Path] = None) -> GraphSpec:
    if scope not in {"t1", "t1_plus_t11", "custom"}:
        raise ValueError(f"unsupported scope: {scope}")
    if scope == "custom" and custom_t1_file is None:
        raise ValueError("--custom-t1-file is required with --scope custom")
    if scope != "custom" and custom_t1_file is not None:
        raise ValueError("--custom-t1-file is only valid with --scope custom")

    inventory = inventory_sources(csv_dir)
    custom_keys = _load_custom_keys(custom_t1_file)
    snapshot_id = _snapshot_id(inventory, scope, custom_keys)
    spec = GraphSpec(snapshot_id=snapshot_id, scope=scope, source_inventory=inventory)

    tables: Dict[str, Tuple[List[str], List[Dict[str, str]]]] = {}
    for item in inventory:
        if item["role"] in {"imported", "enrichment_and_scope_source"}:
            tables[item["path"]] = read_csv_table(csv_dir / item["path"])

    def add_source_node(label: str, table: str, row_number: int, row: Mapping[str, str], key: str) -> None:
        headers, _ = tables[table]
        row_json = source_row_json(headers, row)
        props: Dict[str, Any] = dict(row)
        props.update(
            {
                "source_table": table,
                "source_row_number": row_number,
                "source_row_hash": sha256_text(row_json),
                "source_row_json": row_json,
            }
        )
        spec.add_node(label, row[key], props)
        spec.add_expected_row(table, row_json)

    for label, table, key in [
        ("project", "entities/project.csv", "project_accession"),
        ("study", "entities/study.csv", "study_accession"),
        ("individual", "entities/individual.csv", "individual_accession"),
        ("sample", "entities/sample.csv", "sample_accession"),
        ("t2", "entities/T2.csv", "t2_id"),
    ]:
        _, rows = tables[table]
        for row_number, row in enumerate(rows, start=2):
            add_source_node(label, table, row_number, row, key)

    # Reference rows and concepts are separated so duplicate semantic formats remain lossless.
    fmt_headers, fmt_rows = tables["reference/formats.csv"]
    format_names = sorted({row["语义格式"] for row in fmt_rows})
    for format_name in format_names:
        descriptions = [row["description"] for row in fmt_rows if row["语义格式"] == format_name]
        spec.add_node(
            "data_format",
            format_name,
            {
                "descriptions": descriptions,
                "source_table": "reference/formats.csv",
                "source_row_hash": sha256_text(canonical_json(descriptions)),
            },
        )
    for index, row in enumerate(fmt_rows, start=1):
        row_number = index + 1
        row_id = f"format-row-{index:04d}"
        row_json = source_row_json(fmt_headers, row)
        spec.add_node(
            "data_format_row",
            row_id,
            {
                "format": row["语义格式"],
                "description": row["description"],
                "source_table": "reference/formats.csv",
                "source_row_number": row_number,
                "source_row_hash": sha256_text(row_json),
                "source_row_json": row_json,
            },
        )
        spec.add_expected_row("reference/formats.csv", row_json)
        spec.add_relation(
            "DESCRIBES_FORMAT",
            "data_format_row",
            row_id,
            "data_format",
            row["语义格式"],
            "reference/formats.csv#derived",
            fmt_headers,
            row,
            row_number,
            derived=True,
        )

    for label, table, key in [
        ("data_level", "reference/data_level.csv", "level"),
        ("cohort", "reference/cohorts.csv", "status"),
        ("data_modal", "reference/multimodal.csv", "modal"),
    ]:
        _, rows = tables[table]
        for row_number, row in enumerate(rows, start=2):
            add_source_node(label, table, row_number, row, key)

    sample_headers, sample_rows = tables["entities/sample.csv"]
    samples_by_id = {row["sample_accession"]: row for row in sample_rows}
    t1_headers, t1_rows = tables["entities/T1.csv"]
    t11_headers, t11_rows = tables["T11.csv"]
    normalized_by_name = {clean_t1_name(row["dataName"]): row for row in t1_rows}
    legacy_by_name = {clean_t1_name(row["files"]): row for row in t11_rows}
    all_keys = set(normalized_by_name) | set(legacy_by_name)
    if scope == "t1":
        selected_keys = set(normalized_by_name)
    elif scope == "t1_plus_t11":
        selected_keys = all_keys
    else:
        missing_custom = sorted(set(custom_keys) - all_keys)
        if missing_custom:
            raise ValueError(f"custom scope references unknown T1 files: {missing_custom[:10]}")
        selected_keys = set(custom_keys)
    spec.excluded_scope_rows["T11.csv"] = len(set(legacy_by_name) - selected_keys)
    spec.excluded_scope_rows["entities/T1.csv"] = len(set(normalized_by_name) - selected_keys)

    format_rel_headers, format_rel_rows = tables["relations/T1_in_format.csv"]
    level_rel_headers, level_rel_rows = tables["relations/T1_in_level.csv"]
    semantic_format_by_name = {clean_t1_name(row["files"]): row["format"] for row in format_rel_rows}
    level_by_name = {clean_t1_name(row["files"]): row["data_level"] for row in level_rel_rows}

    for name in sorted(selected_keys):
        normalized = normalized_by_name.get(name, {})
        legacy = legacy_by_name.get(name, {})
        sample_accession = normalized.get("sampleAccession") or legacy.get("sample_accession") or ""
        sample = samples_by_id.get(sample_accession, {})
        props: Dict[str, Any] = {}
        for source_column, target_property in T1_COLUMN_MAP.items():
            props[target_property] = normalized.get(source_column, "")
        props["study_accession"] = props.get("study_accession") or legacy.get("study_accession", "")
        props["sample_accession"] = sample_accession
        props["run_accession"] = props.get("run_accession") or legacy.get("run_accession", "")
        props["individual_accession"] = props.get("individual_accession") or sample.get("individual_accession", "")
        props["individual_name"] = props.get("individual_name") or sample.get("individual_name", "")
        props["sample_name"] = props.get("sample_name") or sample.get("sample_name", "")
        props["sample_description"] = props.get("sample_description") or sample.get("sample_description", "")
        props["files"] = name
        props["file_name"] = legacy.get("file_name", "") or legacy.get("files", "") or name
        props["strategy"] = props.get("strategy") or legacy.get("data_type", "")
        props["data_type"] = legacy.get("data_type", "")
        props["read_pair"] = legacy.get("Read Pair", "") or infer_read_pair(name)
        props["physical_format"] = legacy.get("format", "") or infer_physical_format(name)
        props["semantic_format"] = semantic_format_by_name.get(name, "")
        props["file_path"] = legacy.get("file_path", "") or props["file_name"]
        props["file_description"] = legacy.get("file_description", "")
        props["experiment_accession"] = props.get("experiment_accession") or legacy.get("Experiment", "")
        props["platform"] = props.get("platform") or legacy.get("Platform", "")
        props["data_level"] = level_by_name.get(name) or legacy.get("data_level", "")
        props["pipeline_id"] = legacy.get("pipeline-id", "")
        props["parameter"] = legacy.get("parameter", "")
        props["normalized_source_present"] = bool(normalized)
        props["legacy_source_present"] = bool(legacy)
        props["source_tables"] = sorted(
            table for table, present in (("T11.csv", bool(legacy)), ("entities/T1.csv", bool(normalized))) if present
        )
        if normalized:
            normalized_json = source_row_json(t1_headers, normalized)
            props["normalized_source_row_json"] = normalized_json
            props["normalized_source_row_hash"] = sha256_text(normalized_json)
            spec.add_expected_row("entities/T1.csv", normalized_json)
        else:
            props["normalized_source_row_json"] = ""
            props["normalized_source_row_hash"] = ""
        if legacy:
            legacy_json = source_row_json(t11_headers, legacy)
            props["legacy_source_row_json"] = legacy_json
            props["legacy_source_row_hash"] = sha256_text(legacy_json)
            spec.add_expected_row("T11.csv", legacy_json)
        else:
            props["legacy_source_row_json"] = ""
            props["legacy_source_row_hash"] = ""
        props["source_row_hash"] = sha256_text(
            props["normalized_source_row_hash"] + ":" + props["legacy_source_row_hash"]
        )
        spec.add_node("t1", name, props)

    # Runs are first-class identities derived from the relation table and selected T1 scope.
    run_headers, run_rows = tables["relations/run_in_sample.csv"]
    run_ids = {row["run_accession"] for row in run_rows}
    run_ids.update(
        str(spec.nodes[spec.node_id("t1", name)]["properties"].get("run_accession", ""))
        for name in selected_keys
    )
    for run_id in sorted(run_id for run_id in run_ids if run_id):
        spec.add_node("run", run_id, {"source_table": "relations/run_in_sample.csv", "source_row_hash": ""})

    def add_relation_table(
        table: str,
        rel_type: str,
        start_label: str,
        start_column: str,
        end_label: str,
        end_column: str,
        selected_start_keys: Optional[set[str]] = None,
    ) -> None:
        headers, rows = tables[table]
        for row_number, row in enumerate(rows, start=2):
            start_key = clean_t1_name(row[start_column]) if start_label == "t1" else row[start_column]
            if selected_start_keys is not None and start_key not in selected_start_keys:
                continue
            spec.add_relation(
                rel_type,
                start_label,
                start_key,
                end_label,
                row[end_column],
                table,
                headers,
                row,
                row_number,
            )

    add_relation_table("relations/study_in_project.csv", "IN_PROJECT", "study", "study_accession", "project", "project_accession")
    add_relation_table("relations/individual_in_study.csv", "IN_STUDY", "individual", "individual_accession", "study", "study_accession")
    add_relation_table("relations/sample_in_individual.csv", "IN_INDIVIDUAL", "sample", "sample_accession", "individual", "individual_accession")
    add_relation_table("relations/run_in_sample.csv", "IN_SAMPLE", "run", "run_accession", "sample", "sample_accession")
    add_relation_table("relations/T1_in_run.csv", "IN_RUN", "t1", "files", "run", "run_accession", selected_keys)
    add_relation_table("relations/T1_in_study.csv", "IN_STUDY", "t1", "files", "study", "study_accession", selected_keys)
    add_relation_table("relations/T1_in_format.csv", "IN_FORMAT", "t1", "files", "data_format", "format", selected_keys)
    add_relation_table("relations/T1_in_level.csv", "IN_LEVEL", "t1", "files", "data_level", "data_level", selected_keys)
    add_relation_table("relations/T2_in_study.csv", "IN_STUDY", "t2", "t2_id", "study", "study_accession")
    add_relation_table("relations/T2_in_format.csv", "IN_FORMAT", "t2", "t2_id", "data_format", "format")
    add_relation_table("relations/T2_in_level.csv", "IN_LEVEL", "t2", "t2_id", "data_level", "level")
    add_relation_table("reference/cohort_subclass.csv", "SUBCLASS_OF", "cohort", "child", "cohort", "parent")

    # T11-only scope records have explicit study/run/level metadata but no semantic-format relation CSV.
    if scope in {"t1_plus_t11", "custom"}:
        for name in sorted(selected_keys - set(normalized_by_name)):
            legacy = legacy_by_name[name]
            row_number = t11_rows.index(legacy) + 2
            for rel_type, end_label, source_column in [
                ("IN_RUN", "run", "run_accession"),
                ("IN_STUDY", "study", "study_accession"),
                ("IN_LEVEL", "data_level", "data_level"),
            ]:
                spec.add_relation(
                    rel_type,
                    "t1",
                    name,
                    end_label,
                    legacy[source_column],
                    "T11.csv#derived",
                    t11_headers,
                    legacy,
                    row_number,
                    derived=True,
                )

    for table in spec.roundtrip_expected:
        spec.roundtrip_expected[table] = sorted(spec.roundtrip_expected[table])
    spec.dangling_fk.sort(
        key=lambda row: (row["source_table"], row["source_row_number"], row["relationship_type"])
    )
    return spec


def chunked(rows: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def safe_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"unsafe Cypher identifier: {value!r}")
    return value


def assert_target_isolation(
    session: Any,
    expected_database_id: str,
    forbidden_database_ids: Sequence[str],
    require_no_tools: bool = True,
) -> Dict[str, Any]:
    info = session.run("CALL db.info() YIELD id, name, creationDate RETURN id, name, creationDate").single()
    if info is None:
        raise RuntimeError("CALL db.info() returned no row")
    database_id = str(info["id"])
    if database_id != expected_database_id:
        raise RuntimeError(
            f"target database id mismatch: expected {expected_database_id}, connected to {database_id}"
        )
    if database_id in set(forbidden_database_ids):
        raise RuntimeError(f"refusing forbidden/production database id: {database_id}")
    tool_count = session.run(
        "MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) RETURN count(n) AS count",
        labels=sorted(TOOL_LABELS),
    ).single()["count"]
    if require_no_tools and tool_count:
        raise RuntimeError(f"refusing target containing {tool_count} tool-catalog nodes")
    return {
        "database_id": database_id,
        "database_name": str(info["name"]),
        "creation_date": str(info["creationDate"]),
        "tool_catalog_node_count": int(tool_count),
    }


def aggregate_dangling(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[Tuple[str, str, str], int] = {}
    for row in rows:
        key = (row["source_table"], row["relationship_type"], "+".join(row["missing"]))
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "source_table": key[0],
            "relationship_type": key[1],
            "missing": key[2].split("+"),
            "count": count,
        }
        for key, count in sorted(counts.items())
    ]
