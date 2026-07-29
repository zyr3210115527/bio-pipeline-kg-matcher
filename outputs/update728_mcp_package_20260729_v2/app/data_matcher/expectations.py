"""Load the data-graph contract expected by runtime health and Neo4j reads."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPECTATIONS_PATH = REPO_ROOT / "config" / "unified_graph_expectations.json"


def expectations_path(path: Optional[str | Path] = None) -> Path:
    configured = path or os.environ.get("DATAGRAPH_EXPECTATIONS_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_EXPECTATIONS_PATH


def load_expectations(path: Optional[str | Path] = None) -> Dict[str, Any]:
    source = expectations_path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to load data-graph expectations: {source}") from exc
    graph = payload.get("data_graph") or {}
    counts = graph.get("counts") or {}
    legacy = payload.get("legacy_backend") or {}
    return {
        "path": str(source),
        "snapshot_id": str(graph.get("snapshot_id") or ""),
        "node_count": int(counts.get("nodes") or 0),
        "relationship_count": int(counts.get("relationships") or 0),
        "schema_version": str(graph.get("schema_version") or ""),
        "legacy_backend": {
            "schema_version": str(legacy.get("schema_version") or ""),
            "source_sha256": str(legacy.get("source_sha256") or ""),
            "core_node_count": int(legacy.get("core_node_count") or 0),
            "label_counts": {
                str(label): int(count)
                for label, count in (legacy.get("label_counts") or {}).items()
            },
        },
        "tool_count": int((payload.get("tool_catalog") or {}).get("tools") or 0),
        "raw": payload,
    }
