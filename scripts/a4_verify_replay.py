"""A4: Verify DEMO_REPLAY=1 can run all 7 demo queries offline."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

os.environ["DEMO_REPLAY"] = "1"
os.environ["LLM_API_KEY"] = "invalid-to-prove-no-network"
os.environ["LLM_BASE_URL"] = "https://invalid.local"

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
    ok = 0
    for label, query in QUERIES:
        try:
            result = composer.plan(query, top_k=3)
            print(f"OK {label}: {result.get('selection_status')} candidates={result.get('candidate_count')}")
            ok += 1
        except Exception as e:
            print(f"FAIL {label}: {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(QUERIES)} replayed successfully")
    return 0 if ok == len(QUERIES) else 1


if __name__ == "__main__":
    sys.exit(main())
