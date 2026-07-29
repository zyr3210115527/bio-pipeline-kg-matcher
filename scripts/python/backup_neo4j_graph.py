#!/usr/bin/env python3
"""Create a read-only, restorable logical backup of one Neo4j database."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence

from neo4j import GraphDatabase, READ_ACCESS


def write_record(handle: Any, payload: Dict[str, Any]) -> None:
    handle.write((json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n").encode("utf-8"))


def backup(args: argparse.Namespace) -> Dict[str, Any]:
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {args.password_env}")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_path = output_dir / f"{args.prefix}_{timestamp}.jsonl.gz"

    driver = GraphDatabase.driver(args.uri, auth=(args.user, password))
    counts = {"nodes": 0, "relationships": 0, "constraints": 0, "indexes": 0}
    try:
        with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
            db_info = dict(
                session.run("CALL db.info() YIELD id,name,creationDate RETURN id,name,creationDate").single()
            )
            components = [
                dict(row)
                for row in session.run(
                    "CALL dbms.components() YIELD name,versions,edition RETURN name,versions,edition ORDER BY name"
                )
            ]
            constraints = [dict(row) for row in session.run("SHOW CONSTRAINTS YIELD * RETURN * ORDER BY name")]
            indexes = [dict(row) for row in session.run("SHOW INDEXES YIELD * RETURN * ORDER BY name")]
            with backup_path.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as handle:
                    write_record(
                        handle,
                        {
                            "kind": "metadata",
                            "format": "neo4j-logical-backup/v1",
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "source_uri": args.uri,
                            "source_database": args.database,
                            "database": db_info,
                            "components": components,
                        },
                    )
                    for row in constraints:
                        write_record(handle, {"kind": "constraint", "value": row})
                        counts["constraints"] += 1
                    for row in indexes:
                        write_record(handle, {"kind": "index", "value": row})
                        counts["indexes"] += 1
                    result = session.run(
                        "MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS properties "
                        "ORDER BY elementId(n)"
                    )
                    for row in result:
                        write_record(handle, {"kind": "node", "value": dict(row)})
                        counts["nodes"] += 1
                        if counts["nodes"] % 10000 == 0:
                            print(f"[backup] nodes={counts['nodes']}")
                    result = session.run(
                        "MATCH (a)-[r]->(b) RETURN elementId(r) AS id, elementId(a) AS start_id, "
                        "elementId(b) AS end_id, type(r) AS type, properties(r) AS properties "
                        "ORDER BY elementId(r)"
                    )
                    for row in result:
                        write_record(handle, {"kind": "relationship", "value": dict(row)})
                        counts["relationships"] += 1
                        if counts["relationships"] % 20000 == 0:
                            print(f"[backup] relationships={counts['relationships']}")
                    write_record(handle, {"kind": "trailer", "counts": counts})
    finally:
        driver.close()

    digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    metadata = {
        "format": "neo4j-logical-backup/v1",
        "backup_path": str(backup_path),
        "sha256": digest,
        "counts": counts,
        "database": db_info,
        "components": components,
        "restore_command_template": (
            ".venv/bin/python scripts/python/restore_neo4j_graph.py "
            f"--backup '{backup_path}' --uri <isolated-uri> --database <empty-database> "
            "--user neo4j --password-env <PASSWORD_ENV> --expected-database-id <EMPTY_DB_ID> "
            f"--forbid-database-id {db_info['id']}"
        ),
    }
    metadata_path = backup_path.with_suffix(backup_path.suffix + ".manifest.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[backup] path={backup_path}")
    print(f"[backup] sha256={digest}")
    print(f"[backup] counts={json.dumps(counts, sort_keys=True)}")
    return metadata


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prefix", default="production_full_logical_backup")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        backup(parse_args(argv if argv is not None else sys.argv[1:]))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
