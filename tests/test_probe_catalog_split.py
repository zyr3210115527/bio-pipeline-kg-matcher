"""probe_30_prompts 的"这条失败算不算数"分类器。

0822 图谱断线那轮，探针报 21/30，九条 FAIL 一条真缺陷都不是：ready 要有原子候选链、
execution_params 要读 method.inputs 的槽位、连"期望有业务流程推荐"都得看目录（本地
benchmark 只有 14 条 pipeline，cnvkit_cnv_clinical 只存在于图谱里，目录一空菜单上就
没有 CNV 这项）。把它们计成失败，等于每次断网都伪造九个缺陷。

但这个分类器危险的方向是**另一边**：多判一条"无从判定"，就是把一个真缺陷永久藏起来，
而且藏得悄无声息——记分牌照样全绿。所以下面正反两个方向都锁死，反向那组尤其不能松。

纯离线，不连图谱、不调 LLM。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from probe_30_prompts import split_by_catalog


class CatalogDependentTests(unittest.TestCase):
    """目录一空就无从判定的那几类。"""

    def test_missing_atomic_chain_is_unverifiable(self):
        real, skipped = split_by_catalog(["期望有原子候选链，实际为空"])
        self.assertEqual(real, [])
        self.assertEqual(len(skipped), 1)

    def test_expected_ready_but_got_something_else_is_unverifiable(self):
        real, skipped = split_by_catalog(["status=information 不在期望 ['ready']"])
        self.assertEqual(real, [])
        self.assertEqual(len(skipped), 1)

    def test_param_binding_needs_slots_from_the_catalog(self):
        real, skipped = split_by_catalog([
            "整卡缺少可直接提交的参数绑定: ['normal_r1', 'tumor_r1']",
            "整卡存在未解析参数: None",
        ])
        self.assertEqual(real, [])
        self.assertEqual(len(skipped), 2)

    def test_missing_pipeline_recommendation_is_unverifiable(self):
        # F5 的形状：cnvkit_cnv_clinical 只在图谱里，离线菜单上压根没有 CNV。
        real, skipped = split_by_catalog(["期望有业务流程推荐，实际为空"])
        self.assertEqual(real, [])
        self.assertEqual(len(skipped), 1)


class StillCountsWithoutCatalogTests(unittest.TestCase):
    """这组才是重点：目录空**不能**成为放过这些的理由。"""

    def test_fabricated_chain_still_counts(self):
        # 目录是空的却端出了候选链——这只可能是编的，比任何时候都该报。
        real, skipped = split_by_catalog(["期望无原子候选链，实际有 3 条"])
        self.assertEqual(skipped, [])
        self.assertEqual(len(real), 1)

    def test_recommending_when_it_should_refuse_still_counts(self):
        real, skipped = split_by_catalog(["期望无业务流程推荐，实际有 wes_somatic_pair"])
        self.assertEqual(skipped, [])
        self.assertEqual(len(real), 1)

    def test_refusing_without_a_reason_still_counts(self):
        # 拒答不给理由和目录有没有连上无关，永远是缺陷。
        real, skipped = split_by_catalog(["没有给出无法成链的理由"])
        self.assertEqual(skipped, [])
        self.assertEqual(len(real), 1)

    def test_contract_invariants_still_count(self):
        real, skipped = split_by_catalog([
            "候选 rank1 validation_ok=False 却被接受",
            "候选 rank2 feasibility=missing_data 却被接受",
        ])
        self.assertEqual(skipped, [])
        self.assertEqual(len(real), 2)

    def test_actual_ready_against_a_non_ready_expectation_still_counts(self):
        # 实际给出了 ready，说明它确实产出了候选链，目录为空解释不了这件事。
        # 之所以安全，是因为 'ready' 只会带引号出现在 sorted(expect) 那半边——
        # 这条锁的就是别哪天把匹配放宽成裸 "ready"，一放宽这个缺陷就被吞掉。
        real, skipped = split_by_catalog(["status=ready 不在期望 ['unsupported']"])
        self.assertEqual(skipped, [])
        self.assertEqual(len(real), 1)

    def test_crash_still_counts(self):
        real, skipped = split_by_catalog(["抛出异常 KeyError: 'inputs'"])
        self.assertEqual(skipped, [])
        self.assertEqual(len(real), 1)

    def test_mixed_case_keeps_the_real_one(self):
        # 一条用例同时有两种违反时，必须仍然判 FAIL，不能因为掺了个跳过项就整条放行。
        real, skipped = split_by_catalog([
            "期望有原子候选链，实际为空",
            "没有给出无法成链的理由",
        ])
        self.assertEqual(real, ["没有给出无法成链的理由"])
        self.assertEqual(len(skipped), 1)


if __name__ == "__main__":
    unittest.main()
