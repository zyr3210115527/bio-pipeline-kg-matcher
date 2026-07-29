#!/usr/bin/env python3
"""Backfill t1.file_path on the live graph from the source T1 CSV.

Why
---
The live `t1` (raw fastq) nodes were loaded with only `files` (bare filename)
and never got a `file_path` property (0 / 19178 carry one). But the source
`data/update728/csv/entities/T1.csv` encodes the real absolute path inside the
`dataName` column as `filename::/abs/path`. ~64% of rows carry a real path.

This makes `route_pipeline_request` recommendations able to emit real
`execution_params` for fastq-input pipelines instead of always reporting
`no_confirmed_path` (see execution_params derivation in workflow_composer).

What it does (and does NOT)
---------------------------
* ONLY sets `t1.file_path` on nodes matched by (study_accession, run_accession,
  files) whose source dataName carries a real `::/abs/path`. Idempotent.
* Never touches any other property, label, node, or edge. Tool catalog untouched.
* Rows whose dataName has no `::/path` (the ~36%) are left without a path.

Usage
-----
    python scripts/python/backfill_t1_file_path.py            # dry-run (default)
    python scripts/python/backfill_t1_file_path.py --apply    # write
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "update728" / "csv" / "entities" / "T1.csv"


def env_creds() -> dict:
    env = {}
    for line in (ROOT / ".env.local").read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
    return env


def parse_paths():
    """(study, run, filename) -> abs_path, for rows whose dataName has ::/path."""
    out = {}
    no_path = 0
    with CSV_PATH.open(newline="") as fh:
        for row in csv.DictReader(fh):
            data_name = (row.get("dataName") or "").strip()
            if "::" not in data_name:
                no_path += 1
                continue
            name, path = data_name.split("::", 1)
            name, path = name.strip(), path.strip()
            if not path.startswith("/"):
                no_path += 1
                continue
            key = (row["studyAccession"].strip(), row["runAccession"].strip(), name)
            out[key] = path
    return out, no_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write (default: dry-run)")
    args = ap.parse_args()

    paths, no_path = parse_paths()
    print(f"源 CSV: {CSV_PATH.relative_to(ROOT)}")
    print(f"  带真实路径的 (study,run,file) 键 : {len(paths)}")
    print(f"  无路径行(跳过)                   : {no_path}")

    env = env_creds()
    drv = GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"]))
    db = env.get("NEO4J_DATABASE", "neo4j")

    rows = [{"study": s, "run": r, "file": f, "path": p} for (s, r, f), p in paths.items()]

    with drv.session(database=db) as s:
        before = s.run(
            "MATCH (n:t1) WHERE n.file_path IS NOT NULL AND n.file_path<>'' RETURN count(n) AS c"
        ).single()["c"]
        total_t1 = s.run("MATCH (n:t1) RETURN count(n) AS c").single()["c"]

        # How many live t1 nodes would this actually match?
        matchable = s.run(
            "UNWIND $rows AS row "
            "MATCH (n:t1 {study_accession:row.study, run_accession:row.run, files:row.file}) "
            "RETURN count(n) AS c",
            rows=rows,
        ).single()["c"]

    print(f"\n活图 t1 总数                       : {total_t1}")
    print(f"  当前已带 file_path               : {before}")
    print(f"  本次可命中并回填的 t1 节点        : {matchable}")
    print(f"  回填后仍无 file_path 的 t1        : {total_t1 - matchable}")

    if not args.apply:
        print("\n[dry-run] 未写入。加 --apply 执行。")
        drv.close()
        return

    with drv.session(database=db) as s:
        res = s.run(
            "UNWIND $rows AS row "
            "MATCH (n:t1 {study_accession:row.study, run_accession:row.run, files:row.file}) "
            "WHERE n.file_path IS NULL OR n.file_path='' "
            "SET n.file_path = row.path "
            "RETURN count(n) AS c",
            rows=rows,
        ).single()["c"]
        after = s.run(
            "MATCH (n:t1) WHERE n.file_path IS NOT NULL AND n.file_path<>'' RETURN count(n) AS c"
        ).single()["c"]

    print(f"\n[apply] 本次写入 file_path 的节点  : {res}")
    print(f"[apply] 现在带 file_path 的 t1 总数 : {after}")
    drv.close()


if __name__ == "__main__":
    main()
