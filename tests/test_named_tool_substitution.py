"""用户点名了目录里没有的工具时，不许拿同类工具顶替。

0822 从 `test_atomic_unsupported_and_capability_routing` 那条失败查出来的。原始症状：

    问：把 RNA-seq 标准流程中的 RSEM 换成 Salmon
    答：selection_status=ready，链 = fastp -> star -> **rsem** -> samtools -> featurecounts

用户要求把 RSEM 换掉，回包里 RSEM 还在，而且标 ready、unsupported_reason 为 null。
链本身完全合法（工具都在目录里、NEXT 边都对、终产物也确实是表达矩阵），校验器一条
都拦不住，光看回包发现不了——这是这个项目反复出现的那类错：**错得像对**。
确定性复现 6/6，同类还有「用 HISAT2 代替 STAR」拿到 star、「用 Salmon 做定量」拿到 rsem。

根因有两层，都是"规则盖过 LLM"：

1. 提示词第 6 条的硬约束触发词只列了"只要/不要/不做/不能修改/已有/只有"，不含
   "换成/代替/改用"；第 8 条只在**终产物**不可达时才清空 candidates，而表达矩阵经
   RSEM 是可达的。于是规划器判 ready 并不算违规——补了第 6b 条。
2. 更要命的是第二层：补完提示词后规划器**判对了**（analysis.checks 原话"用户逐字
   点名 HISAT2，目录无该工具，按硬约束清空 candidates"，candidates 交空），但
   `_top3_llm_decision` 里的确定性回退凭关键词（命中 rna-seq、没命中 maf/vcf/wes）
   把标准链塞了回去，把一次正确的拒答改写成了 ready。同一层还有
   `_build_recommendations` 的确定性推荐规则，把规划器主动清掉的 rnaseq_singletask
   （内置 STAR/RSEM，正是用户要排除的）又补了回来，并把顶层状态从 unsupported 顶成
   information。

所以这里锁的不只是"别返回错链"，而是**规划器主动拒答时，确定性规则不得改写它**。
第二条断言（拒答时 candidates 必须为空）在只修提示词、不修回退的版本上会挂——那正
是这个文件要防的回归。

本套件要连图谱 + LLM，两者缺一断言都不成立，缺时 skip 并说明跳过不等于通过。
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph_gate import require_graph_catalog  # noqa: E402

REFUSAL = {"unsupported", "no_candidate"}

# (case_id, 提问, 点名但目录里没有的工具, 不许出现在链里的同类工具)
NAMED_ABSENT_TOOL_CASES = [
    ("A", "把 RNA-seq 标准流程中的 RSEM 换成 Salmon", "salmon", "rsem"),
    ("B", "RNA-seq 上游分析，用 HISAT2 代替 STAR 做比对", "hisat2", "star"),
    ("C", "我要用 Kallisto 做转录本定量，不要用别的工具", "kallisto", "rsem"),
    ("D", "用 Salmon 对双端 RNA-seq FASTQ 做转录本定量", "salmon", "rsem"),
    ("E", "bulk RNA-seq 流程，比对步骤改用 Bowtie2", "bowtie2", "star"),
]

# 这几条是两处确定性回退当初要治的抖动，必须继续给出链。收紧判据时最容易连坐的就是
# 它们：一旦回退被关死，标准 RNA-seq 上游会在 ready 和 information 之间来回跳。
STILL_MUST_PLAN_CASES = [
    ("F", "把 RNA-seq 标准流程中的 fastp 换成 trim_galore"),
    ("M", "双端 RNA-seq FASTQ 做上游分析并出 MultiQC 汇总报告"),
    ("R", "对双端 RNA-seq FASTQ 做完整上游分析得到表达矩阵"),
    ("R2", "双端 bulk RNA-seq FASTQ 做质控比对和表达定量"),
    ("R3", "我有一批 RNA-seq 的 fastq，想跑完整上游拿到表达矩阵"),
]


def _chain_tool_ids(candidate):
    extensions = candidate.get("extensions") or {}
    ids = extensions.get("internal_tool_ids")
    if not ids:
        ids = [
            step.get("tool_id")
            for step in candidate.get("tool_chain") or []
        ]
    return [str(tool_id or "").strip().lower() for tool_id in ids]


class NamedAbsentToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_graph_catalog()
        if os.environ.get("LLM_MODE", "api").strip().lower() == "off":
            raise unittest.SkipTest(
                "本套件断言的是规划器的拒答判断，LLM 关闭时无从产生该判断；"
                "跳过**不等于**通过。"
            )
        from workflow_composer import WorkflowComposer

        cls.composer = WorkflowComposer()
        catalog = cls.composer.registered_methods
        cls.atomic = {str(name).strip().lower() for name in catalog.methods}
        cls.plans = {
            case_id: cls.composer.plan(prompt)
            for case_id, prompt, _, _ in NAMED_ABSENT_TOOL_CASES
        }

    def test_the_named_tools_really_are_absent_from_the_catalog(self):
        """前提自检：这些工具真不在目录里，题目才成立。

        哪天 Salmon 真被原子化了，这个文件的期望就得整体改写——那时应该在这里挂掉，
        而不是让下面几条断言继续以"必须拒答"的名义把一个已经支持的需求判成不支持。
        """
        for _, _, named, _ in NAMED_ABSENT_TOOL_CASES:
            with self.subTest(tool=named):
                self.assertNotIn(
                    named,
                    self.atomic,
                    f"`{named}` 现在已经在原子目录里了（共 {len(self.atomic)} 个）。"
                    "本套件的全部期望建立在它不存在之上，请连同用例一起改写。",
                )

    def test_chain_never_contains_the_tool_the_user_asked_to_replace(self):
        """最直接的那条：别把用户要求换掉的工具原样端回去。"""
        for case_id, prompt, named, forbidden in NAMED_ABSENT_TOOL_CASES:
            with self.subTest(case=case_id, prompt=prompt):
                for candidate in self.plans[case_id].get("candidates") or []:
                    chain = _chain_tool_ids(candidate)
                    self.assertNotIn(
                        forbidden,
                        chain,
                        f"用户点名 {named}，返回的链里却是 {forbidden}：{chain}。"
                        "工具、NEXT 边、终产物全合法，校验器拦不住，"
                        "只有这条断言看得见。",
                    )

    def test_planner_refusal_is_not_rewritten_into_a_ready_plan(self):
        """规划器主动拒答，确定性回退不得把它改写成 ready。

        这条才是根因所在。只补提示词、不收紧 `_top3_llm_decision` 里那句
        `if not accepted and self._eligible_rnaseq_fallback(...)` 的版本上，规划器
        交的是空 candidates，回退照样按关键词塞进标准链，这条会挂而上一条不一定挂
        （回退塞的链里恰好含 rsem 时才挂）。判据已收紧为 `normalized and not
        accepted`——只有规划器**交了链、但全被校验拦下**才回退。
        """
        for case_id, prompt, named, _ in NAMED_ABSENT_TOOL_CASES:
            with self.subTest(case=case_id, prompt=prompt):
                result = self.plans[case_id]
                status = result.get("selection_status")
                self.assertIn(
                    status,
                    REFUSAL,
                    f"点名了目录里没有的 {named}，却给出 selection_status={status}；"
                    f"candidates={result.get('candidate_count')} "
                    f"recommendations="
                    f"{[r.get('pipeline_id') for r in result.get('recommendations') or []]}。"
                    "确定性规则又盖过规划器的判断了。",
                )
                self.assertEqual(
                    result.get("candidates") or [],
                    [],
                    f"{case_id} 判了拒答却仍带着候选链，回包自相矛盾。",
                )

    def test_refusal_says_which_tool_is_missing(self):
        """拒答必须给出理由，且指名道姓。

        "无法生成候选链"这种话等于没说——用户要知道的是"你点的 Salmon 我这儿没有"，
        才知道该换工具还是换需求。理由可能落在顶层 unsupported_reason，也可能落在
        extensions.atomic_candidate_unavailable_reason（有业务推荐时顶层会被置空），
        两处都认。
        """
        for case_id, prompt, named, _ in NAMED_ABSENT_TOOL_CASES:
            with self.subTest(case=case_id, prompt=prompt):
                result = self.plans[case_id]
                extensions = result.get("extensions") or {}
                reason = (
                    result.get("unsupported_reason")
                    or extensions.get("atomic_candidate_unavailable_reason")
                    or ""
                )
                self.assertTrue(
                    str(reason).strip(),
                    f"{case_id} 拒答了但一个字的理由都没有。",
                )
                self.assertIn(
                    named,
                    str(reason).lower(),
                    f"{case_id} 的理由里没提用户点名的 {named}：{reason}",
                )

    def test_recommendation_does_not_reintroduce_the_excluded_tool(self):
        """业务推荐同样不许把用户排除掉的那套流程端回来。

        rnaseq_singletask 内置 STAR/RSEM。用户明说要换掉 STAR，再把这条流程作为
        "推荐"给出去，等于绕过约束换个字段交付；而且它一旦非空，顶层状态就会从
        unsupported 变成 information——"做不了"变成"给你推荐"。
        """
        for case_id, prompt, named, _ in NAMED_ABSENT_TOOL_CASES:
            with self.subTest(case=case_id, prompt=prompt):
                pipelines = [
                    r.get("pipeline_id")
                    for r in self.plans[case_id].get("recommendations") or []
                ]
                self.assertNotIn(
                    "rnaseq_singletask",
                    pipelines,
                    f"用户点名 {named} 要替换掉内置工具，却仍推荐 rnaseq_singletask"
                    f"（该流程正是用 STAR/RSEM 跑的）：{pipelines}",
                )


class DeterministicFallbackStillWorksTests(unittest.TestCase):
    """收紧回退判据的连坐检查。

    上面那几条断言只要把两处确定性回退整个删掉就能全绿——但那会让标准 bulk RNA-seq
    上游重新开始在 ready / information 之间抖动，也就是回退当初要治的毛病。所以必须
    同时钉住反面：该给链的仍然要给链。
    """

    @classmethod
    def setUpClass(cls):
        require_graph_catalog()
        if os.environ.get("LLM_MODE", "api").strip().lower() == "off":
            raise unittest.SkipTest("LLM 关闭；跳过**不等于**通过。")
        from workflow_composer import WorkflowComposer

        cls.composer = WorkflowComposer()

    def test_ordinary_rnaseq_upstream_still_plans(self):
        for case_id, prompt in STILL_MUST_PLAN_CASES:
            with self.subTest(case=case_id, prompt=prompt):
                result = self.composer.plan(prompt)
                self.assertEqual(
                    result.get("selection_status"),
                    "ready",
                    f"{case_id} 不该受「点名工具」那条收紧影响，"
                    f"实际 status={result.get('selection_status')} "
                    f"理由={result.get('unsupported_reason')}",
                )
                self.assertTrue(
                    result.get("candidates"),
                    f"{case_id} 该给出可执行链却给了空。",
                )

    def test_swapping_to_a_registered_tool_is_honoured(self):
        """换成目录里**有**的工具时，必须照新工具生成，不能反过来一律拒答。

        这是第 6b 条最容易被写过头的地方：把"点名工具"一律当成拒答理由，
        fastp 换 trim_galore 这种完全合法的替换也会被误伤。
        """
        result = self.composer.plan("把 RNA-seq 标准流程中的 fastp 换成 trim_galore")
        self.assertEqual(result.get("selection_status"), "ready", result.get("unsupported_reason"))
        chains = [_chain_tool_ids(c) for c in result.get("candidates") or []]
        self.assertTrue(chains, "换成目录里有的工具，却一条链都没给")


if __name__ == "__main__":
    unittest.main()
