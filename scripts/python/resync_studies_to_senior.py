#!/usr/bin/env python3
"""Resync the 13 shared *original* studies' data lineage to exactly match the
senior's dataset ("全按她来", incl. t1/t2 granularity + missing individuals).

Why
---
After Phase 2 the 6 NEW studies already mirror her data. The 13 shared originals
still carry my *coarse* / drifted lineage:
  * t2: dir-level (6-16 nodes/study) vs her per-file (thousands)   -> different keys, MERGE alone would DOUBLE
  * t1: drifted counts (some more, some fewer than hers)           -> MERGE alone leaves stale extras
  * individual: gaps -> orphaned samples (HRA000122/000071/001749/007167)

So for each of the 13 studies we do a **full lineage replace**: delete my
individual/sample/run/t1/t2 for that study, then MERGE her translated lineage.
study + project nodes are kept and re-MERGE'd (property refresh only).

Scope guards
------------
* Only the 13 studies below. The 6 NEW studies (already hers) and my mine-only
  HRA000321 are never touched.
* The tool-catalog layer (tool_id/io_slot/... + builder_param) is never touched;
  verified by a before/after invariant.
* Safety: a study whose translated payload has 0 sample AND 0 t1 is SKIPPED
  (never wiped) -- prevents blanking a study if her CSV lacks its lineage.

Deletion order per study (must delete run via sample BEFORE deleting sample,
since run carries no study_accession and is only reachable run->IN_SAMPLE->sample):
    t1 -> t2 -> run(via sample) -> sample -> individual

Usage
-----
    python scripts/python/resync_studies_to_senior.py                  # dry-run
    python scripts/python/resync_studies_to_senior.py --import-dir DIR
    python scripts/python/resync_studies_to_senior.py --apply          # write
"""
from __future__ import annotations

import argparse
from pathlib import Path

from add_new_studies_lineage import (
    DEFAULT_IMPORT_DIR,
    NODE_KEY,
    TOOL_LABELS,
    build_payload,
    env_creds,
)

# The 13 shared originals (all her studies EXCEPT the 6 Phase-2 new ones).
SHARED_ORIGINAL = [
    "HRA000021", "HRA000071", "HRA000074", "HRA000122", "HRA000873",
    "HRA001272", "HRA001748", "HRA001749", "HRA003107", "HRA005191",
    "HRA006499", "HRA007167", "HRA007169",
]

LINEAGE_LABELS = ["individual", "sample", "run", "t1", "t2"]


def per_study_counts(payload) -> dict:
    """Group her translated payload counts by study_accession."""
    nodes = payload["nodes"]
    out = {a: {lab: 0 for lab in LINEAGE_LABELS} for a in SHARED_ORIGINAL}
    for lab in ("individual", "sample", "t1", "t2"):
        for row in nodes[lab]:
            a = row.get("study_accession", "")
            if a in out:
                out[a][lab] += 1
    # runs: attribute a run to a study via its sample (run_to_sample built into t1)
    run_study = {}
    for row in nodes["t1"]:
        r, a = row.get("run_accession", ""), row.get("study_accession", "")
        if r and a:
            run_study.setdefault(r, a)
    for a in run_study.values():
        if a in out:
            out[a]["run"] += 1
    return out


def apply(payload, targets: list[str]) -> None:
    from neo4j import GraphDatabase

    env = env_creds()
    driver = GraphDatabase.driver(
        env.get("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(env.get("NEO4J_USER", "neo4j"), env.get("NEO4J_PASSWORD", "neo4j")),
    )
    db = env.get("NEO4J_DATABASE", "neo4j")
    nodes, rels = payload["nodes"], payload["rels"]

    def count(session, label):
        return session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]

    try:
        with driver.session(database=db) as s:
            before_tools = {lab: count(s, lab) for lab in TOOL_LABELS}
            before_line = {lab: count(s, lab) for lab in NODE_KEY}

            # 1) delete existing lineage for each target study
            for acc in targets:
                s.run("MATCH (n:t1 {study_accession:$a}) DETACH DELETE n", a=acc)
                s.run("MATCH (n:t2 {study_accession:$a}) DETACH DELETE n", a=acc)
                s.run("MATCH (r:run)-[:IN_SAMPLE]->(:sample {study_accession:$a}) DETACH DELETE r", a=acc)
                s.run("MATCH (n:sample {study_accession:$a}) DETACH DELETE n", a=acc)
                s.run("MATCH (n:individual {study_accession:$a}) DETACH DELETE n", a=acc)

            # 2) reload her translated lineage (MERGE nodes then rels)
            for label, rows in nodes.items():
                if not rows:
                    continue
                key = NODE_KEY[label]
                s.run(
                    f"UNWIND $rows AS row MERGE (n:{label} {{{key}: row.{key}}}) SET n += row",
                    rows=rows,
                )
            for (a, t, b), rows in rels.items():
                if not rows:
                    continue
                ka, kb = NODE_KEY[a], NODE_KEY[b]
                s.run(
                    f"UNWIND $rows AS row "
                    f"MATCH (x:{a} {{{ka}: row.a}}), (y:{b} {{{kb}: row.b}}) "
                    f"MERGE (x)-[:{t}]->(y)",
                    rows=rows,
                )

            after_tools = {lab: count(s, lab) for lab in TOOL_LABELS}
            after_line = {lab: count(s, lab) for lab in NODE_KEY}

            # orphan-sample check across the target studies
            orphans = {}
            for acc in targets:
                orphans[acc] = s.run(
                    "MATCH (n:sample {study_accession:$a}) "
                    "WHERE NOT (n)-[:IN_INDIVIDUAL]->(:individual) RETURN count(n) AS c",
                    a=acc,
                ).single()["c"]
    finally:
        driver.close()

    print("=== 谱系节点计数 before -> after ===")
    for lab in NODE_KEY:
        d = after_line[lab] - before_line[lab]
        print(f"  {lab:11} {before_line[lab]:6} -> {after_line[lab]:6}  ({d:+d})")
    print("=== 工具层(必须零变化) ===")
    ok = True
    for lab in TOOL_LABELS:
        d = after_tools[lab] - before_tools[lab]
        if d != 0:
            ok = False
        print(f"  {lab:13} {before_tools[lab]} -> {after_tools[lab]}  {'OK' if d==0 else '!!! CHANGED'}")
    print("工具层不变" if ok else "警告: 工具层被改动!")
    print("=== 目标 study 悬空 sample(应全为 0)===")
    bad = [a for a, c in orphans.items() if c]
    for a, c in orphans.items():
        print(f"  {a:11} orphan_sample={c}")
    print("所有目标 study 悬空 sample 已清零" if not bad else f"警告: 仍有悬空: {bad}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--import-dir", default=str(DEFAULT_IMPORT_DIR))
    ap.add_argument("--apply", action="store_true", help="write to the live graph (default: dry-run)")
    args = ap.parse_args()

    payload = build_payload(Path(args.import_dir), set(SHARED_ORIGINAL))
    counts = per_study_counts(payload)

    print("=== 每个 study 将替换为师姐版本(她的目标计数)===")
    print(f"  {'study':11} {'indiv':>6} {'sample':>7} {'run':>6} {'t1':>6} {'t2':>6}")
    targets, skipped = [], []
    for acc in SHARED_ORIGINAL:
        c = counts[acc]
        print(f"  {acc:11} {c['individual']:6} {c['sample']:7} {c['run']:6} {c['t1']:6} {c['t2']:6}")
        # safety: never wipe a study her CSV has no lineage for
        if c["sample"] == 0 and c["t1"] == 0:
            skipped.append(acc)
        else:
            targets.append(acc)
    if skipped:
        print(f"\n[安全护栏] 以下 study 她的数据无血缘(sample=0 且 t1=0),将跳过、不删: {skipped}")
    print(f"\n将替换 {len(targets)} 个 study: {targets}")

    if args.apply:
        print("\n--- APPLYING (delete+reload per study) ---")
        apply(payload, targets)
    else:
        print("\n(dry-run; 未写入。加 --apply 才写。)")


if __name__ == "__main__":
    main()
