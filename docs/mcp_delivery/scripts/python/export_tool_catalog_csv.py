#!/usr/bin/env python3
"""Export the catalog subgraph to explicit, lossless CSV tables (read-only source)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence

from neo4j import GraphDatabase, READ_ACCESS


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from copy_tool_catalog import CATALOG_LABEL_KEYS, load_catalog  # noqa: E402


NODE_FIELDS = {
    "tool_id": [
        "identity", "labels", "catalog_id", "catalog_source", "description",
        "input_format", "omics", "output_format", "tool_id", "tool_kind", "tool_name",
    ],
    "io_slot": [
        "identity", "labels", "catalog_source", "description", "direction",
        "one_of_group", "required", "slot_id", "slot_name", "tool_id",
    ],
    "artifact_type": [
        "identity", "labels", "artifact_type", "description", "is_generic",
    ],
    "function": ["identity", "labels", "function", "description"],
    "format": ["identity", "labels", "format", "description"],
}


def _encode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _write(path: Path, fields: Sequence[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _encode(row.get(field)) for field in fields})


def export(args: argparse.Namespace) -> Dict[str, Any]:
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {args.password_env}")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, password))
    try:
        with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
            info = dict(session.run("CALL db.info() YIELD id,name RETURN id,name").single())
            if str(info["id"]) != args.expected_database_id:
                raise RuntimeError(
                    f"database id mismatch: expected {args.expected_database_id}, got {info['id']}"
                )
            catalog = load_catalog(session)
    finally:
        driver.close()

    output = Path(args.output_dir).resolve()
    counts: Dict[str, int] = {}
    for label, fields in NODE_FIELDS.items():
        rows = []
        for node in catalog["nodes"]:
            if not node["identity"].startswith(label + ":"):
                continue
            rows.append({
                "identity": node["identity"],
                "labels": "|".join(node["labels"]),
                **node["properties"],
            })
        _write(output / f"{label}.csv", fields, rows)
        counts[label] = len(rows)
    relationship_rows = [
        {
            "type": item["type"],
            "start": item["start"],
            "end": item["end"],
            "properties_json": json.dumps(
                item["properties"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ),
        }
        for item in catalog["relationships"]
        if item["type"] != "NEXT"
    ]
    _write(
        output / "relationships.csv",
        ["type", "start", "end", "properties_json"],
        relationship_rows,
    )
    return {
        "source": {"id": str(info["id"]), "name": str(info["name"])},
        "output_dir": str(output),
        "node_counts": counts,
        "relationship_count_excluding_next": len(relationship_rows),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--expected-database-id", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    result = export(parse_args(argv if argv is not None else sys.argv[1:]))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
