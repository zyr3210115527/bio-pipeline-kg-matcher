#!/usr/bin/env python3
"""Replay the questions from 测试报告.md against the current backend.

The report was produced against a deployment that predates the 0811 migration:
its `health_check` returns 82,659 nodes with a `run` label and expects snapshot
`dg-b23135…`, which is the graph and the config we replaced on 2026-08-12. So
the report cannot tell us whether the current backend answers these questions --
it only tells us what that older deployment did.

This replays the exact wording through `WorkflowComposer.plan()`, which is what
`route_pipeline_request` calls, so the two can be compared case by case. It
deliberately does not assert anything: the point is to see what comes back.

    python3 scripts/probe_test_report.py
    python3 scripts/probe_test_report.py --only failing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 报告里列出的用例，group 是报告给的结论
CASES: List[Dict[str, str]] = [
    # 报告说这 5 个「未触发工具」——但工具调用列表为空，说明是他们的 agent 没调我们
    ("failing", "肝癌 TPM 表达矩阵能做免疫浸润分析吗？", "immune_infiltration_iobr"),
    ("failing", "食管癌 counts 数据怎么做无监督聚类？", "rnaseq_unsupervised_cluster"),
    ("failing", "肝癌 MAF 文件怎么画突变景观图？", "wes_somatic_maf_landscape"),
    ("failing", "RNA-seq FASTQ 原始数据怎么做完整上游分析？", "rnaseq_singletask"),
    ("failing", "胶质瘤 counts 矩阵怎么做 WGCNA？", "wgcna"),
    # 报告说这 4 个命中了
    ("passing", "黑色素瘤患者的 TMB 高低和生存预后有没有关系？", "tmb_survival_analysis"),
    ("passing", "肝癌 EGFR 突变和 PFS 有关系吗？", "survival_analysis"),
    ("passing", "肝癌突变数据能不能比较男女患者的驱动基因差异？", "driver_gene_gender_analysis"),
    ("passing", "胶质瘤能做 HER2 表达和 PFS 的生存分析吗？", "her2_pfs_survival"),
    # 假基因：报告说无脑回退到 her2_pfs_survival
    ("fakegene", "肝癌 XXX6 表达高低和 PFS 有关系吗？", "应拒绝或说明基因未知"),
    ("fakegene", "肺癌 XXX6 表达高低和 PFS 有关系吗？", "应拒绝或说明基因未知"),
    ("fakegene", "食管癌 XXX6 表达高低和 PFS 有关系吗？", "应拒绝或说明基因未知"),
    # 无意义/超纲：报告说卡在「无法可靠区分」
    ("nonsense", "苹果的红色程度和 PFS 有关系吗？", "应明确不支持"),
    ("nonsense", "胃癌患者的身高体重和总生存期有关系吗？", "应明确不支持"),
    ("nonsense", "今天天气怎么样？", "应明确不支持"),
    # 元数据类：报告说被硬塞进方案匹配
    ("metadata", "服务器上有哪些可用的队列数据？", "能力/元数据问答"),
    ("metadata", "HRA001272 队列里有多少个样本？", "能力/元数据问答"),
    ("metadata", "帮我看看 HRA001272 的临床数据里都有哪些字段", "能力/元数据问答"),
    # 英文
    ("english", "Can you analyze whether high ERBB2 expression relates to PFS in liver cancer?", "her2_pfs_survival"),
    ("english", "黑色素瘤 HER2 表达和 PFS", "her2_pfs_survival"),
]


def summarize(result: Dict[str, Any]) -> Dict[str, Any]:
    recs = result.get("recommendations") or []
    cands = result.get("candidates") or []
    planner = result.get("planner_metadata") or {}
    return {
        "status": result.get("selection_status"),
        "recommendations": [
            {
                "pipeline_id": r.get("pipeline_id"),
                "study": r.get("study_accession"),
                "note": (r.get("match_note") or "")[:70],
                "feasibility": r.get("feasibility_status"),
            }
            for r in recs[:3]
        ],
        "candidate_count": len(cands),
        "candidate_chains": [
            "->".join(str(s.get("tool_id")) for s in (c.get("tool_chain") or []))
            for c in cands[:2]
        ],
        "unsupported_reason": (result.get("unsupported_reason") or "")[:110],
        "llm_used": planner.get("used"),
    }


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="", help="逗号分隔的分组：failing/passing/fakegene/nonsense/metadata/english")
    parser.add_argument("--json-out", default="docs/probe_test_report_result.json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    groups = {g.strip() for g in args.only.split(",") if g.strip()}
    from workflow_composer import WorkflowComposer

    composer = WorkflowComposer()
    out: List[Dict[str, Any]] = []
    for group, prompt, expected in CASES:
        if groups and group not in groups:
            continue
        try:
            summary = summarize(composer.plan(prompt))
            error = None
        except Exception as exc:  # noqa: BLE001 - 探针要把异常也当成一种结果记下来
            summary, error = {}, f"{type(exc).__name__}: {exc}"
        record = {"group": group, "prompt": prompt, "report_expected": expected,
                  "result": summary, "error": error}
        out.append(record)
        recs = summary.get("recommendations") or []
        head = recs[0]["pipeline_id"] if recs else "—"
        print(f"[{group:<9}] {prompt[:34]:<36} status={summary.get('status','ERR'):<12} "
              f"pipeline={str(head):<28} 候选={summary.get('candidate_count','-')}")
        if error:
            print(f"              {error}")
    Path(args.json_out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细 -> {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
