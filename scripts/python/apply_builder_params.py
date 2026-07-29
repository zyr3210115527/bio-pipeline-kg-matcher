#!/usr/bin/env python3
"""Attach real PipelineBuilder WDL parameter names to pipeline io_slots.

Background
----------
The MCP output emits each pipeline input slot's ``slot_name`` (e.g. ``somatic_maf``)
which does NOT match the actual PipelineBuilder WDL parameter name a submitter
must fill (e.g. ``maf_file``). This adds two additive fields to each pipeline
input slot:

* ``builder_param`` — the real PipelineBuilder parameter name (``interface.params[].name``)
* ``wdl_target``     — the fully-qualified WDL key (``interface.params[].target``)

Source of truth: the senior's ``workflow.zip`` knowledge cards
(``<pipeline>/knowledge_card.yaml`` → ``interface.params``). The mapping below was
extracted from those cards and pinned here so the change is reviewable and
reproducible without re-reading the zip.

The mapping is keyed by graph ``slot_id`` (per-pipeline, namespaced — no sharing),
so setting a per-slot value can never collide across pipelines.

Usage
-----
    python scripts/python/apply_builder_params.py            # rewrite CSV copies
    python scripts/python/apply_builder_params.py --neo4j    # also SET on live graph
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# slot_id -> (builder_param, wdl_target)
# Extracted from workflow.zip/<pipeline>/knowledge_card.yaml interface.params.
# paired_fastq_to_unmapped_bam::in::fastq_{1,2} are intentionally absent: that
# pipeline resolves FASTQs via a db_sample_lookup resolver (params sample_name /
# sample_accession), so its fastq slots have no direct file WDL parameter.
MAPPING: dict[str, tuple[str, str]] = {
    # differential expression + enrichment
    "diff_expr_go::in::expression": ("expression_matrix", "DiffExprGoWorkflow.expression_matrix"),
    "diff_expr_kegg::in::expression": ("expression_matrix", "DiffExprKeggWorkflow.expression_matrix"),
    # driver gene gender stratification
    "driver_gene_gender_analysis::in::maf": ("maf", "driver_gene_gender_analysis.maf"),
    "driver_gene_gender_analysis::in::clinical": ("clinical_xls", "driver_gene_gender_analysis.clinical_xls"),
    "driver_gene_gender_analysis::in::metainfo": ("metainfo_xlsx", "driver_gene_gender_analysis.metainfo_xlsx"),
    # HER2 expression + PFS survival
    "her2_pfs_survival::in::expression": ("tpm_matrix", "her2_pfs_survival.tpm_matrix"),
    "her2_pfs_survival::in::clinical": ("clinical_xls", "her2_pfs_survival.clinical_xls"),
    "her2_pfs_survival::in::metainfo": ("metainfo_xlsx", "her2_pfs_survival.metainfo_xlsx"),
    # immune infiltration (IOBR CIBERSORT)
    "immune_infiltration_iobr::in::expression": ("expression_tsv", "ImmuneInfiltrationIOBRCIBERSORT.expression_tsv"),
    "immune_infiltration_iobr::in::clinical": ("clinical_xls", "ImmuneInfiltrationIOBRCIBERSORT.clinical_xls"),
    "immune_infiltration_iobr::in::metainfo": ("metainfo_xlsx", "ImmuneInfiltrationIOBRCIBERSORT.metainfo_xlsx"),
    # RNA-seq single-task upstream
    "rnaseq_singletask::input::fastq_1": ("sample_r1", "RNASeqPipeline.sample_r1"),
    "rnaseq_singletask::input::fastq_2": ("sample_r2", "RNASeqPipeline.sample_r2"),
    "rnaseq_singletask::input::rrna_star_index": ("rrna_star_index", "RNASeqPipeline.rrna_star_index"),
    "rnaseq_singletask::input::star_genome_index": ("star_genome_index", "RNASeqPipeline.star_genome_index"),
    "rnaseq_singletask::input::rsem_index": ("rsem_index", "RNASeqPipeline.rsem_index"),
    "rnaseq_singletask::input::gtf_file": ("gtf_file", "RNASeqPipeline.gtf_file"),
    # RNA-seq unsupervised clustering
    "rnaseq_unsupervised_cluster::in::counts": ("count_tsv", "rnaseq_unsupervised_cluster.count_tsv"),
    # survival analysis
    "survival_analysis::in::maf": ("maf_file", "SurvivalAnalysis.maf_file"),
    "survival_analysis::in::clinical": ("clinical_file", "SurvivalAnalysis.clinical_file"),
    "survival_analysis::in::metainfo": ("metainfo_file", "SurvivalAnalysis.metainfo_file"),
    # TMB + survival
    "tmb_survival_analysis::in::maf": ("maf_file", "TMBSurvivalAnalysis.maf_file"),
    "tmb_survival_analysis::in::clinical": ("clinical_file", "TMBSurvivalAnalysis.clinical_file"),
    "tmb_survival_analysis::in::metainfo": ("metainfo_file", "TMBSurvivalAnalysis.metainfo_file"),
    # WES somatic MAF landscape
    "wes_somatic_maf_landscape::in::maf": ("maf_file", "wes_somatic_maf_landscape.maf_file"),
    # WGCNA
    "wgcna::in::counts": ("counts_tsv", "HRA000074_WGCNA.counts_tsv"),
    "wgcna::in::clinical": ("clinical_xls", "HRA000074_WGCNA.clinical_xls"),
    "wgcna::in::metainfo": ("metainfo_xlsx", "HRA000074_WGCNA.metainfo_xlsx"),
}

NEW_COLS = ["builder_param", "wdl_target"]

# The canonical source read by scripts/python/sync_neo4j_tool_catalog.py, plus the
# packaged delivery copies kept in lock-step. Timestamped snapshots under outputs/
# are historical and intentionally NOT touched.
CSV_COPIES = [
    ROOT / "data" / "csv" / "catalog" / "io_slot.csv",
    ROOT / "data" / "update728" / "csv" / "catalog" / "io_slot.csv",
    ROOT / "docs" / "mcp_delivery" / "app" / "data" / "csv" / "catalog" / "io_slot.csv",
]


def rewrite_csv(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    for col in NEW_COLS:
        if col not in fieldnames:
            fieldnames.append(col)
    hits = 0
    for row in rows:
        slot_id = row.get("slot_id") or ""
        bp, wt = MAPPING.get(slot_id, ("", ""))
        # preserve any pre-existing value if this run doesn't cover the slot
        row["builder_param"] = bp or row.get("builder_param", "") or ""
        row["wdl_target"] = wt or row.get("wdl_target", "") or ""
        if bp:
            hits += 1
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return hits


def patch_neo4j() -> int:
    from neo4j import GraphDatabase  # local import; only needed with --neo4j

    env = {}
    env_path = ROOT / ".env.local"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    uri = env.get("NEO4J_URI") or os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = env.get("NEO4J_USER") or os.environ.get("NEO4J_USER", "neo4j")
    pwd = env.get("NEO4J_PASSWORD") or os.environ.get("NEO4J_PASSWORD", "neo4j")
    db = env.get("NEO4J_DATABASE") or os.environ.get("NEO4J_DATABASE", "neo4j")
    rows = [{"slot_id": k, "bp": v[0], "wt": v[1]} for k, v in MAPPING.items()]
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session(database=db) as session:
            res = session.run(
                "UNWIND $rows AS row "
                "MATCH (s) WHERE (s:io_slot OR s:IOSlot) AND s.slot_id = row.slot_id "
                "SET s.builder_param = row.bp, s.wdl_target = row.wt "
                "RETURN count(s) AS n",
                rows=rows,
            )
            n = res.single()["n"]
        return n
    finally:
        driver.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--neo4j", action="store_true", help="also SET builder_param/wdl_target on the live graph")
    args = ap.parse_args()

    for path in CSV_COPIES:
        if path.exists():
            hits = rewrite_csv(path)
            print(f"[csv] {path.relative_to(ROOT)}: {hits} slots mapped")
        else:
            print(f"[csv] SKIP (missing): {path}")

    if args.neo4j:
        n = patch_neo4j()
        print(f"[neo4j] SET builder_param/wdl_target on {n} io_slot nodes")


if __name__ == "__main__":
    main()
