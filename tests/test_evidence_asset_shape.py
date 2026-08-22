"""recommendations[].data.assets[] 的形状。

背景：v2 里 candidates[].assets 用 asset_id / role / path（schema 里是 required），
而证据链这边一直用内部形状 file_id / input_role / file_path。schema 对本字段写的是
自由对象，所以两套并存**不算违约**——0822 一开始我把它记成"合同违规"，是记错了。

真实的问题是另一回事：消费方照着 candidates 的写法去读 `path`，拿到的是 None，
不报错、不告警，静静地当成"这个文件没有路径"。这套用例锁的就是加性补齐后的三个
规范键，以及"角色解析不出来时不许拿空串糊过去"。

全部离线，不连图谱、不调 LLM，所以任何环境都必须跑过——不加 graph_gate。
"""

import pathlib
import unittest

from workflow_composer import _evidence_asset

REPO = pathlib.Path(__file__).resolve().parent.parent

# 组合匹配那条路给出的典型一行：有 file_path / file_id，没有 input_role。
COMBO_ITEM = {
    "files": "HRA001272-Genes-FPKM-1.0.tsv",
    "file_id": "HRA001272-Genes-FPKM-1.0.tsv",
    "file_name": "HRA001272-Genes-FPKM-1.0.tsv",
    "file_path": "/hpcdisk1/data/HRA001272/RNAseq/HRA001272-Genes-FPKM-1.0.tsv",
    "format": "tsv",
    "strategy": "bulk_RNA",
    "study_accession": "HRA001272",
    "match_reason": "格式匹配 tsv",
}


class CanonicalKeysTests(unittest.TestCase):
    def test_three_canonical_keys_are_populated(self):
        asset = _evidence_asset(COMBO_ITEM, lambda item: "expression_abundance")
        self.assertEqual(asset["asset_id"], "HRA001272-Genes-FPKM-1.0.tsv")
        self.assertEqual(asset["path"], COMBO_ITEM["file_path"])
        self.assertEqual(asset["role"], "expression_abundance")

    def test_existing_internal_keys_are_untouched(self):
        # 加性修复的全部意义就在这：老调用方读 file_path / file_id 必须原样能读到。
        asset = _evidence_asset(COMBO_ITEM, lambda item: "expression_abundance")
        for key, value in COMBO_ITEM.items():
            self.assertEqual(asset[key], value, f"{key} 被改动了")
        self.assertEqual(asset["graph_status"], "available")
        self.assertEqual(asset["name"], COMBO_ITEM["files"])

    def test_input_role_wins_when_present(self):
        # 引用资产那条路已经算过 input_role，不能被 role_of 覆盖掉。
        item = {**COMBO_ITEM, "input_role": "somatic_maf"}
        asset = _evidence_asset(item, lambda _: "expression_abundance")
        self.assertEqual(asset["role"], "somatic_maf")

    def test_role_is_derived_rather_than_left_blank(self):
        # 这条是这个文件的主张所在：组合匹配的 item 没有 input_role，早先的写法
        # 直接落成 role=""，把"没解析出角色"伪装成"角色是空的"。
        calls = []

        def role_of(item):
            calls.append(item)
            return "expression_abundance"

        asset = _evidence_asset(COMBO_ITEM, role_of)
        self.assertEqual(len(calls), 1, "没有解析角色就直接给了空串")
        self.assertEqual(asset["role"], "expression_abundance")

    def test_broken_role_resolver_degrades_to_blank_not_crash(self):
        # 角色解析炸了不该让整条推荐挂掉——但也不许编一个角色出来。
        def boom(item):
            raise KeyError("strategy")

        asset = _evidence_asset(COMBO_ITEM, boom)
        self.assertEqual(asset["role"], "")
        self.assertEqual(asset["path"], COMBO_ITEM["file_path"])


class NoSiteKeepsTheOldShapeTests(unittest.TestCase):
    """源码级检查：新增第四个出口时别再手写一遍旧形状。

    断言代码文本确实脆（改个空格就得跟着改），但这个 bug 的复发方式就是"某处又
    照着旧写法拼了一个 dict"，运行时用例覆盖不到还没写出来的那个出口。
    """

    def test_no_inline_available_asset_dicts_remain(self):
        for name in ("workflow_composer.py", "pipeline_router.py"):
            text = (REPO / name).read_text(encoding="utf-8")
            self.assertNotIn(
                '"graph_status": "available", **item',
                text,
                f"{name} 里还有手写的旧 asset 形状，请改走 _evidence_asset",
            )


if __name__ == "__main__":
    unittest.main()
