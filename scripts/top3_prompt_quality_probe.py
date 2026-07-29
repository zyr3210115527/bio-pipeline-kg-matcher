#!/usr/bin/env python3
"""Run live adversarial prompt checks against the Top-3 planner."""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime_config import get_llm_health, initialize_runtime

initialize_runtime(ROOT / ".env.local")

from workflow_composer import WorkflowComposer


CASES = [
    {
        "id": "fastqc_only",
        "query": "我有双端 bulk RNA-seq FASTQ，只做原始数据 FastQC 质控，不修剪、不比对，也不要表达定量。",
        "candidate_policy": "forbidden",
        "recommendation_forbidden": ["rnaseq_singletask"],
        "status_required": "unsupported",
    },
    {
        "id": "rnaseq_count_only",
        "query": "对双端 bulk RNA-seq FASTQ 做质控、修剪和 STAR 比对，最终只要基因 raw count 矩阵，不要 RSEM、TPM 或 FPKM。",
        "candidate_required": ["fastp", "star", "samtools", "featurecounts"],
        "candidate_forbidden": ["rsem"],
        "candidate_policy": "required",
    },
    {
        "id": "rnaseq_abundance_only",
        "query": "对双端 bulk RNA-seq FASTQ 做质控、修剪和 STAR 比对，最终只要 RSEM 的 TPM/FPKM 表达丰度，不要 featureCounts 或 raw count。",
        "candidate_required": ["fastp", "star", "rsem"],
        "candidate_forbidden": ["featurecounts"],
        "candidate_policy": "required",
    },
    {
        "id": "terminal_wgcna",
        "query": "已有 bulk RNA-seq count 矩阵和临床性状表，做 WGCNA 并输出模块、模块性状关联和 hub genes。",
        "candidate_policy": "forbidden",
        "recommendation_required": ["wgcna"],
    },
    {
        "id": "cellranger_10x",
        "query": "10x 单细胞 RNA-seq 双端 FASTQ 做 Cell Ranger，输出 filtered feature-barcode matrix。",
        "candidate_policy": "forbidden",
        "recommendation_required": ["cellranger_workflow"],
    },
    {
        "id": "paired_wes_annotated_vcf",
        "query": "肿瘤和正常配对 WES 四个 FASTQ，从质控比对开始，最终得到过滤并功能注释的 somatic VCF。",
        "candidate_policy": "forbidden",
        "recommendation_required": ["wes_somatic_pair"],
        "rejected_candidates_forbidden": True,
    },
    {
        "id": "maf_cannot_star",
        "query": "我只有一个体细胞突变 MAF 文件，请用 STAR 做转录组比对并生成基因 count 矩阵。",
        "candidate_policy": "forbidden",
        "recommendation_policy": "forbidden",
        "status_required": "unsupported",
    },
    {
        "id": "qc_without_read_changes",
        "query": "双端 FASTQ 只需要质量评估和汇总报告，任何 reads 都不能被修剪或修改。",
        "candidate_policy": "forbidden",
        "recommendation_policy": "forbidden",
        "status_required": "unsupported",
    },
    {
        "id": "fastq_to_ubam",
        "query": "同一样本的双端 FASTQ 转成带 read group 的 unmapped BAM，不做参考基因组比对。",
        "candidate_policy": "forbidden",
        "recommendation_required": ["paired_fastq_to_unmapped_bam"],
    },
    {
        "id": "upstream_then_wgcna",
        "query": "从双端 bulk RNA-seq FASTQ 开始完成上游处理，并继续做 WGCNA 模块和 hub gene 分析。",
        "candidate_policy": "forbidden",
        "recommendation_policy": "forbidden",
        "status_required": "unsupported",
    },
    {
        "id": "ambiguous_fastq_to_maf",
        "query": "我有一对双端 FASTQ，帮我一直分析到 MAF 突变文件。",
        "candidate_policy": "forbidden",
        "recommendation_forbidden": ["wes_somatic_pair"],
        "status_required": "unsupported",
    },
    {
        "id": "contradictory_rna_bwa",
        "query": "这是 bulk RNA-seq 双端 FASTQ，请用 BWA 做 DNA 体细胞变异检测并输出 somatic VCF。",
        "candidate_policy": "forbidden",
        "recommendation_policy": "forbidden",
        "status_required": "unsupported",
    },
]


def internal_chains(result: dict[str, Any]) -> list[list[str]]:
    return [
        [str(value) for value in (candidate.get("extensions") or {}).get("internal_tool_ids") or []]
        for candidate in result.get("candidates") or []
    ]


def assess(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    chains = internal_chains(result)
    top = chains[0] if chains else []
    recommendations = [
        str(item.get("pipeline_id") or "") for item in result.get("recommendations") or []
    ]
    failures = []
    policy = case.get("candidate_policy")
    if policy == "required" and not top:
        failures.append("expected a validated atomic candidate")
    if policy == "forbidden" and chains:
        failures.append("returned an atomic candidate for an unsupported/contradictory terminal goal")
    if case.get("recommendation_policy") == "forbidden" and recommendations:
        failures.append("returned a business recommendation for an incompatible request")
    for tool_id in case.get("candidate_required") or []:
        if tool_id not in top:
            failures.append(f"top candidate missing required tool: {tool_id}")
    for tool_id in case.get("candidate_forbidden") or []:
        if tool_id in top:
            failures.append(f"top candidate contains forbidden tool: {tool_id}")
    for pipeline_id in case.get("recommendation_required") or []:
        if pipeline_id not in recommendations:
            failures.append(f"missing expected business recommendation: {pipeline_id}")
    for pipeline_id in case.get("recommendation_forbidden") or []:
        if pipeline_id in recommendations:
            failures.append(f"returned forbidden business recommendation: {pipeline_id}")
    if case.get("status_required") and result.get("selection_status") != case["status_required"]:
        failures.append(
            f"expected status {case['status_required']}, got {result.get('selection_status')}"
        )
    rejected = (result.get("extensions") or {}).get("rejected_candidates") or []
    if case.get("rejected_candidates_forbidden", True) and rejected:
        failures.append("model produced a candidate that the deterministic validator rejected")
    return {
        "passed": not failures,
        "failures": failures,
        "selection_status": result.get("selection_status"),
        "candidate_chains": chains,
        "recommendations": recommendations,
        "unsupported_reason": result.get("unsupported_reason"),
        "rejected_candidates": rejected,
    }


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = WorkflowComposer().plan(case["query"], top_k=3)
        error = None
    except Exception as exc:  # Keep the batch auditable when one live call fails.
        result = {}
        error = f"{type(exc).__name__}: {exc}"
    assessment = assess(case, result) if not error else {
        "passed": False,
        "failures": ["probe exception"],
    }
    return {
        "id": case["id"],
        "probe_run": case.get("probe_run", 1),
        "query": case["query"],
        "elapsed_s": round(time.perf_counter() - started, 3),
        "assessment": assessment,
        "error": error,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    selected_cases = [
        case for case in CASES if not args.case_ids or case["id"] in set(args.case_ids)
    ]
    if args.case_ids and len(selected_cases) != len(set(args.case_ids)):
        parser.error("unknown --case id")
    expanded_cases = []
    for run_number in range(1, max(1, args.runs) + 1):
        for case in selected_cases:
            expanded_cases.append({**case, "probe_run": run_number})
    completed = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as executor:
        futures = {executor.submit(run_case, case): case for case in expanded_cases}
        for future in as_completed(futures):
            item = future.result()
            completed.append(item)
            print(json.dumps({
                "id": item["id"],
                "elapsed_s": item["elapsed_s"],
                **item["assessment"],
            }, ensure_ascii=False), flush=True)
    order = {case["id"]: index for index, case in enumerate(CASES)}
    completed.sort(key=lambda item: (order[item["id"]], item.get("probe_run", 1)))
    payload = {
        "schema_version": "top3-prompt-quality/v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "llm": get_llm_health(),
        "case_count": len(completed),
        "passed": sum(bool(item["assessment"].get("passed")) for item in completed),
        "failed": sum(not bool(item["assessment"].get("passed")) for item in completed),
        "cases": completed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "passed": payload["passed"],
        "failed": payload["failed"],
    }, ensure_ascii=False, indent=2))
    return 0 if payload["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
