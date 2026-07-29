#!/usr/bin/env python3
"""Run the release routing matrix against a live local demo server."""

from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any, Dict, List


def ask(base_url: str, query: str, timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/ask",
        data=json.dumps({"query": query, "top_k": 5}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def run(base_url: str, timeout: float) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []

    capability = ask(base_url, "有哪些流程可以处理 MAF 文件", timeout)
    capability_ids = [
        item["tool_id"] for item in capability["capability_answer"]["pipelines"]
    ]
    assert capability["workflow_mode"] == "capability", capability
    assert capability["selection_status"] == "information", capability
    assert capability_ids == [
        "driver_gene_gender_analysis",
        "survival_analysis",
        "tmb_survival_analysis",
        "wes_somatic_maf_landscape",
    ], capability_ids
    summaries.append({
        "case": "capability_maf",
        "mode": capability["workflow_mode"],
        "selection_status": capability["selection_status"],
        "tool_ids": capability_ids,
    })

    recommendation = ask(
        base_url, "从 RNA-seq paired-end FASTQ 到表达矩阵选哪个流程", timeout
    )
    recommendation_ids = recommendation["workflow_plan"]["pipeline_ids"]
    assert recommendation["workflow_mode"] == "standard", recommendation
    assert recommendation_ids == ["rnaseq_singletask"], recommendation_ids
    assert recommendation["selection_status"] == "ready", recommendation
    summaries.append({
        "case": "singular_standard_recommendation",
        "mode": recommendation["workflow_mode"],
        "selection_status": recommendation["selection_status"],
        "tool_ids": recommendation_ids,
        "model": recommendation["llm"].get("model"),
        "llm_used": recommendation["llm"].get("used"),
    })

    combined = ask(
        base_url, "我有肝癌 MAF，先做突变景观，再做 TMB 生存分析", timeout
    )
    combined_ids = combined["workflow_plan"]["pipeline_ids"]
    assert combined["workflow_mode"] == "standard", combined
    assert combined_ids == [
        "wes_somatic_maf_landscape", "tmb_survival_analysis"
    ], combined_ids
    summaries.append({
        "case": "combined_standard_pipelines",
        "mode": combined["workflow_mode"],
        "selection_status": combined["selection_status"],
        "tool_ids": combined_ids,
        "model": combined["llm"].get("model"),
        "llm_used": combined["llm"].get("used"),
    })

    custom = ask(
        base_url,
        "修改完整双端 RNA-seq 上游流程：去掉 RSEM，只保留 featureCounts 计数，"
        "其余 FastQC、Trim Galore、STAR、SAMtools 和 MultiQC 保持。",
        timeout,
    )
    methods = custom["workflow_plan"]["methods"]
    custom_ids = [item["tool_id"] for item in methods]
    assert custom["workflow_mode"] == "custom", custom
    assert custom["workflow_plan"]["validation"]["ok"], custom["workflow_plan"]
    assert custom_ids == [
        "fastqc", "trim_galore", "star", "samtools", "featurecounts", "multiqc"
    ], custom_ids
    samtools = next(item for item in methods if item["tool_id"] == "samtools")
    assert samtools["inputs"]["aligned_bam"]["from"]["output"] == "aligned_bam"
    summaries.append({
        "case": "personalized_valid_custom_chain",
        "mode": custom["workflow_mode"],
        "selection_status": custom["selection_status"],
        "validation_ok": True,
        "tool_ids": custom_ids,
        "model": custom["llm"].get("model"),
        "llm_used": custom["llm"].get("used"),
    })

    blocked = ask(
        base_url, "把 RNA-seq 标准流程中的 RSEM 换成 Salmon", timeout
    )
    assert blocked["workflow_mode"] == "custom", blocked
    assert blocked["workflow_plan"]["execution_status"] == (
        "blocked_by_incomplete_method_decomposition"
    ), blocked["workflow_plan"]
    assert blocked["workflow_plan"]["validation"]["decomposition_gaps"], blocked
    summaries.append({
        "case": "personalized_missing_method",
        "mode": blocked["workflow_mode"],
        "selection_status": blocked["selection_status"],
        "execution_status": blocked["workflow_plan"]["execution_status"],
        "model": blocked["llm"].get("model"),
        "llm_used": blocked["llm"].get("used"),
    })
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8012")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    print(json.dumps(run(args.base_url, args.timeout), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
