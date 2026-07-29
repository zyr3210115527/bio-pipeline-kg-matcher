#!/usr/bin/env python3
"""Verify that a database contains the exact approved data graph and tool catalog."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Sequence

from neo4j import GraphDatabase, READ_ACCESS


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from copy_tool_catalog import (  # noqa: E402
    CATALOG_LABEL_KEYS,
    catalog_counts,
    catalog_fingerprint,
    load_catalog,
)
from import_datagraph import actual_graph_fingerprint, current_counts  # noqa: E402


def verify(args: argparse.Namespace) -> Dict[str, Any]:
    expected = json.loads(Path(args.expectations).read_text(encoding="utf-8"))
    if expected.get("schema_version") != "unified-graph-expectations/v1":
        raise RuntimeError(f"unsupported expectations schema: {expected.get('schema_version')}")
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {args.password_env}")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, password))
    try:
        with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
            info_row = session.run(
                "CALL db.info() YIELD id,name,creationDate RETURN id,name,creationDate"
            ).single()
            database_id = str(info_row["id"])
            if database_id != args.expected_database_id:
                raise RuntimeError(
                    f"database id mismatch: expected {args.expected_database_id}, got {database_id}"
                )
            if database_id in set(args.forbid_database_id):
                raise RuntimeError(f"refusing forbidden database id: {database_id}")

            data_counts_by_type = current_counts(session)
            data_counts = {
                "nodes": sum(data_counts_by_type["labels"].values()),
                "relationships": sum(data_counts_by_type["relationships"].values()),
            }
            data_fingerprint = actual_graph_fingerprint(session)
            snapshots = [
                dict(row)
                for row in session.run(
                    "MATCH (n) WHERE n.datagraph_managed = true "
                    "RETURN n.snapshot_id AS snapshot_id, count(n) AS count ORDER BY snapshot_id"
                )
            ]

            catalog = load_catalog(session)
            catalog_summary = catalog_counts(catalog)
            catalog_fp = catalog_fingerprint(catalog)
            tool_kinds = {
                str(row["tool_kind"]): int(row["count"])
                for row in session.run(
                    "MATCH (t:tool_id) RETURN t.tool_kind AS tool_kind,count(t) AS count ORDER BY tool_kind"
                )
            }
            catalog_rel_counts = Counter(
                relationship["type"] for relationship in catalog["relationships"]
            )
            mixed_nodes = int(
                session.run(
                    "MATCH (n) WHERE n.datagraph_managed = true "
                    "AND any(label IN labels(n) WHERE label IN $catalog_labels) "
                    "RETURN count(n) AS count",
                    catalog_labels=sorted(CATALOG_LABEL_KEYS),
                ).single()["count"]
            )
            cross_domain_relationships = int(
                session.run(
                    "MATCH (a)-[r]-(b) "
                    "WHERE any(label IN labels(a) WHERE label IN $catalog_labels) "
                    "AND b.datagraph_managed = true RETURN count(r) AS count",
                    catalog_labels=sorted(CATALOG_LABEL_KEYS),
                ).single()["count"]
            )
            totals = {
                "nodes": int(session.run("MATCH (n) RETURN count(n) AS count").single()["count"]),
                "relationships": int(
                    session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]
                ),
            }
    finally:
        driver.close()

    expected_data = expected["data_graph"]
    expected_catalog = expected["tool_catalog"]
    checks = [
        {"name": "data_counts", "ok": data_counts == expected_data["counts"], "actual": data_counts},
        {
            "name": "data_fingerprint",
            "ok": data_fingerprint == expected_data["graph_fingerprint"],
            "actual": data_fingerprint,
        },
        {
            "name": "snapshot_id",
            "ok": snapshots == [{"snapshot_id": expected_data["snapshot_id"], "count": data_counts["nodes"]}],
            "actual": snapshots,
        },
        {
            "name": "catalog_counts",
            "ok": {
                "nodes": catalog_summary["nodes"],
                "relationships": catalog_summary["relationships"],
            }
            == expected_catalog["counts"],
            "actual": catalog_summary,
        },
        {
            "name": "catalog_fingerprint",
            "ok": catalog_fp == expected_catalog["fingerprint"],
            "actual": catalog_fp,
        },
        {
            "name": "tool_counts",
            "ok": sum(tool_kinds.values()) == expected_catalog["tools"]
            and tool_kinds.get("atomic", 0) == expected_catalog["atomic_tools"]
            and sum(value for key, value in tool_kinds.items() if key != "atomic")
            == expected_catalog["pipeline_tools"],
            "actual": tool_kinds,
        },
        {
            "name": "catalog_contract_counts",
            "ok": catalog_rel_counts["NEXT"] == expected_catalog["next"]
            and catalog_rel_counts["HAS_INPUT_SLOT"] == expected_catalog["input_slots"]
            and catalog_rel_counts["HAS_OUTPUT_SLOT"] == expected_catalog["output_slots"]
            and catalog_rel_counts["HAS_STEP"] == expected_catalog["has_step"],
            "actual": dict(sorted(catalog_rel_counts.items())),
        },
        {
            "name": "domain_isolation",
            "ok": mixed_nodes == 0 and cross_domain_relationships == 0,
            "actual": {
                "mixed_nodes": mixed_nodes,
                "cross_domain_relationships": cross_domain_relationships,
            },
        },
        {
            "name": "total_counts",
            "ok": totals
            == {
                "nodes": expected_data["counts"]["nodes"] + expected_catalog["counts"]["nodes"],
                "relationships": expected_data["counts"]["relationships"]
                + expected_catalog["counts"]["relationships"],
            },
            "actual": totals,
        },
    ]
    report = {
        "schema_version": "unified-graph-verification/v1",
        "database": {
            "name": str(info_row["name"]),
            "id": database_id,
            "creation_date": str(info_row["creationDate"]),
        },
        "checks": checks,
        "ok": all(check["ok"] for check in checks),
        "failed_checks": [check["name"] for check in checks if not check["ok"]],
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for check in checks:
        print(("PASS" if check["ok"] else "FAIL") + f" {check['name']}")
    print(f"report={output}")
    return report


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expectations", required=True)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--expected-database-id", required=True)
    parser.add_argument("--forbid-database-id", action="append", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        report = verify(parse_args(argv if argv is not None else sys.argv[1:]))
        return 0 if report["ok"] else 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
