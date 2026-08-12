#!/usr/bin/env python3
"""Rebuild the 0811 graph on a remote Neo4j reachable only over bolt.

``import_0811.py`` needs the CSVs sitting in the server's ``import/`` directory
because the delivery is written as ``LOAD CSV FROM 'file:///…'``. For a remote
server we have no filesystem access, so each ``LOAD CSV … AS row`` clause is
rewritten to ``UNWIND $rows AS row`` and the rows are streamed from the local
CSVs in batches. Everything after that clause -- the MERGE/SET bodies, the
constraints and the indexes -- is the delivery's Cypher verbatim, so the result
is the same graph the local import produces.

Two details keep the emulation faithful to ``LOAD CSV``:

* empty fields become ``null`` rather than ``""``, which is what the server does
  when it parses a CSV itself. The delivery relies on this in its
  ``WHERE … IS NOT NULL`` guards;
* the BOM is stripped on read, so the delivery's ``coalesce(row.x, row['\\ufeffx'])``
  fallbacks resolve through the first branch.

``--write-specimen`` is the one deliberate deviation and is off by default. See
``_write_specimen`` for what it writes and why the property names differ from
the sidecar's.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

from neo4j import GraphDatabase

DELETE_BATCH = 20000
LOAD_CSV_RE = re.compile(
    r"(?is)^\s*LOAD\s+CSV\s+WITH\s+HEADERS\s+FROM\s+'file:///([^']+)'\s+AS\s+(\w+)\s+(.*)$"
)


def split_statements(text: str) -> List[str]:
    lines = [line for line in text.splitlines() if line.strip() and not line.strip().startswith("//")]
    body = "\n".join(lines)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return [stmt.strip() for stmt in body.split(";") if stmt.strip()]


def load_rows(path: Path) -> List[Dict[str, Any]]:
    """Read a CSV the way the server's LOAD CSV would hand it to Cypher."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: List[Dict[str, Any]] = []
        for raw in reader:
            row: Dict[str, Any] = {}
            for key, value in raw.items():
                if key is None:
                    continue
                if isinstance(value, list):
                    value = ",".join(part for part in value if part)
                row[key] = None if value in (None, "") else value
            rows.append(row)
    return rows


def chunked(rows: Sequence[Dict[str, Any]], size: int) -> Iterator[List[Dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield list(rows[start : start + size])


def run_statement(
    driver: Any,
    database: str,
    statement: str,
    csv_root: Path,
    batch_rows: int,
) -> None:
    match = LOAD_CSV_RE.match(statement)
    if not match:
        with driver.session(database=database) as session:
            session.run(statement).consume()
        return

    relative, variable, body = match.group(1), match.group(2), match.group(3)
    path = csv_root / relative
    if not path.exists():
        raise FileNotFoundError(path)
    rows = load_rows(path)
    unwound = f"UNWIND $rows AS {variable}\n{body}"

    done = 0
    started = time.monotonic()
    with driver.session(database=database) as session:
        for chunk in chunked(rows, batch_rows):
            session.run(unwound, rows=chunk).consume()
            done += len(chunk)
            if len(rows) > batch_rows:
                elapsed = time.monotonic() - started
                print(f"        {done:>7,}/{len(rows):,}  {elapsed:5.1f}s", flush=True)
    print(f"        {len(rows):,} 行  {time.monotonic() - started:.1f}s", flush=True)


def run_file(driver: Any, database: str, path: Path, csv_root: Path, batch_rows: int) -> None:
    statements = split_statements(path.read_text(encoding="utf-8"))
    print(f"[RUN] {path.name} ({len(statements)} 条语句)", flush=True)
    for index, statement in enumerate(statements, start=1):
        print(f"    [{index:02d}] {statement.splitlines()[0][:88]}", flush=True)
        run_statement(driver, database, statement, csv_root, batch_rows)
    print(f"[OK ] {path.name}\n", flush=True)


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
            print(f"    [clear] 已删 {deleted:,}", flush=True)
        remaining = int(session.run("MATCH (n) RETURN count(n) AS c").single()["c"])
    if remaining:
        raise RuntimeError(f"清空后仍剩 {remaining} 个节点")
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
            "relationships": int(
                session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            ),
        }
    return {"labels": labels, "relationships": relationships, "totals": totals}


def compare_to_reference(counts: Dict[str, Any], reference: Dict[str, Any]) -> List[str]:
    problems: List[str] = []
    for key, expected in reference["totals"].items():
        actual = counts["totals"][key]
        if actual != expected:
            problems.append(f"总{key}: 期望 {expected:,}, 实际 {actual:,}")
    for section in ("labels", "relationships"):
        expected_section = reference[section]
        actual_section = counts[section]
        for name in sorted(set(expected_section) | set(actual_section)):
            expected = expected_section.get(name, 0)
            actual = actual_section.get(name, 0)
            if expected != actual:
                problems.append(f"{section} {name}: 期望 {expected:,}, 实际 {actual:,}")
    return problems


def _write_specimen(driver: Any, database: str, path: Path, batch_rows: int) -> Dict[str, int]:
    """Put the recovered tumor/normal split onto the server's sample nodes.

    The runtime never reads this: the matcher loads the same CSV as an in-memory
    sidecar. It exists so anyone querying this server directly can tell tumor
    from normal, which the 0811 delivery on its own cannot express.

    The sidecar's own column names are not reused. Its ``tissue_type`` holds
    Tumor/Normal, while the 0811 ``sample`` table already uses ``tissue_type``
    for the material (Blood) on 557 rows. Writing ours under the same name would
    leave one property carrying two meanings, so the role goes to ``sample_role``
    and only ``specimen_types`` -- which the delivery does not set at all --
    keeps its name.
    """
    rows = []
    for row in load_rows(path):
        role = str(row.get("tissue_type") or "").strip().lower()
        rows.append(
            {
                "sample_accession": row.get("sample_accession"),
                "specimen_types": row.get("specimen_types"),
                "sample_role": role if role in {"tumor", "normal"} else None,
            }
        )
    statement = """
    UNWIND $rows AS row
    MATCH (s:sample {sample_accession: row.sample_accession})
    SET s.specimen_types = row.specimen_types,
        s.sample_role = row.sample_role,
        s.specimen_source = 'pre-0811-backfill'
    """
    matched = 0
    with driver.session(database=database) as session:
        for chunk in chunked(rows, batch_rows):
            summary = session.run(statement, rows=chunk).consume()
            matched += summary.counters.properties_set
        covered = int(
            session.run(
                "MATCH (s:sample) WHERE s.sample_role IS NOT NULL RETURN count(s) AS c"
            ).single()["c"]
        )
    return {"csv_rows": len(rows), "properties_set": matched, "samples_with_role": covered}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--csv-source", default="data/0811")
    parser.add_argument("--cypher-dir", default="cypher/import0811")
    parser.add_argument("--uri", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--database", default="neo4j")
    parser.add_argument("--batch-rows", type=int, default=5000)
    parser.add_argument("--reference", default="config/senior_0811_reference_counts.json")
    parser.add_argument(
        "--write-specimen",
        default="",
        help="路径给定时，导入后把 tumor/normal 写回 sample 节点（偏离 0811 原样）",
    )
    parser.add_argument("--confirm-clear", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_clear:
        parser.error("--confirm-clear is required; this rebuild wipes the database")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = Path(args.project_root).resolve()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"密码环境变量未设置: {args.password_env}")

    cypher_dir = root / args.cypher_dir
    csv_root = root / args.csv_source
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

    started = time.monotonic()
    driver = GraphDatabase.driver(args.uri, auth=(args.user, password), connection_timeout=15)
    try:
        with driver.session(database=args.database) as session:
            info = session.run(
                "CALL dbms.components() YIELD versions,edition RETURN versions[0] AS v, edition"
            ).single()
        print(f"[db] {args.uri} {args.database} Neo4j {info['v']} {info['edition']}\n", flush=True)

        cleared = clear_graph(driver, args.database)
        print(
            f"[clear] 节点 {cleared['deleted_nodes']:,} "
            f"约束 {len(cleared['dropped']['constraints'])} "
            f"索引 {len(cleared['dropped']['indexes'])}\n",
            flush=True,
        )

        for path in files:
            run_file(driver, args.database, path, csv_root, args.batch_rows)

        counts = report_counts(driver, args.database)
        reference = json.loads((root / args.reference).read_text(encoding="utf-8"))
        problems = compare_to_reference(counts, reference)

        specimen = None
        if args.write_specimen:
            print("[specimen] 写回 tumor/normal", flush=True)
            specimen = _write_specimen(
                driver, args.database, root / args.write_specimen, args.batch_rows
            )
            print(f"    {specimen}\n", flush=True)
    finally:
        driver.close()

    print("=" * 52)
    print(
        f"节点 {counts['totals']['nodes']:,}  关系 {counts['totals']['relationships']:,}"
        f"  用时 {time.monotonic() - started:.0f}s"
    )
    for label, count in counts["labels"].items():
        print(f"  {label:<14} {count:>7,}")
    for rel_type, count in counts["relationships"].items():
        print(f"  [{rel_type:<16}] {count:>7,}")
    if specimen:
        print(f"  sample_role 覆盖 {specimen['samples_with_role']:,} 个 sample")
    print("=" * 52)
    if problems:
        print("与师姐 0811 权威计数不一致:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"与师姐 0811 权威计数逐项一致（{args.reference}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
