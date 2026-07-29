"""A4: Record LLM cassettes for 7 demo queries."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

os.environ["DEMO_RECORD"] = "1"

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
    for label, query in QUERIES:
        print(f"=== recording: {label} ===")
        result = composer.plan(query, top_k=3)
        print(f"  status={result.get('selection_status')} candidates={result.get('candidate_count')}")
    cassette_dir = REPO / "demo" / "cassettes"
    files = sorted(cassette_dir.glob("*.json"))
    print(f"\nrecorded {len(files)} cassettes in {cassette_dir}")
    for f in files:
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
