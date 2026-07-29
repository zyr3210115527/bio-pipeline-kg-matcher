#!/usr/bin/env python3
"""Run the four-layer CSV/Neo4j data-matcher equivalence corpus."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PACKAGE_ROOT / "app" if (PACKAGE_ROOT / "app/pipeline_router.py").exists() else PACKAGE_ROOT
sys.path.insert(0, str(APP_ROOT))

from data_matcher.comparison import compare_results, load_allowlist  # noqa: E402
from data_matcher.neo4j_matcher import Neo4jKGDataMatcher  # noqa: E402
from pipeline_router import CsvKGDataMatcher  # noqa: E402
from runtime_config import initialize_runtime  # noqa: E402


PIPELINES = (
    "rnaseq_singletask",
    "paired_fastq_to_unmapped_bam",
    "diff_expr_go",
    "diff_expr_kegg",
    "rnaseq_unsupervised_cluster",
    "wgcna",
    "immune_infiltration_iobr",
    "her2_pfs_survival",
    "wes_somatic_maf_landscape",
    "survival_analysis",
    "tmb_survival_analysis",
    "driver_gene_gender_analysis",
)

PIPELINE_INTENTS: Dict[str, Dict[str, Any]] = {
    "rnaseq_singletask": {"query_text": "paired RNA-seq FASTQ upstream", "omics_type": "bulk RNA-seq", "input_hint": "FASTQ"},
    "paired_fastq_to_unmapped_bam": {"query_text": "paired FASTQ to uBAM", "input_hint": "fq.gz"},
    "diff_expr_go": {"query_text": "TPM differential expression GO", "input_hint": "TPM", "quant_hint": "TPM"},
    "diff_expr_kegg": {"query_text": "FPKM differential expression pathway", "input_hint": "FPKM", "quant_hint": "FPKM"},
    "rnaseq_unsupervised_cluster": {"query_text": "raw count matrix clustering", "input_hint": "tsv", "quant_hint": "count"},
    "wgcna": {"query_text": "expression clinical metainfo WGCNA"},
    "immune_infiltration_iobr": {"query_text": "TPM clinical metainfo immune infiltration", "quant_hint": "TPM"},
    "her2_pfs_survival": {"query_text": "TPM clinical metainfo PFS", "quant_hint": "TPM"},
    "wes_somatic_maf_landscape": {"query_text": "somatic MAF mutation landscape", "input_hint": "MAF"},
    "survival_analysis": {"query_text": "MAF clinical metainfo survival", "input_hint": "MAF"},
    "tmb_survival_analysis": {"query_text": "MAF clinical metainfo TMB survival", "input_hint": "MAF"},
    "driver_gene_gender_analysis": {"query_text": "MAF clinical metainfo driver gender", "input_hint": "MAF"},
}


def _case(case_id: str, layer: str, intent: Mapping[str, Any], pipeline_ids: Sequence[str]) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "layer": layer,
        "intent": dict(intent),
        "pipeline_ids": list(pipeline_ids),
    }


def test_regression_cases() -> Iterable[Dict[str, Any]]:
    yield _case("test-count-vs-tpm", "test_regression", {"query_text": "TPM matrix clustering", "input_hint": "TPM", "quant_hint": "TPM"}, ["rnaseq_unsupervised_cluster"])
    yield _case("test-rna-paired-fastq", "test_regression", {"query_text": "paired RNA-seq FASTQ", "omics_type": "bulk RNA-seq", "input_hint": "FASTQ"}, ["rnaseq_singletask"])
    yield _case("test-wes-paired-role", "test_regression", {"query_text": "paired tumor normal WES FASTQ", "omics_type": "WES", "input_hint": "FASTQ"}, ["wes_somatic_pair"])
    yield _case("test-abundance-go", "test_regression", {"query_text": "TPM GO enrichment", "input_hint": "TPM", "quant_hint": "TPM"}, ["diff_expr_go"])
    yield _case("test-maf-landscape", "test_regression", {"query_text": "MAF mutation landscape", "input_hint": "MAF"}, ["wes_somatic_maf_landscape"])
    yield _case("test-no-pipeline", "test_regression", {"query_text": "unknown data request"}, [])


def demo_cases(path: Path) -> Iterable[Dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    for index, entry in enumerate(value.get("cases") or []):
        yield _case(f"demo-{index + 1:02d}", "demo_queries", entry.get("intent") or {}, entry.get("pipeline_ids") or [])


def matrix_cases(csv_matcher: CsvKGDataMatcher) -> Iterable[Dict[str, Any]]:
    for study in csv_matcher.study:
        study_id = str(study.get("study_accession") or "unknown")
        disease = study.get("tumor_type") or None
        for pipeline_id in PIPELINES:
            intent = dict(PIPELINE_INTENTS[pipeline_id])
            intent["query_text"] = f"{study_id} {intent['query_text']}"
            intent["disease"] = disease
            yield _case(
                f"matrix-{study_id}-{pipeline_id}",
                "study_pipeline_matrix",
                intent,
                [pipeline_id],
            )


def boundary_cases() -> Iterable[Dict[str, Any]]:
    definitions = [
        ("HRA000021", "BAM scope boundary", {"input_hint": "BAM"}, ["wes_somatic_pair"]),
        ("HRA000122", "T11-only FASTQ scope boundary", {"input_hint": "FASTQ", "omics_type": "WES"}, ["wes_somatic_pair"]),
        ("HRA000321", "paired FASTQ edge", {"input_hint": "FASTQ", "omics_type": "bulk RNA-seq"}, ["rnaseq_singletask"]),
        ("HRA000873", "tumor normal pairing", {"input_hint": "FASTQ", "omics_type": "WES"}, ["wes_somatic_pair"]),
        ("T2-count", "count matrix", {"input_hint": "tsv", "quant_hint": "count"}, ["rnaseq_unsupervised_cluster"]),
        ("T2-TPM", "TPM matrix", {"input_hint": "TPM", "quant_hint": "TPM"}, ["immune_infiltration_iobr"]),
        ("T2-MAF", "MAF", {"input_hint": "MAF"}, ["wes_somatic_maf_landscape"]),
        ("T2-clinical", "clinical and metainfo", {}, ["survival_analysis"]),
        ("assay-empty", "FASTQ with empty assay metadata", {"input_hint": "FASTQ"}, ["rnaseq_singletask"]),
        ("size-suffix", "legacy byte size suffix", {"input_hint": "FASTQ"}, ["paired_fastq_to_unmapped_bam"]),
    ]
    for case_id, query, extra, pipelines in definitions:
        intent = {"query_text": query, **extra}
        yield _case(f"boundary-{case_id}", "boundary", intent, pipelines)


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", default="neo4j")
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--snapshot-id", default="dg-b23135d49c950d0846a563bc")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allowlist", default=str(APP_ROOT / "config/data_matcher_diff_allowlist.json"))
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    initialize_runtime()
    args = parse_args(argv if argv is not None else sys.argv[1:])
    password = os.environ.get(args.password_env)
    if not password:
        print(f"ERROR: password environment variable is not set: {args.password_env}", file=sys.stderr)
        return 1
    allowlist = load_allowlist(Path(args.allowlist))
    csv_started = time.perf_counter()
    csv_matcher = CsvKGDataMatcher()
    csv_init_ms = (time.perf_counter() - csv_started) * 1000
    neo_started = time.perf_counter()
    neo4j_matcher = Neo4jKGDataMatcher(
        uri=args.uri,
        user=args.user,
        password=password,
        database=args.database,
        snapshot_id=args.snapshot_id,
    )
    neo4j_init_ms = (time.perf_counter() - neo_started) * 1000
    cases = [
        *test_regression_cases(),
        *demo_cases(PACKAGE_ROOT / "docs/data_matcher_demo_cases.json"),
        *matrix_cases(csv_matcher),
        *boundary_cases(),
    ]
    reports: List[Dict[str, Any]] = []
    try:
        for case in cases:
            pipelines = [{"pipeline_id": pipeline_id} for pipeline_id in case["pipeline_ids"]]
            started = time.perf_counter()
            csv_result = csv_matcher.match(case["intent"], pipelines, limit=args.limit)
            csv_ms = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            neo4j_result = neo4j_matcher.match(case["intent"], pipelines, limit=args.limit)
            neo4j_ms = (time.perf_counter() - started) * 1000
            report = compare_results(
                case["case_id"],
                case["intent"],
                case["pipeline_ids"],
                csv_result,
                neo4j_result,
                {"csv": csv_ms, "neo4j": neo4j_ms},
            )
            report["layer"] = case["layer"]
            reports.append(report)
    finally:
        neo4j_matcher.close()

    csv_times = [item["timing_ms"]["csv"] for item in reports]
    neo4j_times = [item["timing_ms"]["neo4j"] for item in reports]
    layers: Dict[str, Dict[str, int]] = {}
    for report in reports:
        layer = layers.setdefault(report["layer"], {"cases": 0, "material_diff_count": 0})
        layer["cases"] += 1
        layer["material_diff_count"] += report["material_diff_count"]
    output = {
        "schema_version": "data-matcher-diff-suite/v1",
        "configuration": {
            "uri": args.uri,
            "database": args.database,
            "snapshot_id": args.snapshot_id,
            "limit": args.limit,
            "allowlist_rule_ids": [rule["id"] for rule in allowlist.get("rules") or [] if rule.get("enabled")],
        },
        "summary": {
            "case_count": len(reports),
            "material_diff_count": sum(item["material_diff_count"] for item in reports),
            "known_representation_diff_count": sum(item["known_representation_diff_count"] for item in reports),
            "layers": layers,
            "initialization_ms": {"csv": round(csv_init_ms, 3), "neo4j": round(neo4j_init_ms, 3)},
            "match_timing_ms": {
                "csv": {"median": round(statistics.median(csv_times), 3), "p95": round(percentile(csv_times, 0.95), 3), "max": round(max(csv_times), 3)},
                "neo4j": {"median": round(statistics.median(neo4j_times), 3), "p95": round(percentile(neo4j_times, 0.95), 3), "max": round(max(neo4j_times), 3)},
            },
        },
        "cases": reports,
    }
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2, sort_keys=True))
    print(f"report={output_path}")
    return 0 if output["summary"]["material_diff_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
