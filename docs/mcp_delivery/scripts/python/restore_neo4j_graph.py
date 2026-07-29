#!/usr/bin/env python3
"""Restore a neo4j-logical-backup/v1 archive into an explicitly empty database."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from neo4j import GraphDatabase, WRITE_ACCESS

from datagraph_common import chunked, safe_identifier


def records(path: Path) -> Iterable[Dict[str, Any]]:
    with gzip.open(path, mode="rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def add_if_not_exists(statement: str) -> str:
    if re.match(r"^CREATE\s+CONSTRAINT\s+", statement, flags=re.I):
        return re.sub(r"^(CREATE\s+CONSTRAINT\s+`?[^`\s]+`?)\s+", r"\1 IF NOT EXISTS ", statement, count=1, flags=re.I)
    if re.match(r"^CREATE(?:\s+RANGE|\s+TEXT|\s+POINT|\s+LOOKUP|\s+FULLTEXT)?\s+INDEX\s+", statement, flags=re.I):
        return re.sub(r"^(CREATE(?:\s+RANGE|\s+TEXT|\s+POINT|\s+LOOKUP|\s+FULLTEXT)?\s+INDEX\s+`?[^`\s]+`?)\s+", r"\1 IF NOT EXISTS ", statement, count=1, flags=re.I)
    return statement


def restore(args: argparse.Namespace) -> None:
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {args.password_env}")
    backup_path = Path(args.backup).resolve()
    grouped_nodes: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
    grouped_relationships: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    constraints: List[str] = []
    indexes: List[str] = []
    metadata: Dict[str, Any] = {}
    trailer: Dict[str, Any] = {}
    for record in records(backup_path):
        kind = record["kind"]
        if kind == "metadata":
            metadata = record
        elif kind == "node":
            value = record["value"]
            labels = tuple(sorted(str(label) for label in value["labels"]))
            grouped_nodes[labels].append(value)
        elif kind == "relationship":
            value = record["value"]
            grouped_relationships[str(value["type"])].append(value)
        elif kind == "constraint":
            statement = record["value"].get("createStatement")
            if statement:
                constraints.append(str(statement))
        elif kind == "index":
            value = record["value"]
            statement = value.get("createStatement")
            if statement and not value.get("owningConstraint"):
                indexes.append(str(statement))
        elif kind == "trailer":
            trailer = record

    driver = GraphDatabase.driver(args.uri, auth=(args.user, password))
    try:
        with driver.session(database=args.database, default_access_mode=WRITE_ACCESS) as session:
            info = session.run("CALL db.info() YIELD id,name RETURN id,name").single()
            database_id = str(info["id"])
            if database_id != args.expected_database_id:
                raise RuntimeError(f"database id mismatch: expected {args.expected_database_id}, got {database_id}")
            if database_id in set(args.forbid_database_id):
                raise RuntimeError(f"refusing forbidden database id: {database_id}")
            count = int(session.run("MATCH (n) RETURN count(n) AS count").single()["count"])
            if count:
                raise RuntimeError(f"restore target must be empty; found {count} nodes")
            session.run(
                "CREATE CONSTRAINT logical_backup_id_unique IF NOT EXISTS "
                "FOR (n:__LogicalBackupNode) REQUIRE n.__backup_id IS UNIQUE"
            ).consume()
            for labels in sorted(grouped_nodes):
                clause = "".join(f":`{safe_identifier(label)}`" for label in labels)
                rows = sorted(grouped_nodes[labels], key=lambda row: row["id"])
                batches = list(chunked(rows, args.batch_size))
                query = f"UNWIND $rows AS row CREATE (n:__LogicalBackupNode{clause}) SET n = row.properties, n.__backup_id = row.id"
                for index, batch in enumerate(batches, start=1):
                    session.run(query, rows=list(batch)).consume()
                    print(f"[restore nodes {labels}] {index}/{len(batches)} rows={len(batch)}")
            for rel_type in sorted(grouped_relationships):
                rows = sorted(grouped_relationships[rel_type], key=lambda row: row["id"])
                batches = list(chunked(rows, args.batch_size))
                query = (
                    "UNWIND $rows AS row MATCH (a:__LogicalBackupNode {__backup_id: row.start_id}) "
                    "MATCH (b:__LogicalBackupNode {__backup_id: row.end_id}) "
                    f"CREATE (a)-[r:`{safe_identifier(rel_type)}`]->(b) SET r = row.properties"
                )
                for index, batch in enumerate(batches, start=1):
                    session.run(query, rows=list(batch)).consume()
                    print(f"[restore rels {rel_type}] {index}/{len(batches)} rows={len(batch)}")
            session.run("MATCH (n:__LogicalBackupNode) REMOVE n.__backup_id REMOVE n:__LogicalBackupNode").consume()
            session.run("DROP CONSTRAINT logical_backup_id_unique IF EXISTS").consume()
            for statement in sorted(set(constraints)):
                session.run(add_if_not_exists(statement)).consume()
            for statement in sorted(set(indexes)):
                session.run(add_if_not_exists(statement)).consume()
            session.run("CALL db.awaitIndexes($seconds)", seconds=300).consume()
            actual_nodes = int(session.run("MATCH (n) RETURN count(n) AS count").single()["count"])
            actual_rels = int(session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"])
            expected = trailer.get("counts", {})
            if actual_nodes != int(expected.get("nodes", -1)) or actual_rels != int(expected.get("relationships", -1)):
                raise RuntimeError(
                    f"restored counts mismatch: expected={expected}, actual_nodes={actual_nodes}, actual_rels={actual_rels}"
                )
            print(f"[restore] source_database={metadata.get('database')}")
            print(f"[restore] nodes={actual_nodes} relationships={actual_rels}")
    finally:
        driver.close()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--expected-database-id", required=True)
    parser.add_argument("--forbid-database-id", action="append", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        restore(parse_args(argv if argv is not None else sys.argv[1:]))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
