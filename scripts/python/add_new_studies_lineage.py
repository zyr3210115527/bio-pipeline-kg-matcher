#!/usr/bin/env python3
"""Merge the senior's 6 NEW studies' data lineage into the live Neo4j graph.

Context
-------
The senior's latest dataset (packaged as a full neo4j-community distribution)
carries 6 studies my graph lacks:

    HRA000073  HRA000087  HRA002693  HRA006117  HRA007413  HRA016026

Her graph uses a *different* model (Capitalized labels, ``NEXT_TOOL``,
``T1_in_sample``/``T1_in_modal``, no ``io_slot`` observability layer). My MCP
backend queries the *lowercase* lineage model (``study``/``sample``/``individual``/
``run``/``t1``/``t2``) plus a tool-catalog layer (``tool_id``/``io_slot``/...).
So we do NOT import her schema. We read her raw entity CSVs, translate the 6
new studies into MY lowercase schema, and MERGE only the data-lineage nodes and
edges. The tool-catalog / io_slot / builder_param layer is never touched.

Target schema (verified against the live graph)
-----------------------------------------------
Nodes (lowercase):  project study individual sample run t1 t2
Edges:  (study)-[:IN_PROJECT]->(project)
        (individual)-[:IN_STUDY]->(study)
        (sample)-[:IN_INDIVIDUAL]->(individual)
        (run)-[:IN_SAMPLE]->(sample)
        (t1)-[:IN_RUN]->(run)
        (t1)-[:IN_STUDY]->(study)
        (t2)-[:IN_STUDY]->(study)
Node keys:  project.project_accession, study.study_accession,
            individual.individual_accession, sample.sample_accession,
            run.run_accession, t1.files, t2.t2_id

Usage
-----
    python scripts/python/add_new_studies_lineage.py                 # dry-run (no writes)
    python scripts/python/add_new_studies_lineage.py --import-dir DIR # override her import/ path
    python scripts/python/add_new_studies_lineage.py --apply          # write to live graph

The live graph carries NO ``datagraph_managed`` marker (legacy load), so the new
nodes deliberately carry none either — they stay schema-identical to the
existing lineage nodes.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMPORT_DIR = Path(
    "/tmp/herzip/neo4j-community-2026.06.0/import"
)

NEW_STUDIES = {
    "HRA000073",
    "HRA000087",
    "HRA002693",
    "HRA006117",
    "HRA007413",
    "HRA016026",
}

# Tool-catalog labels that must remain byte-for-byte untouched. Used only as a
# post-write invariant check.
TOOL_LABELS = ["tool_id", "io_slot", "artifact_type", "function", "format"]


# --------------------------------------------------------------------------- #
# CSV loading (her CSVs mix UTF-8 and GB18030)
# --------------------------------------------------------------------------- #
def load_csv(path: Path) -> List[Dict[str, str]]:
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    return [
        {k: (v if v is not None else "") for k, v in row.items()}
        for row in csv.DictReader(text.splitlines())
    ]


def clean(value: str) -> str:
    """Normalise dirty sentinels to empty string."""
    v = (value or "").strip()
    if v.lower() in {"null", "na", "n/a", "none", "nan", "-"}:
        return ""
    return v


def infer_read_pair(name: str) -> str:
    lowered = (name or "").lower()
    if re.search(r"(_r?1|_f1|read1)", lowered):
        return "R1"
    if re.search(r"(_r?2|_f2|read2)", lowered):
        return "R2"
    return ""


def infer_physical_format(name: str) -> str:
    lowered = (name or "").lower()
    for suffix in ("fastq.gz", "fq.gz", "xlsx", "xls", "tsv", "csv", "maf", "vcf", "bam", "h5"):
        if lowered.endswith(suffix):
            return suffix
    return ""


# --------------------------------------------------------------------------- #
# Translate her rows -> my lowercase node property dicts
# --------------------------------------------------------------------------- #
def build_payload(import_dir: Path, studies: "set[str] | None" = None) -> Dict[str, object]:
    """Translate the senior's raw CSVs for ``studies`` into my lowercase schema.

    ``studies`` defaults to the 6 NEW studies (original Phase-2 behaviour); pass a
    different set to translate any subset of her dataset (e.g. the 13 shared
    originals for a full "align to hers" resync).
    """
    studies = set(studies) if studies is not None else NEW_STUDIES
    E = import_dir / "entities"
    R = import_dir / "relations"

    study = [r for r in load_csv(E / "study.csv") if r["study_accession"] in studies]
    project_rows = load_csv(E / "project.csv")
    project = [r for r in project_rows if r.get("study_accession") in studies]
    individual = [r for r in load_csv(E / "individual.csv") if r.get("study_accession") in studies]
    sample_all = load_csv(E / "sample.csv")
    sample = [r for r in sample_all if r.get("study_accession") in studies]
    sample_study = {r["sample_accession"]: r.get("study_accession", "") for r in sample_all}
    sample_strategy = {r["sample_accession"]: r.get("experimental_strategy", "") for r in sample_all}
    t1_all = load_csv(E / "T1.csv")
    t1 = [r for r in t1_all if sample_study.get(r.get("sample_accession", "")) in studies]
    t2 = [r for r in load_csv(E / "T2.csv") if r.get("study_accession") in studies]

    sip = {
        r["study_accession"]: r["project_accession"]
        for r in load_csv(R / "study_in_project.csv")
        if r["study_accession"] in studies
    }

    # ---- nodes (my schema) ----
    n_study = [
        {
            "study_accession": r["study_accession"],
            "title": clean(r.get("Title", "")),
            "study_description": clean(r.get("study_description", "")),
            "study_type": clean(r.get("study_type", "")),
            "tumor_type": clean(r.get("tumor_type", "")),
            "individual_count": clean(r.get("individual_count", "")),
            "sample_count": clean(r.get("sample_count", "")),
            "information_source": clean(r.get("information_source", "")),
        }
        for r in study
    ]

    n_project = [
        {
            "project_accession": r["project_accession"],
            "project_name": clean(r.get("project_name", "")),
            "project_code": clean(r.get("project_code", "")),
            "project_description": clean(r.get("project_description", "")),
            "relevance": clean(r.get("relevance", "")),
            "sample_scope": clean(r.get("sample_scope", "")),
            "data_types": clean(r.get("data_types", "")),
            "organisms": clean(r.get("organism", "")),
            "individual_count": clean(r.get("individual_count", "")),
            "country": clean(r.get("country", "")),
            "tumor_type": clean(r.get("tumor_type", "")),
            "type": clean(r.get("type", "")),
            "organization": clean(r.get("organization", "")),
            "release_date": clean(r.get("release_date", "")),
            "submission_date": clean(r.get("submission_date", "")),
            "information_source": clean(r.get("information_source", "")),
            "study_accession": clean(r.get("study_accession", "")),
        }
        for r in project
    ]

    n_individual = [
        {
            "individual_accession": r["individual_accession"],
            "individual_id": clean(r.get("individual_id", "")),
            "study_accession": clean(r.get("study_accession", "")),
            "project_accession": clean(r.get("project_accession", "")),
            "project_name": clean(r.get("project_name", "")),
            "tumor_type": clean(r.get("tumor_type", "")),
            "tumor_subtype": clean(r.get("tumor_subtype", "")),
            "primary_tumor_site": clean(r.get("primary_tumor_site", "")),
            "primary_tumor_location": clean(r.get("primary_tumor_location", "")),
            "gender": clean(r.get("gender", "")),
            "country": clean(r.get("country", "")),
            "race": clean(r.get("race", "")),
            "age": clean(r.get("age", "")),
            "tumor_grade": clean(r.get("tumor_grade", "")),
            "treatment_intent_type": clean(r.get("treatment_intent_type", "")),
            "neoadjuvant_treatment_type": clean(r.get("neoadjuvant_treatment_type", "")),
            "neoadjuvant_treatment_agents": clean(r.get("neoadjuvant_treatment_agents", "")),
            "adjuvant_treatment_outcome_response": clean(
                r.get("neoadjuvant_treatment_outcome_(pathological_response)", "")
            ),
            "sample_type": clean(r.get("sample_type", "")),
            "specimen_types": clean(r.get("specimen_types", "")),
            "overall_survival_time": clean(r.get("overall_survival_time", "")),
            "overall_survival_days": clean(r.get("survival_days", "")),
            "overall_vital_status": clean(r.get("vital_status", "")),
            "dfs_status": clean(r.get("dfs_status", "")),
        }
        for r in individual
    ]

    n_sample = [
        {
            "sample_accession": r["sample_accession"],
            "study_accession": clean(r.get("study_accession", "")),
            "sample_name": clean(r.get("sample_name", "")),
            "sample_description": "",
            "individual_accession": clean(r.get("individual_accession", "")),
            "individual_name": clean(r.get("individual_id", "")),
            "biospecimen_anatomic_site": clean(r.get("biospecimen_anatomic_site", "")),
            "sample_type": "",
            "specimen_types": clean(r.get("specimen_type", "")),
            "strategy": clean(r.get("experimental_strategy", "")),
            "tissue_type": clean(r.get("tissue_type", "")),
        }
        for r in sample
    ]

    n_t1 = []
    run_to_sample: Dict[str, str] = {}
    for r in t1:
        fname = clean(r.get("file_name", ""))
        sacc = clean(r.get("sample_accession", ""))
        racc = clean(r.get("run_accession", ""))
        study_acc = sample_study.get(sacc, "")
        if racc and sacc:
            run_to_sample.setdefault(racc, sacc)
        n_t1.append(
            {
                "files": fname,
                "run_accession": racc,
                "sample_accession": sacc,
                "individual_accession": clean(r.get("individual_accession", "")),
                "study_accession": study_acc,
                "experiment_accession": clean(r.get("experiment_accession", "")),
                "platform": clean(r.get("platform", "")),
                "data_level": clean(r.get("data_level", "")),
                "strategy": sample_strategy.get(sacc, ""),
                "format": infer_physical_format(fname) or clean(r.get("format", "")),
                "read_pair": infer_read_pair(fname),
            }
        )

    n_t2 = [
        {
            "t2_id": r["T2_id"],
            "study_accession": clean(r.get("study_accession", "")),
            "files": clean(r.get("file_name", "")),
            "file_path": clean(r.get("file_path", "")),
            "format": clean(r.get("format", "")),
            "size": clean(r.get("size", "")),
            "strategy": clean(r.get("strategy", "")),
            "data_level": clean(r.get("data_level", "")),
            "file_type": "",
            "size_bytes": "",
        }
        for r in t2
    ]

    n_run = [{"run_accession": racc} for racc in sorted(run_to_sample)]

    # ---- relationships (endpoint key pairs) ----
    rel_study_project = [
        {"a": s, "b": p} for s, p in sip.items()
    ]
    rel_ind_study = [
        {"a": r["individual_accession"], "b": clean(r.get("study_accession", ""))}
        for r in individual
        if clean(r.get("study_accession", ""))
    ]
    rel_sample_ind = [
        {"a": r["sample_accession"], "b": clean(r.get("individual_accession", ""))}
        for r in sample
        if clean(r.get("individual_accession", ""))
    ]
    rel_run_sample = [{"a": racc, "b": sacc} for racc, sacc in sorted(run_to_sample.items())]
    rel_t1_run = [
        {"a": t["files"], "b": t["run_accession"]} for t in n_t1 if t["files"] and t["run_accession"]
    ]
    rel_t1_study = [
        {"a": t["files"], "b": t["study_accession"]} for t in n_t1 if t["files"] and t["study_accession"]
    ]
    rel_t2_study = [
        {"a": t["t2_id"], "b": t["study_accession"]} for t in n_t2 if t["t2_id"] and t["study_accession"]
    ]

    return {
        "nodes": {
            "study": n_study,
            "project": n_project,
            "individual": n_individual,
            "sample": n_sample,
            "run": n_run,
            "t1": n_t1,
            "t2": n_t2,
        },
        "rels": {
            ("study", "IN_PROJECT", "project"): rel_study_project,
            ("individual", "IN_STUDY", "study"): rel_ind_study,
            ("sample", "IN_INDIVIDUAL", "individual"): rel_sample_ind,
            ("run", "IN_SAMPLE", "sample"): rel_run_sample,
            ("t1", "IN_RUN", "run"): rel_t1_run,
            ("t1", "IN_STUDY", "study"): rel_t1_study,
            ("t2", "IN_STUDY", "study"): rel_t2_study,
        },
    }


NODE_KEY = {
    "study": "study_accession",
    "project": "project_accession",
    "individual": "individual_accession",
    "sample": "sample_accession",
    "run": "run_accession",
    "t1": "files",
    "t2": "t2_id",
}


def env_creds() -> Dict[str, str]:
    env: Dict[str, str] = {}
    p = ROOT / ".env.local"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def report(payload: Dict[str, object]) -> None:
    nodes = payload["nodes"]
    rels = payload["rels"]
    print("=== 将新增节点(MERGE, 按 key 幂等) ===")
    for label, rows in nodes.items():
        keys = {r[NODE_KEY[label]] for r in rows}
        print(f"  {label:11} rows={len(rows):5}  unique_keys={len(keys)}")
    print("=== 将新增关系 ===")
    for (a, t, b), rows in rels.items():
        print(f"  ({a})-[:{t}]->({b}): {len(rows)}")
    print("=== 样例翻译 ===")
    if nodes["t1"]:
        t = nodes["t1"][0]
        print(f"  t1: files={t['files']} read_pair={t['read_pair']} format={t['format']} "
              f"strategy={t['strategy']} study={t['study_accession']}")
    if nodes["t2"]:
        t = nodes["t2"][0]
        print(f"  t2: t2_id={t['t2_id'][:48]}... files={t['files']} format={t['format']} study={t['study_accession']}")
    if nodes["study"]:
        s = nodes["study"][0]
        print(f"  study: {s['study_accession']} title={s['title'][:40]!r} type={s['study_type']}")


def apply(payload: Dict[str, object]) -> None:
    from neo4j import GraphDatabase

    env = env_creds()
    uri = env.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = env.get("NEO4J_USER", "neo4j")
    pwd = env.get("NEO4J_PASSWORD", "neo4j")
    db = env.get("NEO4J_DATABASE", "neo4j")
    nodes = payload["nodes"]
    rels = payload["rels"]

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(database=db) as session:
            before_tools = {
                lab: session.run(f"MATCH (n:{lab}) RETURN count(n) AS c").single()["c"]
                for lab in TOOL_LABELS
            }
            before_lineage = {
                lab: session.run(f"MATCH (n:{lab}) RETURN count(n) AS c").single()["c"]
                for lab in NODE_KEY
            }
            for label, rows in nodes.items():
                if not rows:
                    continue
                key = NODE_KEY[label]
                session.run(
                    f"UNWIND $rows AS row MERGE (n:{label} {{{key}: row.{key}}}) SET n += row",
                    rows=rows,
                )
            for (a, t, b), rows in rels.items():
                if not rows:
                    continue
                ka, kb = NODE_KEY[a], NODE_KEY[b]
                session.run(
                    f"UNWIND $rows AS row "
                    f"MATCH (x:{a} {{{ka}: row.a}}), (y:{b} {{{kb}: row.b}}) "
                    f"MERGE (x)-[:{t}]->(y)",
                    rows=rows,
                )
            after_tools = {
                lab: session.run(f"MATCH (n:{lab}) RETURN count(n) AS c").single()["c"]
                for lab in TOOL_LABELS
            }
            after_lineage = {
                lab: session.run(f"MATCH (n:{lab}) RETURN count(n) AS c").single()["c"]
                for lab in NODE_KEY
            }

    finally:
        driver.close()

    print("=== 谱系节点计数 before -> after ===")
    for lab in NODE_KEY:
        print(f"  {lab:11} {before_lineage[lab]:6} -> {after_lineage[lab]:6}  (+{after_lineage[lab]-before_lineage[lab]})")
    print("=== 工具层计数(必须零变化) ===")
    ok = True
    for lab in TOOL_LABELS:
        delta = after_tools[lab] - before_tools[lab]
        flag = "OK" if delta == 0 else "!!! CHANGED"
        if delta != 0:
            ok = False
        print(f"  {lab:13} {before_tools[lab]} -> {after_tools[lab]}  {flag}")
    print("工具层不变" if ok else "警告: 工具层被改动!")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--import-dir", default=str(DEFAULT_IMPORT_DIR))
    ap.add_argument("--apply", action="store_true", help="write to the live graph (default: dry-run)")
    args = ap.parse_args()

    import_dir = Path(args.import_dir)
    payload = build_payload(import_dir)
    report(payload)
    if args.apply:
        print("\n--- APPLYING to live graph ---")
        apply(payload)
    else:
        print("\n(dry-run; 未写入。加 --apply 才写。)")


if __name__ == "__main__":
    main()
