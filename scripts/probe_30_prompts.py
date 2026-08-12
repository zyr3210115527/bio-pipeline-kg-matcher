#!/usr/bin/env python3
"""30 条自拟提问的回归探针，按业务契约逐条判定结论是否正确。

覆盖六个维度：能力问答、RNA-seq 上游、WES/WGS、未原子化需求、输入与方法冲突、
数据可用性。每条不是只看"跑没跑通"，而是断言契约里真正该成立的东西：

* `information` 只属于确定性能力问答路径（`planner_metadata.used` 必须为 False）；
* 分析请求要么给出通过校验且数据齐全的原子链，要么明确说明为什么给不出；
* 输入与方法冲突时，recommendations 和 candidates 必须同时为空；
* 目录边界（单样本 GATK、GATK->BCFtools 传参、双端 FastQC）必须短路为空候选。

用法：
    python3 scripts/probe_30_prompts.py                    # 真实 LLM 跑一轮
    python3 scripts/probe_30_prompts.py --repeat 3         # 测稳定性
    python3 scripts/probe_30_prompts.py --force-rule       # 关掉 LLM，只看确定性路径
    python3 scripts/probe_30_prompts.py --only A,B         # 只跑某几组
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NO_CHAIN = {"unsupported", "information", "no_candidate"}


def case(cid, group, prompt, **expect):
    return {"case_id": cid, "group": group, "prompt": prompt, "expect": expect}


# expect 支持的键：
#   status          期望的 selection_status 集合
#   llm_used        planner_metadata.used 期望值
#   candidates      "some" | "none"
#   recommendations "some" | "none"
#   reason          True 表示必须给出无法成链的理由
CASES: List[Dict[str, Any]] = [
    # ---- A. 能力/目录问答：走确定性路径，不调 LLM ----
    case("A1", "A", "你们能做什么？",
         status={"information"}, llm_used=False, candidates="none"),
    case("A2", "A", "有哪些原子工具？",
         status={"information"}, llm_used=False, candidates="none"),
    case("A3", "A", "有哪些流程可以处理 MAF 文件？",
         status={"information"}, llm_used=False, candidates="none"),
    case("A4", "A", "有哪些流程支持单细胞数据？",
         status={"information"}, llm_used=False, candidates="none"),
    case("A5", "A", "目录里有哪些工具能输出 BAM？",
         status={"information"}, llm_used=False, candidates="none"),

    # ---- B. RNA-seq 上游：目录能完整表达，必须给出可执行链 ----
    case("B1", "B", "双端 RNA-seq FASTQ 做完整上游分析。",
         status={"ready"}, candidates="some"),
    case("B2", "B", "我有 paired-end RNA-seq 数据，想得到基因表达计数矩阵。",
         status={"ready"}, candidates="some"),
    case("B3", "B", "RNA-seq 原始数据怎么做质控、比对和表达定量？",
         status={"ready"}, candidates="some"),
    case("B4", "B", "从双端 RNA-seq FASTQ 出发做 STAR 比对，再用 featureCounts 计数。",
         status={"ready"}, candidates="some"),
    case("B5", "B", "完整双端 RNA-seq 上游流程，但去掉 RSEM，只保留 featureCounts 计数。",
         status={"ready"}, candidates="some"),

    # ---- C. WES / WGS ----
    case("C1", "C", "我有双端 WES FASTQ，想做比对并得到排序去重后的 BAM。",
         status={"ready"}, candidates="some"),
    # 配对 WES 走整卡：不拆原子链，而是给出 wes_somatic_pair 的推荐，
    # 并把四个 FASTQ 直接绑定到 tumor_r1/tumor_r2/normal_r1/normal_r2。
    case("C2", "C", "我有 tumor-normal 配对的 WES 双端 FASTQ，想做体细胞突变检测。",
         candidates="none", recommendations="some",
         execution_params={"tumor_r1", "tumor_r2", "normal_r1", "normal_r2"}),
    # 目录边界：单样本 GATK 只支持 tumor-normal 四槽形式
    case("C3", "C", "我只有一个样本的 WES 数据，想直接用 GATK call 变异。",
         status=NO_CHAIN, candidates="none", reason=True),
    # 目录边界：GATK -> BCFtools 的 VCF 及 index 传参当前合同表达不了
    case("C4", "C", "从 WES FASTQ 一路做到过滤并注释后的 VCF，路径要经过 GATK、BCFtools 和 SnpEff。",
         status=NO_CHAIN, candidates="none", reason=True),
    case("C5", "C", "WGS 双端 FASTQ 做 BWA 比对。",
         status={"ready"}, candidates="some"),

    # ---- D. 未原子化的分析需求：保留业务推荐，但不得编出原子链 ----
    case("D1", "D", "我有肝癌 MAF，先做突变景观，再做 TMB 生存分析。",
         status=NO_CHAIN, candidates="none", reason=True),
    case("D2", "D", "用基因表达矩阵和临床表做 WGCNA 共表达网络分析。",
         status=NO_CHAIN, candidates="none", reason=True),
    case("D3", "D", "表达矩阵做差异表达分析，然后做 GO 富集。",
         status=NO_CHAIN, candidates="none", reason=True),
    case("D4", "D", "用临床随访数据画 Kaplan-Meier 生存曲线。",
         status=NO_CHAIN, candidates="none", reason=True),
    case("D5", "D", "单细胞数据做细胞间通讯分析。",
         status=NO_CHAIN, candidates="none", reason=True),
    case("D6", "D", "把原始测序 FASTQ 整理成 GATK 后续分析可用的 uBAM 文件。",
         status=NO_CHAIN, candidates="none", reason=True),

    # ---- E. 输入与方法冲突：recommendations 和 candidates 都必须为空 ----
    case("E1", "E", "我只有 MAF 文件，想用 STAR 做基因组比对。",
         status={"unsupported", "no_candidate"}, candidates="none",
         recommendations="none", reason=True),
    case("E2", "E", "我有 RNA-seq 表达矩阵，想跑 DNA 体细胞变异检测流程。",
         status={"unsupported", "no_candidate"}, candidates="none",
         recommendations="none", reason=True),
    case("E3", "E", "我手上只有临床信息表，想做基因组比对拿到 BAM。",
         status={"unsupported", "no_candidate"}, candidates="none",
         recommendations="none", reason=True),
    case("E4", "E", "用已有的 VCF 文件做 FastQC 测序质量评估。",
         status={"unsupported", "no_candidate"}, candidates="none",
         recommendations="none", reason=True),

    # ---- F. 数据可用性与组学识别：至少要给出对的业务推荐 ----
    # 按 study 反查"这批数据能做什么"目前没有实现：能力问答是目录级的，不接受
    # study 作用域。查询本身也没说明数据类型和分析终点，所以正确行为是拒答并
    # 说明缺什么，而不是猜一个流程出来。
    case("F1", "F", "HRA000021 这个研究的数据可以做哪些分析？",
         status=NO_CHAIN, candidates="none", reason=True),
    case("F2", "F", "我有 10x 单细胞测序的 FASTQ 文件，想生成细胞-基因表达矩阵。",
         recommendations="some"),
    case("F3", "F", "有没有 WES 的 tumor/normal 配对数据可以做体细胞突变分析？",
         recommendations="some"),
    case("F4", "F", "用 bulk RNA-seq 表达矩阵和临床表做免疫浸润分析。",
         recommendations="some"),
    case("F5", "F", "我有比对好的 BAM 和临床数据，想做 CNV 分析。",
         recommendations="some"),
]


def check(result: Dict[str, Any], expect: Dict[str, Any]) -> List[str]:
    problems: List[str] = []
    status = result.get("selection_status")
    candidates = result.get("candidates") or []
    recommendations = result.get("recommendations") or []
    metadata = result.get("planner_metadata") or {}
    extensions = result.get("extensions") or {}

    if "status" in expect and status not in expect["status"]:
        problems.append(f"status={status} 不在期望 {sorted(expect['status'])}")
    if "llm_used" in expect and bool(metadata.get("used")) != expect["llm_used"]:
        problems.append(f"llm_used={metadata.get('used')} 期望 {expect['llm_used']}")
    if expect.get("candidates") == "some" and not candidates:
        problems.append("期望有原子候选链，实际为空")
    if expect.get("candidates") == "none" and candidates:
        problems.append(f"期望无原子候选链，实际有 {len(candidates)} 条")
    if expect.get("recommendations") == "some" and not recommendations:
        problems.append("期望有业务流程推荐，实际为空")
    if expect.get("recommendations") == "none" and recommendations:
        problems.append(
            "期望无业务流程推荐，实际有 "
            + ", ".join(str(item.get("pipeline_id")) for item in recommendations)
        )
    if expect.get("execution_params"):
        bound = set((recommendations[0] or {}).get("execution_params") or {}) if recommendations else set()
        gap = expect["execution_params"] - bound
        if gap:
            problems.append(f"整卡缺少可直接提交的参数绑定: {sorted(gap)}")
        stranded = (recommendations[0] or {}).get("execution_params_missing") if recommendations else None
        if stranded:
            problems.append(
                "整卡存在未解析参数: "
                + ", ".join(str(item.get("param")) for item in stranded)
            )
    if expect.get("reason") and not (
        result.get("unsupported_reason")
        or extensions.get("atomic_candidate_unavailable_reason")
    ):
        problems.append("没有给出无法成链的理由")

    # 契约不变量：无论哪一类，通过的候选都必须校验通过且数据齐全
    for item in candidates:
        if not item.get("validation_ok"):
            problems.append(f"候选 rank{item.get('rank')} validation_ok=False 却被接受")
        if item.get("feasibility_status") != "ready":
            problems.append(
                f"候选 rank{item.get('rank')} feasibility={item.get('feasibility_status')} 却被接受"
            )
    return problems


def summarize(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "selection_status": result.get("selection_status"),
        "candidate_count": result.get("candidate_count"),
        "chains": [
            [step.get("tool_id") for step in (item.get("tool_chain") or [])]
            for item in (result.get("candidates") or [])
        ],
        "recommendations": [
            item.get("pipeline_id") for item in (result.get("recommendations") or [])
        ],
        "llm_used": (result.get("planner_metadata") or {}).get("used"),
        "deterministic_fallback": (result.get("planner_metadata") or {}).get(
            "deterministic_fallback"
        ),
        "reason": (
            result.get("unsupported_reason")
            or (result.get("extensions") or {}).get("atomic_candidate_unavailable_reason")
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--force-rule", action="store_true")
    parser.add_argument("--only", default="", help="逗号分隔的分组，如 A,B")
    parser.add_argument("--output", default="docs/probe_30_prompts_result.json")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.force_rule:
        os.environ["FORCE_RULE"] = "1"

    groups = {value.strip().upper() for value in args.only.split(",") if value.strip()}
    cases = [item for item in CASES if not groups or item["group"] in groups]

    from workflow_composer import WorkflowComposer

    composer = WorkflowComposer()
    records: List[Dict[str, Any]] = []
    verdicts: Dict[str, List[bool]] = collections.defaultdict(list)

    for run in range(1, args.repeat + 1):
        for item in cases:
            started = time.time()
            try:
                result = composer.plan(item["prompt"])
                problems = check(result, item["expect"])
                detail = summarize(result)
            except Exception as exc:  # noqa: BLE001 - a crash is itself a finding
                problems = [f"抛出异常 {type(exc).__name__}: {exc}"]
                detail = {}
            verdicts[item["case_id"]].append(not problems)
            records.append({
                "run": run,
                "case_id": item["case_id"],
                "group": item["group"],
                "prompt": item["prompt"],
                "elapsed_s": round(time.time() - started, 1),
                "passed": not problems,
                "problems": problems,
                **detail,
            })
            mark = "PASS" if not problems else "FAIL"
            print(f"[{run}] {mark} {item['case_id']} {item['prompt'][:34]}")
            for problem in problems:
                print(f"        - {problem}")

    by_group: Dict[str, List[int]] = collections.defaultdict(lambda: [0, 0])
    for item in cases:
        results = verdicts[item["case_id"]]
        by_group[item["group"]][1] += len(results)
        by_group[item["group"]][0] += sum(results)

    print("\n" + "=" * 62)
    labels = {
        "A": "能力问答", "B": "RNA-seq 上游", "C": "WES/WGS",
        "D": "未原子化需求", "E": "输入方法冲突", "F": "数据可用性",
    }
    total_pass = total_all = 0
    for group in sorted(by_group):
        passed, total = by_group[group]
        total_pass += passed
        total_all += total
        print(f"  {group} {labels.get(group, ''):14} {passed}/{total}")
    print(f"  合计 {total_pass}/{total_all}")

    flaky = [cid for cid, values in verdicts.items() if 0 < sum(values) < len(values)]
    if flaky:
        print(f"  不稳定用例: {', '.join(sorted(flaky))}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"repeat": args.repeat, "force_rule": args.force_rule, "records": records},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"  明细 -> {output}")
    return 0 if total_pass == total_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
