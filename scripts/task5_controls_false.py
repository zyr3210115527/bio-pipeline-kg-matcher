"""Historical control queries migrated to the Top-3 contract."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from workflow_composer import WorkflowComposer

QUERIES = [
    ("双端 FASTQ RNA-seq 上游", "我有双端 FASTQ 想做 RNA-seq 上游分析,需要表达矩阵和基因计数"),
    ("GO+KEGG 富集", "想同时做 GO 和 KEGG 富集"),
    ("单样本 WES FASTQ", "我有一个样本的 WES FASTQ,想做变异检测和注释"),
    ("配对肿瘤正常 WES", "我有肿瘤和正常配对的 WES FASTQ,想做体细胞变异检测并注释"),
]


def summarize(result):
    candidates = result.get("candidates") or []
    return {
        "status": result.get("selection_status"),
        "candidate_count": len(candidates),
        "chains": [[step.get("tool_id") for step in item.get("tool_chain") or []] for item in candidates],
        "rejected_candidates": (result.get("extensions") or {}).get("rejected_candidates", []),
    }


def main():
    composer = WorkflowComposer()
    out = {}
    for label, query in QUERIES:
        result = composer.plan(query, top_k=3)
        out[label] = summarize(result)
        print(f"{label}: {out[label]['status']} candidates={out[label]['candidate_count']}")
    with open("docs/task5_controls_false.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved docs/task5_controls_false.json")


if __name__ == "__main__":
    main()
