#!/usr/bin/env python3
"""Rebuild the Neo4j graph from the 0812 data delivery.

The delivery in ``cypher/import0812/`` is used verbatim for the reference,
entity, ontology and workflow statements. Only two things are handled here
instead of in Cypher:

* the clear step drops every constraint and index by name (including our own
  ``tool_catalog_id_unique``) and deletes nodes in batches, because a single
  ``MATCH (n) DETACH DELETE n`` over ~80k nodes is heap-hostile;
* oversized ``LOAD CSV`` statements are retried inside ``CALL { } IN
  TRANSACTIONS`` when the server rejects them for memory.

The result is the 0812 delivery and nothing else: no extra labels, no extra
properties. Our slot model and execution bindings are not written into the
graph at all -- they are merged in at runtime by ``tool_catalog_source``.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

from neo4j import GraphDatabase


CSV_SUBDIRS = ("entities", "reference", "relations")
DELETE_BATCH = 20000


def split_statements(text: str) -> List[str]:
    lines = [line for line in text.splitlines() if line.strip() and not line.strip().startswith("//")]
    return [stmt.strip() for stmt in "\n".join(lines).split(";") if stmt.strip()]


def batched_load_csv(statement: str, rows: int) -> str:
    """Wrap the body after the LOAD CSV clause in CALL { } IN TRANSACTIONS."""
    match = re.match(
        r"(?is)^\s*(LOAD\s+CSV\s+WITH\s+HEADERS\s+FROM\s+'[^']+'\s+AS\s+(\w+))\s+(.*)$",
        statement,
    )
    if not match:
        raise RuntimeError("statement is not a simple LOAD CSV; cannot batch it")
    header, variable, body = match.group(1), match.group(2), match.group(3)
    return f"{header}\nCALL ({variable}) {{\n{body}\n}} IN TRANSACTIONS OF {rows} ROWS"


def run_statement(driver: Any, database: str, statement: str, batch_rows: int) -> None:
    try:
        with driver.session(database=database) as session:
            session.run(statement).consume()
        return
    except Exception as exc:  # noqa: BLE001 - retry policy depends on the message
        message = str(exc)
        retryable = "memory" in message.lower() or "OutOfMemory" in message
        if not (retryable and statement.lstrip().upper().startswith("LOAD CSV")):
            raise
        print(f"    [RETRY] batching after: {message.splitlines()[0][:120]}")
    with driver.session(database=database) as session:
        session.run(batched_load_csv(statement, batch_rows)).consume()


def run_file(driver: Any, database: str, path: Path, batch_rows: int) -> None:
    statements = split_statements(path.read_text(encoding="utf-8"))
    print(f"[RUN] {path.name} ({len(statements)} statements)")
    for index, statement in enumerate(statements, start=1):
        head = statement.splitlines()[0][:96]
        print(f"    [{index:02d}] {head}")
        run_statement(driver, database, statement, batch_rows)
    print(f"[OK ] {path.name}")


def sync_csv(source: Path, target: Path) -> Dict[str, int]:
    copied: Dict[str, int] = {}
    for name in CSV_SUBDIRS:
        src = source / name
        if not src.is_dir():
            raise RuntimeError(f"missing CSV directory: {src}")
        dst = target / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        copied[name] = len(list(dst.glob("*.csv")))
    return copied


def clear_graph(driver: Any, database: str) -> Dict[str, Any]:
    dropped: Dict[str, List[str]] = {"constraints": [], "indexes": []}
    with driver.session(database=database) as session:
        for row in session.run("SHOW CONSTRAINTS YIELD name RETURN name"):
            dropped["constraints"].append(str(row["name"]))
        for name in dropped["constraints"]:
            session.run(f"DROP CONSTRAINT `{name}` IF EXISTS").consume()
        for row in session.run("SHOW INDEXES YIELD name,type RETURN name,type"):
            if str(row["type"]).upper() == "LOOKUP":
                continue
            dropped["indexes"].append(str(row["name"]))
        for name in dropped["indexes"]:
            session.run(f"DROP INDEX `{name}` IF EXISTS").consume()

        deleted = 0
        while True:
            summary = session.run(
                f"MATCH (n) WITH n LIMIT {DELETE_BATCH} DETACH DELETE n"
            ).consume()
            if not summary.counters.nodes_deleted:
                break
            deleted += summary.counters.nodes_deleted
            print(f"    [clear] deleted={deleted}")
        remaining = int(session.run("MATCH (n) RETURN count(n) AS c").single()["c"])
    if remaining:
        raise RuntimeError(f"graph not empty after clear: {remaining} nodes remain")
    return {"dropped": dropped, "deleted_nodes": deleted}


def report_counts(driver: Any, database: str) -> Dict[str, Any]:
    with driver.session(database=database) as session:
        labels = {
            str(row["label"]): int(row["count"])
            for row in session.run(
                "MATCH (n) UNWIND labels(n) AS label "
                "RETURN label, count(*) AS count ORDER BY count DESC"
            )
        }
        relationships = {
            str(row["type"]): int(row["count"])
            for row in session.run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC"
            )
        }
        totals = {
            "nodes": int(session.run("MATCH (n) RETURN count(n) AS c").single()["c"]),
            "relationships": int(session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]),
        }
    return {"labels": labels, "relationships": relationships, "totals": totals}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--csv-source", default="data/0812")
    parser.add_argument("--cypher-dir", default="cypher/import0812")
    parser.add_argument("--neo4j-import-dir", required=True)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--expected-database-id", required=True)
    parser.add_argument("--batch-rows", type=int, default=5000)
    parser.add_argument(
        "--confirm-clear",
        action="store_true",
        help="required; the clear step wipes every node, constraint and index",
    )
    parser.add_argument("--skip-csv-sync", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_clear:
        parser.error("--confirm-clear is required; this rebuild wipes the database")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.project_root).resolve()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {args.password_env}")

    cypher_dir = root / args.cypher_dir
    files = [
        cypher_dir / "constraints.cypher",
        cypher_dir / "indexes.cypher",
        cypher_dir / "01_import_reference.cypher",
        cypher_dir / "02_import_entities.cypher",
        cypher_dir / "03_import_ontology_relations.cypher",
        cypher_dir / "04_import_workflow_relations.cypher",
    ]
    for path in files:
        if not path.exists():
            raise FileNotFoundError(path)

    if not args.skip_csv_sync:
        copied = sync_csv(root / args.csv_source, Path(args.neo4j_import_dir))
        print(f"[csv] synced {copied} -> {args.neo4j_import_dir}")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, password))
    try:
        with driver.session(database=args.database) as session:
            database_id = str(session.run("CALL db.info() YIELD id RETURN id").single()["id"])
        if database_id != args.expected_database_id:
            raise RuntimeError(
                f"database id mismatch: expected {args.expected_database_id}, got {database_id}"
            )
        print(f"[db] {args.database} id={database_id}")

        cleared = clear_graph(driver, args.database)
        print(
            f"[clear] nodes={cleared['deleted_nodes']} "
            f"constraints={len(cleared['dropped']['constraints'])} "
            f"indexes={len(cleared['dropped']['indexes'])}"
        )

        for path in files:
            run_file(driver, args.database, path, args.batch_rows)

        counts = report_counts(driver, args.database)
    finally:
        driver.close()

    print("=" * 46)
    print(f"nodes={counts['totals']['nodes']} relationships={counts['totals']['relationships']}")
    for label, count in counts["labels"].items():
        print(f"  {label:20} {count}")
    for rel_type, count in counts["relationships"].items():
        print(f"  [{rel_type:22}] {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
