"""Historical MultiQC measurements migrated to the Top-3 contract."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workflow_composer import WorkflowComposer

RNA_SEQ_QUERY = "我有双端 FASTQ 想做 RNA-seq 上游分析,需要表达矩阵和基因计数"
CONTROL_QUERIES = [
    ("双端 FASTQ RNA-seq 上游", RNA_SEQ_QUERY),
    ("GO+KEGG 富集", "想同时做 GO 和 KEGG 富集"),
    ("单样本 WES FASTQ", "我有一个样本的 WES FASTQ,想做变异检测和注释"),
    ("配对肿瘤正常 WES", "我有肿瘤和正常配对的 WES FASTQ,想做体细胞变异检测并注释"),
]


def summarize_run(result):
    candidates = result.get("candidates") or []
    return {
        "status": result.get("selection_status"),
        "candidate_count": len(candidates),
        "chains": [[step.get("tool_id") for step in item.get("tool_chain") or []] for item in candidates],
        "rejected_candidates": (result.get("extensions") or {}).get("rejected_candidates", []),
    }


def main():
    composer = WorkflowComposer()

    # Part 1: 10 runs after fix
    print("=== Part 1: 10 Top-3 RNA-seq runs ===")
    after_results = []
    for i in range(10):
        result = composer.plan(RNA_SEQ_QUERY, top_k=3)
        run = summarize_run(result)
        run["run"] = i + 1
        after_results.append(run)
        print(f"run {i+1}: {run['status']} candidates={run['candidate_count']}")
    ok_count = sum(1 for r in after_results if r["candidate_count"] > 0)
    print(f"\n=== summary: nonempty={ok_count}/10 ===")

    # Part 2: control queries
    print("\n=== Part 2: control queries ===")
    control_results = {}
    for label, query in CONTROL_QUERIES:
        result = composer.plan(query, top_k=3)
        control_results[label] = summarize_run(result)
        run = control_results[label]
        print(f"{label}: {run['status']} candidates={run['candidate_count']}")

    output = {
        "after_fix_10_runs": after_results,
        "control_queries": control_results,
    }
    with open("docs/task5_after_fix.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\nSaved to docs/task5_after_fix.json")


if __name__ == "__main__":
    main()
