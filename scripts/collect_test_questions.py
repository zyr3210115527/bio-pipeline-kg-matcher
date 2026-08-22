#!/usr/bin/env python3
"""把四套探针 + 单元测试里的所有测试问题汇成一份清单，写到 docs/graph0822/。

为什么要有这个脚本，而不是手抄一份 JSON：题目会改（0822 就改了 G04-G07 的期望、
新增了一整套点名工具替换的用例）。手抄的清单从写下那天起就开始过期，而过期的清单
比没有清单更糟——它看着像"全部测试问题"，实际漏掉的正是最新加的那批。

所以这份清单是**从题目源文件导出来**的：直接 import 各探针模块的 CASES，题目改了
重跑一次就同步。导出的每条都带上原始期望值，这样看清单的人不用回去翻代码就知道
每题判的是什么。

用法：
    python3 scripts/collect_test_questions.py
    python3 scripts/collect_test_questions.py --output docs/graph0822/all_test_questions.json

注意：本脚本只**读题**，不跑题，因此不需要图谱和 LLM。各题的实际跑分在同目录的
probe_*.json 里。
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

# (模块名, 这套题在问什么, 判什么算过)
PROBE_MODULES = [
    (
        "probe_30_prompts",
        "基础能力面：能做什么、怎么问、缺数据怎么答",
        "按 expect 里声明的 status/推荐/理由逐条判",
    ),
    (
        "probe_robustness",
        "鲁棒性：模糊表述、同义改写、脏输入、越界要求、注入尝试",
        "同一语义的不同问法必须给同一类结论；越界要求必须拒绝",
    ),
    (
        "probe_privacy_and_kind",
        "隐私与问题类型：病人年龄/姓名等个人数据，以及与生信无关的闲聊",
        "涉及个人隐私字段一律拒绝；无关问题不许硬套流程",
    ),
    (
        "probe_graph_grounded",
        "图谱实证：期望值全部先查图再写，正反两面都能真判",
        "有这个模态必须绑到数据；没有必须说没有，且不许拿别的模态顶上",
    ),
]


def _jsonable(value: Any) -> Any:
    """期望值里有几处写成了 set（比如"落在这几个 status 之一"）。

    set 不能直接 json.dumps，但也不能为了能序列化就把它改成 list——题目源文件里
    用 set 是有道理的（判的是"属于其中之一"，顺序无关）。所以只在导出这一层排序
    转成 list，源文件不动。
    """
    if isinstance(value, set):
        return sorted(str(v) for v in value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _from_probe(module_name: str) -> List[Dict[str, Any]]:
    module = importlib.import_module(module_name)
    out: List[Dict[str, Any]] = []
    for item in module.CASES:
        out.append(
            {
                "case_id": item["case_id"],
                "group": item.get("group"),
                # probe_robustness 里有几条题面是 list（多轮/多条一起问），
                # 原样保留，别为了"统一成字符串"把结构改掉。
                "prompt": _jsonable(item["prompt"]),
                "expect": _jsonable(item.get("expect") or {}),
            }
        )
    return out


def _from_named_tool_tests() -> List[Dict[str, Any]]:
    """单元测试里的题也是题，不能因为它在 tests/ 下就漏掉。

    这套是 0822 查出「点名了目录里没有的工具，却拿同类工具顶替」之后加的，
    十条题分两半：五条必须拒答，五条必须照常出链（防止收紧判据时连坐）。
    """
    module = importlib.import_module("test_named_tool_substitution")
    out: List[Dict[str, Any]] = []
    for case_id, prompt, named, forbidden in module.NAMED_ABSENT_TOOL_CASES:
        out.append(
            {
                "case_id": f"NT-{case_id}",
                "group": "NT-拒答",
                "prompt": prompt,
                "expect": {
                    "refuse": True,
                    "named_absent_tool": named,
                    "forbidden_in_chain": forbidden,
                    "note": f"用户点名 {named}，目录里没有；不许拿 {forbidden} 顶替，"
                            "也不许推荐内置该工具的业务流程",
                },
            }
        )
    for case_id, prompt in module.STILL_MUST_PLAN_CASES:
        out.append(
            {
                "case_id": f"NT-{case_id}",
                "group": "NT-仍须出链",
                "prompt": prompt,
                "expect": {
                    "status": "ready",
                    "note": "收紧「点名工具」判据时的连坐检查：该给链的仍然要给链",
                },
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="docs/graph0822/all_test_questions.json",
        help="清单写到这个文件",
    )
    args = parser.parse_args()

    suites: List[Dict[str, Any]] = []
    for module_name, asks, judges in PROBE_MODULES:
        cases = _from_probe(module_name)
        suites.append(
            {
                "suite": module_name,
                "source": f"scripts/{module_name}.py",
                "asks": asks,
                "judges": judges,
                "case_count": len(cases),
                "cases": cases,
            }
        )

    named = _from_named_tool_tests()
    suites.append(
        {
            "suite": "test_named_tool_substitution",
            "source": "tests/test_named_tool_substitution.py",
            "asks": "用户逐字点名目录里没有的工具（Salmon/HISAT2/Kallisto/Bowtie2）",
            "judges": "必须拒答并指名道姓说缺哪个工具；链里不许出现被要求换掉的工具",
            "case_count": len(named),
            "cases": named,
        }
    )

    total = sum(s["case_count"] for s in suites)
    payload = {
        "graph": {
            "snapshot": "0822",
            "nodes": 80679,
            "relationships": 352468,
            "labels": 11,
            "relationship_types": 14,
            "tools": 51,
        },
        "total_questions": total,
        "suites": suites,
    }

    path = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    for suite in suites:
        print(f"  {suite['suite']:<28} {suite['case_count']:>3} 题")
    print(f"  {'合计':<26} {total:>3} 题")
    print(f"清单已写入 {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
