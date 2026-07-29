"""A2: Measure end-to-end latency for 7 demo queries, 5 runs each."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from workflow_composer import WorkflowComposer

QUERIES = [
    ("配对肿瘤正常 WES", "我有肿瘤和正常配对的 WES FASTQ,想做体细胞变异检测并注释"),
    ("trim_to_fastp", "RNA-seq 上游流程里把 trim_galore 换成 fastp,其他不变"),
    ("双端 FASTQ RNA-seq 上游", "我有双端 FASTQ 想做 RNA-seq 上游分析,需要表达矩阵和基因计数"),
    ("TPM 聚类", "我有 TPM 矩阵想做无监督聚类"),
    ("GO+KEGG 富集", "想同时做 GO 和 KEGG 富集"),
    ("单样本 WES FASTQ", "我有一个样本的 WES FASTQ,想做变异检测和注释"),
    ("MAF 能力", "有哪些流程可以处理 MAF 文件"),
]


def main():
    composer = WorkflowComposer()
    results: dict = {}
    for label, query in QUERIES:
        times = []
        print(f"=== {label}: 5 runs ===")
        runs = []
        for i in range(5):
            start = time.perf_counter()
            result = composer.plan(query, top_k=3)
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            pm = result.get("planner_metadata") or {}
            runs.append({
                "run": i + 1,
                "elapsed_ms": round(elapsed * 1000, 1),
                "selection_status": result.get("selection_status"),
                "candidate_count": result.get("candidate_count"),
                "llm_calls": pm.get("calls"),
                "llm_tokens": pm.get("total_tokens"),
            })
            print(f"  run {i+1}: {elapsed*1000:.1f} ms")
        times_sorted = sorted(times)
        results[label] = {
            "query": query,
            "runs": runs,
            "min_ms": round(min(times) * 1000, 1),
            "median_ms": round(times_sorted[len(times)//2] * 1000, 1),
            "max_ms": round(max(times) * 1000, 1),
            "mean_ms": round(sum(times) / len(times) * 1000, 1),
        }
    out_path = REPO / "docs" / "a2_latency_probe.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
