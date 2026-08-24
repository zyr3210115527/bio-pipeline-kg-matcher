"""「优先 T2」必须是排序偏好，不能变成把 T1 整层排除的过滤器。

0824 师兄报 de_enrichment 一类新工具的 `clinical_xls` / `meta_xlsx` 一直是
`no_confirmed_path`，问"是知识图谱没更新吗"。查下来图里一直有：20 个研究的
Clinical/MetaInfo 都在，`/hpcdisk1/...` 真实路径、semantic_format 是
CLINICAL_DATA_EXCEL / METADATA_SAMPLE_INFO——只不过它们是 **T1** 节点，只有
HRA001748/HRA005191 额外多一份 T2 副本（也正是回包里唯一能绑上这两个参数的研究）。

挡住它们的是 `_match_files` 的打分：问句一旦没带癌种/格式/strategy 信号
（"我想做deg_trend" 就是这样），所有加分项都不触发，只剩 `source == "T2"` 那个
`+2`。于是 T2 得 2 分活下来，T1 恒为 0，被下面那句 `if score <= 0: continue`
整层丢弃。实测 `_match_files` 返回 35572 条，正好等于 T2 总数，T1 一条没有。

后果不是报错，是**归错责**：`no_confirmed_path` 在本仓的口径是"图里没有路径、
归数据侧"，于是查的人去催数据侧补文件，而文件一直都在。这和 0823 的
`filtered_vcf_index`、0824 的 `_build_combinations` 是同一类——某个"偏好"被写在
了会导致丢弃的位置上，回包看起来完全正常。

所以这里锁的是"T1 不能因为没有加分项而消失"，不是锁具体分值。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline_router as router  # noqa: E402

# 真实形状：Clinical/MetaInfo 是 T1，表达矩阵是 T2，同一个研究。
T1_CLINICAL = {
    "study_accession": "HRA000073",
    "file_name": "HRA000073-Clinical-1.0.xlsx",
    "file_path": "/hpcdisk1/cbb_group/data/HRA000073/HRA000073-Clinical-1.0.xlsx",
    "semantic_format": "CLINICAL_DATA_EXCEL",
    "strategy": "Clinical",
    "t1_id": "HRA000073-Clinical-1.0.xlsx",
    "data_level": "1",
}
T2_EXPR = {
    "study_accession": "HRA000073",
    "file_name": "HRA000073-Genes-FPKM-1.0.tsv",
    "file_path": "/hpcdisk1/cbb_group/data/analysis/HRA000073/HRA000073-Genes-FPKM-1.0.tsv",
    "semantic_format": "TABULAR_BIO_DATA",
    "format": "tsv",
    "strategy": "RNA-Seq",
    "t2_id": "HRA000073-Genes-FPKM-1.0.tsv",
    "data_level": "2",
}


def _matcher():
    """只搭 `_match_files` 用到的那点状态，绕开需要读全量 CSV 的 __init__。"""
    m = object.__new__(router.CsvKGDataMatcher)
    m.t1 = [dict(T1_CLINICAL)]
    m.t2 = [dict(T2_EXPR)]
    m.study_by_id = {}
    m.project_by_study = {}
    # `_file_record` 会走样本归属索引；这里只验打分与角色，给空表 / 空目录即可。
    m.sample = []
    m.individual = []
    m.study = []
    m.relation_dir = Path(__file__).resolve().parent / "_no_such_relations"
    return m


class T1SurvivesSignallessQueryTests(unittest.TestCase):
    def _match(self):
        # 没有癌种、没有格式、没有 strategy、没有词——"我想做deg_trend" 这类问句
        # 在 rule 模式下解析出来就是这个样子，所有加分项都不触发。
        return _matcher()._match_files(
            allowed_studies=None,
            strategies=set(),
            formats=set(),
            terms=set(),
            pipeline_ids=["de_enrichment"],
            limit=100,
            intent={"query_text": "我想做deg_trend"},
        )

    def test_t1_clinical_is_not_dropped_when_nothing_scores(self):
        """本轮的原点：问句没信号时 T1 不能整层消失。

        这条挂了就说明 `no_confirmed_path` 又在为图里明明存在的文件背锅——
        查的人会被指去催数据侧，而文件一直都在。
        """
        names = [f.get("files") for f in self._match()]
        self.assertIn(
            T1_CLINICAL["file_name"], names,
            "T1 的 Clinical 文件被 _match_files 丢掉了。它在图里有真实路径，"
            f"丢掉之后 clinical_xls 会报 no_confirmed_path（=图里没有、归数据侧），"
            f"实际是被打分挡的。返回的是：{names}",
        )

    def test_t2_still_outranks_t1(self):
        """修法是给 T1 一个低于 T2 的底分，不是把偏好取消。

        真改成同分（或 T1 反超），这条会挂——"优先使用处理后的 T2 数据"
        仍然要成立，只是降级成排序而不是排除。
        """
        names = [f.get("files") for f in self._match()]
        self.assertEqual(
            names[0], T2_EXPR["file_name"],
            f"T2 不再排在 T1 前面，优先级偏好丢了：{names}",
        )

    def test_clinical_role_survives_the_record_conversion(self):
        """角色识别要落在转换后的记录上——下游 `_role_diverse_selection` 用的是它。

        `_file_record` 换了字段名（file_name -> files），角色判别只要跟着漂，
        clinical 就会退化成 `other`，而 `other` 是被显式排除出候选的。
        """
        record = [f for f in self._match() if f.get("files") == T1_CLINICAL["file_name"]][0]
        self.assertEqual(router._role_of_file(record), "clinical")
        self.assertTrue(
            str(record.get("file_path") or "").startswith("/"),
            f"路径没带过来，下游会当成不可确认路径：{record.get('file_path')!r}",
        )


if __name__ == "__main__":
    unittest.main()
