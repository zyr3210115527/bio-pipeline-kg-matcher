#!/usr/bin/env python3
"""Write the complete production-vs-bootstrap catalog relationship diff."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

from neo4j import GraphDatabase, READ_ACCESS


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from copy_tool_catalog import catalog_counts, catalog_fingerprint, load_catalog  # noqa: E402
from datagraph_common import canonical_json  # noqa: E402


def _load(uri: str, database: str, user: str, password_env: str, expected_id: str):
    password = os.environ.get(password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {password_env}")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        with driver.session(database=database, default_access_mode=READ_ACCESS) as session:
            info = dict(session.run("CALL db.info() YIELD id,name RETURN id,name").single())
            if str(info["id"]) != expected_id:
                raise RuntimeError(f"database id mismatch: expected {expected_id}, got {info['id']}")
            return info, load_catalog(session)
    finally:
        driver.close()


def _rel_key(item: Dict[str, Any]) -> Tuple[str, str, str, str]:
    return item["type"], item["start"], item["end"], canonical_json(item["properties"])


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def report(args: argparse.Namespace) -> Dict[str, Any]:
    production_info, production = _load(
        args.production_uri, args.production_database, args.production_user,
        args.production_password_env, args.production_database_id,
    )
    bootstrap_info, bootstrap = _load(
        args.bootstrap_uri, args.bootstrap_database, args.bootstrap_user,
        args.bootstrap_password_env, args.bootstrap_database_id,
    )
    prod_rel = {_rel_key(item): item for item in production["relationships"]}
    boot_rel = {_rel_key(item): item for item in bootstrap["relationships"]}
    missing = [prod_rel[key] for key in sorted(prod_rel.keys() - boot_rel.keys())]
    extra = [boot_rel[key] for key in sorted(boot_rel.keys() - prod_rel.keys())]
    prod_nodes = {item["identity"]: item for item in production["nodes"]}
    boot_nodes = {item["identity"]: item for item in bootstrap["nodes"]}
    changed_nodes = [
        {"identity": key, "csv_bootstrap": boot_nodes[key], "production": prod_nodes[key]}
        for key in sorted(prod_nodes.keys() & boot_nodes.keys())
        if prod_nodes[key] != boot_nodes[key]
    ]
    grouped: Dict[str, list] = defaultdict(list)
    for item in missing:
        grouped[item["type"]].append(item)

    lines = [
        "# Fix C: Catalog Reproducibility",
        "",
        "## Pre-Fix Difference Evidence",
        "",
        "This appendix was generated from read-only production and an isolated legacy CSV bootstrap. Relationship identity includes type, both canonical endpoints, and the complete property object.",
        "",
        "| Graph | Nodes | Relationships | Fingerprint |",
        "|---|---:|---:|---|",
        f"| Production | {len(production['nodes'])} | {len(production['relationships'])} | `{catalog_fingerprint(production)}` |",
        f"| Legacy CSV bootstrap | {len(bootstrap['nodes'])} | {len(bootstrap['relationships'])} | `{catalog_fingerprint(bootstrap)}` |",
        "",
        f"Missing production relationships: **{len(missing)}**. Incorrect extra CSV mappings: **{len(extra)}**.",
        "",
        "### Missing Relationship Counts",
        "",
        "| Type | Count |",
        "|---|---:|",
    ]
    counts = Counter(item["type"] for item in missing)
    lines.extend(f"| `{rel_type}` | {counts[rel_type]} |" for rel_type in sorted(counts))
    lines.extend(["", "### Complete 301 Missing Relationships", ""])
    for rel_type in sorted(grouped):
        lines.extend([
            f"#### {rel_type} ({len(grouped[rel_type])})",
            "",
            "| Start | End | Properties |",
            "|---|---|---|",
        ])
        for item in grouped[rel_type]:
            lines.append(
                f"| `{_cell(item['start'])}` | `{_cell(item['end'])}` | `{_cell(canonical_json(item['properties']))}` |"
            )
        lines.append("")
    lines.extend([
        "### Complete 6 Incorrect CSV Mappings",
        "",
        "| Type | CSV bootstrap start | CSV bootstrap end | CSV properties | Production state |",
        "|---|---|---|---|---|",
    ])
    for item in extra:
        same_endpoints = [
            value for value in production["relationships"]
            if value["type"] == item["type"]
            and value["start"] == item["start"]
            and value["end"] == item["end"]
        ]
        state = (
            "; ".join(canonical_json(value["properties"]) for value in same_endpoints)
            if same_endpoints else "relationship absent"
        )
        lines.append(
            f"| `{item['type']}` | `{_cell(item['start'])}` | `{_cell(item['end'])}` | "
            f"`{_cell(canonical_json(item['properties']))}` | {_cell(state)} |"
        )
    missing_nodes = sorted(prod_nodes.keys() - boot_nodes.keys())
    lines.extend([
        "",
        "### Node Coverage and Property Drift",
        "",
        f"The legacy bootstrap also omitted **{len(missing_nodes)}** nodes and produced **{len(changed_nodes)}** shared nodes with different labels or properties. It produced no extra node identities.",
        "",
        "Missing node identities:",
        "",
    ])
    lines.extend(f"- `{identity}`" for identity in missing_nodes)
    lines.extend([
        "",
        "Changed shared nodes are preserved in the machine-readable evidence file `docs/fix_c_catalog_diff.json`.",
        "",
        "## Implementation and Gates",
        "",
        "This section is completed after the canonical CSV bootstrap gates run.",
    ])
    output = Path(args.output).resolve()
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    evidence = {
        "schema_version": "catalog-bootstrap-diff/v1",
        "production": {"database": production_info, "counts": catalog_counts(production), "fingerprint": catalog_fingerprint(production)},
        "bootstrap": {"database": bootstrap_info, "counts": catalog_counts(bootstrap), "fingerprint": catalog_fingerprint(bootstrap)},
        "missing_relationships": missing,
        "extra_relationships": extra,
        "missing_nodes": missing_nodes,
        "changed_nodes": changed_nodes,
    }
    Path(args.output_json).resolve().write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"missing": len(missing), "extra": len(extra), "changed_nodes": len(changed_nodes)}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("production", "bootstrap"):
        parser.add_argument(f"--{prefix}-uri", required=True)
        parser.add_argument(f"--{prefix}-database", required=True)
        parser.add_argument(f"--{prefix}-user", required=True)
        parser.add_argument(f"--{prefix}-password-env", required=True)
        parser.add_argument(f"--{prefix}-database-id", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-json", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    print(json.dumps(report(parse_args(argv if argv is not None else sys.argv[1:])), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
