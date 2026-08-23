#!/usr/bin/env python3
"""钉住 0821 交付带来的四条 sample 字段口径。

背景：0821 那版 sample 表把若干「研究级别的默认值」覆盖到了「样本级别的事实」上。
坏值不是空、不是乱码——每一格都填满、单看都合理。举个最清楚的例子：HRA001272 的
`M019_LM1_...`（LM=肺转移）、`M021_BM_...`（BM=骨转移）、`M026_AGM_...`（AGM=肾上腺
转移）、`M033_KM_...`（KM=肾转移），全部 698 个样本的 `biospecimen_anatomic_site` 被
统一写成了 `Liver And Intrahepatic Bile Ducts`，`tumor_descriptor` 被统一写成
`Primary`。查回包看不出任何异常，只有拿样本名这种独立信号交叉验证才露馅。

所以这个文件锁四件事，每一条都对应一种「不报错的错」：

* 拿 `tumor_descriptor` / `biospecimen_anatomic_site` 做过滤 —— 会得到填满的、
  看着合理的、错的结果。本仓库目前一处都没用，这里负责让它保持这样。
* `specimen_type` 用等号比 —— 会静默漏掉 486 个分号多值样本。
* `gender` 不归一化 —— `== "Male"` 会静默漏掉 56 个小写样本。
* 分不出原发/转移/复发时回头去读 `tumor_descriptor` 凑答案 —— 见第一条。
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline_router import (  # noqa: E402
    LESION_BY_NAME_CODE,
    UNRELIABLE_SAMPLE_FIELDS,
    _sample_role,
    normalize_gender,
    sample_lesion,
    specimen_tokens,
)


class SpecimenTypeIsMultiValued(unittest.TestCase):
    """0821 新增了 `Organoid;Patient_Solid_Tissue`（486 个，HRA005191/HRA006499）。"""

    def test_semicolon_multi_value_splits_into_tokens(self):
        self.assertEqual(
            specimen_tokens("Organoid;Patient_Solid_Tissue"),
            {"organoid", "patient solid tissue"},
        )

    def test_underscore_and_space_forms_are_the_same_token(self):
        # 0819 清洗把空格换成了下划线，两版取值都还在图里。
        self.assertEqual(
            specimen_tokens("Patient_Solid_Tissue"),
            specimen_tokens("Patient Solid Tissue"),
        )

    def test_role_still_resolves_when_specimen_type_is_multi_valued(self):
        """这条是真正要防的回归：等号比较在这里返回 None，且不报错。

        判不出角色的样本会被 wes_somatic_pair 之类的流程直接跳过，用户看到的是
        「配不出对」，而不是「有 486 个样本没被算进去」。
        """
        role = _sample_role({
            "study_accession": "HRA000071",
            "specimen_type": "Organoid;Patient_Solid_Tissue",
        })
        self.assertEqual(role, "tumor")

    def test_ambiguous_multi_value_refuses_to_guess(self):
        # 两个 token 指向不同角色时必须交白卷，而不是挑一个。
        role = _sample_role({
            "study_accession": "HRA000071",
            "specimen_type": "Blood;Patient_Solid_Tissue",
        })
        self.assertIsNone(role)

    def test_hra000071_blood_and_solid_still_split_correctly(self):
        # 0821 数据 HRA000071 是 Blood 286 / Patient_Solid_Tissue 286，
        # 与样本名 B_ 286 / T_ 286 完全自洽——这个队列的 tissue_type 是修对了的。
        self.assertEqual(
            _sample_role({"study_accession": "HRA000071", "specimen_type": "Blood"}),
            "normal",
        )
        self.assertEqual(
            _sample_role({"study_accession": "HRA000071",
                          "specimen_type": "Patient_Solid_Tissue"}),
            "tumor",
        )


class GenderIsCaseInconsistent(unittest.TestCase):
    """Male 6474 / Female 3931 / male 56 / female 3 / 字面量 missing 1。"""

    def test_case_variants_collapse(self):
        self.assertEqual(normalize_gender("Male"), normalize_gender("male"))
        self.assertEqual(normalize_gender("Female"), normalize_gender("female"))

    def test_literal_missing_is_not_a_third_gender(self):
        # `missing` 是「没这个信息」被写成了字符串。不归一化它会参与分组，
        # 让性别分层分析多出一个不存在的组。
        self.assertEqual(normalize_gender("missing"), "")
        self.assertEqual(normalize_gender(""), "")
        self.assertEqual(normalize_gender(None), "")


class LesionComesFromSampleName(unittest.TestCase):
    """`tumor_descriptor` 被压平后，样本名后缀是唯一还能分原发/转移/复发的信号。"""

    def test_metastasis_codes_resolve(self):
        cases = {
            "M019_LM1_S2010-10889_2": "metastasis_lung",
            "M021_BM_S2011-1_1": "metastasis_bone",
            "M026_AGM_S2012-3_1": "metastasis_adrenal_gland",
            "M033_KM_S2013-7_1": "metastasis_kidney",
            "M040_PT_S2014-9_1": "primary",
            "M041_RT_S2015-2_1": "recurrent",
            "M042_NC_S2016-4_1": "normal_adjacent",
        }
        for name, expected in cases.items():
            with self.subTest(sample_name=name):
                self.assertEqual(
                    sample_lesion({"study_accession": "HRA001272", "sample_name": name}),
                    expected,
                )

    def test_unregistered_study_returns_none_rather_than_guessing(self):
        """别的队列命名习惯不同，硬套会出事。

        BM 在 HRA001272 是 Bone Metastasis，而全库有 1208 个样本的 specimen_type
        就叫 Bone_Marrow。分不出就是分不出。
        """
        self.assertIsNone(
            sample_lesion({"study_accession": "HRA000071", "sample_name": "T_CGGA_1"})
        )
        self.assertIsNone(
            sample_lesion({"study_accession": "HRA001272", "sample_name": "随便什么"})
        )

    def test_registered_codes_do_not_silently_shrink(self):
        # HRA001272 的十一种代码是逐个数出来的（PT/NC/RT + 8 种转移灶）。
        # 哪天有人删掉几行，这里响亮地挂掉，而不是让那些样本静静变成"分不出"。
        self.assertEqual(len(LESION_BY_NAME_CODE["HRA001272"]), 11)


class UnreliableFieldsStayUnused(unittest.TestCase):
    """这两个字段在本仓库一处消费点都没有——这条测试负责让它保持这样。

    它们不是「暂时没用上」，是**没有可信的样本级取值**：
    * `tumor_descriptor` 全库压平成 Primary 8551 / Metastasis 12 / 空 1902，
      HRA001272 原有的 Metastatic 176、Recurrent 28 与 HRA000071 的 106 个
      Recurrent 全部消失；反过来 1476 个 tissue_type=Normal 的样本被填上了 Primary。
    * `biospecimen_anatomic_site` 是研究级原发部位，HRA001272 全部 698 个样本
      都写成 Liver And Intrahepatic Bile Ducts。

    所以拿它们做过滤不会报错，只会得到一个填满的、看着合理的、错的结果。
    要分原发/转移/复发请调 `sample_lesion()`。
    """

    # 只扫真正参与匹配/编排的代码。docs/ 与 outputs/ 下是历史交付快照，
    # scripts/ 下是一次性的数据核对脚本——那些地方读原始字段是本来就该做的事。
    SOURCES = ["pipeline_router.py", "workflow_composer.py", "intent.py",
               "data_matcher", "tests"]

    @staticmethod
    def _docstrings(tree: ast.AST) -> set:
        """收集所有 docstring 节点，扫描时跳过。

        用 AST 而不是逐行 grep，是因为注释和 docstring 里**写明「为什么不用这两个
        字段」正是我们要的**，不该被自己的说明文字判违规。ast 天然丢掉注释，
        docstring 这里显式排除。
        """
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None and isinstance(node.body[0], ast.Expr):
                    found.add(id(node.body[0].value))
        return found

    def _offenders_in(self, path: Path) -> list:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = self._docstrings(tree)
        # 白名单：常量声明本身，以及它的类型注解形式。
        allowed = set()
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            if any(isinstance(t, ast.Name) and t.id == "UNRELIABLE_SAMPLE_FIELDS"
                   for t in targets):
                allowed.update(id(n) for n in ast.walk(node))

        offenders = []
        for node in ast.walk(tree):
            if id(node) in docstrings or id(node) in allowed:
                continue
            text = None
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            elif isinstance(node, ast.Attribute):
                text = node.attr
            elif isinstance(node, ast.Name):
                text = node.id
            if not text:
                continue
            for field in UNRELIABLE_SAMPLE_FIELDS:
                if field in text:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{node.lineno}: 用到了 {field}"
                    )
        return offenders

    def test_no_filtering_on_unreliable_fields(self):
        offenders = []
        for rel in self.SOURCES:
            target = ROOT / rel
            files = sorted(target.rglob("*.py")) if target.is_dir() else [target]
            for path in files:
                if path.name == Path(__file__).name:
                    continue
                offenders.extend(self._offenders_in(path))
        self.assertEqual(
            offenders, [],
            "这两个字段在 0821 数据里没有可信的样本级取值，不能用来过滤或分组。"
            "要分原发/转移/复发请调 pipeline_router.sample_lesion()。\n"
            + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
