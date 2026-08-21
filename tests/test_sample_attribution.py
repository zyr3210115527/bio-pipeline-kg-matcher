"""资产的 null 到底是「本来没有」还是「没查到」——两者必须能分开。

师兄 0821 看富集分析的 plan 时问「数据有的是 null」。查证结果：富集用的那个
表达矩阵在图里确实没有 generated_from、没有 in_sample、run_accession 也是
null，所以那片 null 是真实情况，不是漏查。但当时输出里没有任何东西能说明这
一点——而隔壁 WES 的逐样本 VCF 也是一片 null，原因却完全不同（图里缺血缘边，
本该有）。同样的 null，两种含义，调用方只能一律理解成「数据缺失」。

_sample_attribution 就是用来把这两类分开的。这里锁住它的行为，特别是那条最
要紧的安全性质：**绝不把逐样本文件误标成 cohort_aggregate**，否则真缺口会被
盖成「正常现象」，比不标还糟。

0821 全量交叉验证（35,572 个 T2 逐个跑分类器比对图内血缘）：判成
cohort_aggregate 的 179 个，全部在图里确实没有血缘，零误报。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline_router import _sample_attribution  # noqa: E402


class SampleAttributionTests(unittest.TestCase):

    def test_resolved_sample_is_per_sample(self):
        for record in ({"sample_accession": "HRS1029912"}, {"sample_name": "L0240_Tumor"}):
            got = _sample_attribution(record, "HRR123456_1.fastq.gz")
            self.assertEqual(got["status"], "per_sample", record)
            self.assertEqual(got["note"], "", "有归属就不该再挂解释")

    def test_cohort_matrix_is_aggregate_not_a_gap(self):
        # 师兄那题的原件。队列级矩阵不属于任何单个样本，null 属正常。
        got = _sample_attribution({}, "HRA001272-Genes-TPM-1.0.tsv")
        self.assertEqual(got["status"], "cohort_aggregate")
        self.assertIn("不代表数据缺失", got["note"])

    def test_scrna_cohort_outputs_are_aggregate(self):
        # 文件名里没有任何样本号的队列级产物，同属聚合类。
        for name in ("Cell_Type.tsv", "UMAP_Final_Annotation.jpeg",
                     "FinalAnno_Markers_Top50.csv", "03_sc_obj_final_anno.rds"):
            self.assertEqual(_sample_attribution({}, name)["status"],
                             "cohort_aggregate", name)

    def test_per_sample_file_without_lineage_is_reported_as_a_gap(self):
        # 这条是本文件的重点。这些 VCF 名字里带 HRI*/HRS*，本该定位到样本，
        # 图里却没有 generated_from——必须报成缺口，绝不能划进 cohort_aggregate。
        for name in ("HRI147472.svaba.somatic.indel.vcf",
                     "HRS1029912.indel.vcf.gz",
                     "HRI023383.svaba.somatic.indel.vcf.gz",
                     "HRR980321_2.fastq.gz"):
            got = _sample_attribution({}, name)
            self.assertEqual(got["status"], "attribution_missing", name)
            self.assertIn("缺口", got["note"])

    def test_aggregate_verdict_requires_absence_of_any_sample_token(self):
        # 反向锁死：只要文件名里出现样本/个体号，就不允许判成 cohort_aggregate。
        # 判据一旦退化成「run_accession 为空」，0821 那 3,676 个逐样本 VCF 会被
        # 整批盖成正常现象。
        self.assertNotEqual(
            _sample_attribution({}, "HRA001272-HRI147472-somatic.vcf")["status"],
            "cohort_aggregate")


if __name__ == "__main__":
    unittest.main(verbosity=2)
