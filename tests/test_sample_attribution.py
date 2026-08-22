"""样本级字段为空 ≠ 查不到——四级归属解析的回归。

来历：0821 师兄看富集分析的 plan 时问「数据有的是 null」。我第一版判成"队列级
矩阵本来就不属于任何样本，空着正常"，并把另一批文件标成"真缺口、不要猜"。
**两个结论都错。** 师兄的原话：图谱里是有 sample 的，这个文件对应的是 study
数据，要 run 和 sample 编号就从 study 下面对应到 individual 再对应到 sample-run。

按这条路查完，全量 35,572 个 T2 **没有一个是查不到归属的**，只有归属在哪一层
的区别。所以这里锁的不再是"标签贴得对不对"，而是"编号有没有真的解析出来"。

这些断言全部离线跑（只读 data/0812 的 CSV），但每个数字都在 0821 的现网图谱上
交叉验证过：
    图谱 MATCH (t:T2) 总数 ............................. 35,572  ✓
    有 generated_from 且能走到 sample ................. 31,313  ✓
    无血缘、文件名带 HRR 号 ..............................  404  ✓
    无血缘、文件名无任何编号 .............................  179  ✓
    HRA001272 → 206 individual → 698 sample ......... 374 bulk_RNA + 324 WES  ✓
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline_router import CsvKGDataMatcher  # noqa: E402

ENRICHMENT_MATRIX = "HRA001272-Genes-TPM-1.0.tsv"


class SampleAttributionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.matcher = CsvKGDataMatcher()
        if not cls.matcher.t2:
            raise unittest.SkipTest(
                f"{cls.matcher.csv_dir} 下没有 T2，跳过（不等于通过）")
        cls.by_name = {}
        for row in cls.matcher.t2:
            cls.by_name.setdefault(row.get("file_name"), row)

    def _record(self, file_name):
        row = self.by_name.get(file_name)
        self.assertIsNotNone(row, f"{file_name} 不在 T2 里，用例前提已失效")
        return self.matcher._file_record("T2", row, "test")

    def test_default_data_dir_is_the_current_generation(self):
        # 默认目录一旦退回 data/csv，下面所有用例都会因为 T2 只有 86 行而失去意义，
        # 且线上会安静地选错矩阵。这条先失败，好过后面一片莫名其妙的报错。
        self.assertGreater(len(self.matcher.t2), 30000,
                           f"T2 只有 {len(self.matcher.t2)} 行，默认 CSV_DIR 可能退回了 data/csv")

    def test_enrichment_matrix_resolves_to_its_cohort(self):
        # 师兄那题的原件。它自身没有单样本归属是事实，但队列成员必须给得出来——
        # 这正是"图谱里是有 sample 的"那句话要求的。
        rec = self._record(ENRICHMENT_MATRIX)
        self.assertEqual(rec["sample_attribution"], "study_cohort")
        self.assertEqual(rec["sample_attribution_via"], "study_membership")
        self.assertGreater(rec["cohort_sample_count"], 0,
                           "队列级文件必须给出成员样本，否则和'查不到'没有区别")
        self.assertTrue(all(s.startswith("HRS") for s in rec["cohort_samples"]))

    def test_cohort_membership_is_filtered_by_strategy(self):
        # HRA001272 底下 374 个 bulk_RNA 和 324 个 WES 混在一起。不按 strategy 过滤，
        # 就会把 WES 样本挂到 RNA 表达矩阵上——比不给还糟，因为它看起来是对的。
        rec = self._record(ENRICHMENT_MATRIX)
        self.assertEqual(rec["strategy"], "bulk_RNA")
        self.assertEqual(rec["cohort_sample_count"], 374,
                         "应只含 bulk_RNA 样本；698 说明 strategy 过滤失效")
        wrong = {r.get("sample_accession") for r in self.matcher.sample
                 if r.get("study_accession") == "HRA001272"
                 and (r.get("strategy") or "") != "bulk_RNA"}
        self.assertEqual(set(rec["cohort_samples"]) & wrong, set(),
                         "队列成员里混进了非 bulk_RNA 样本")

    def test_lineage_edge_fills_in_the_identifiers(self):
        # 这层是"解析"而不只是"标注"的证据：编号必须真的被填回资产。
        rec = self._record("HRR1402616.BQSR.bam")
        self.assertEqual(rec["sample_attribution"], "sample")
        self.assertEqual(rec["sample_attribution_via"], "lineage_edge")
        for field in ("sample_id", "run_accession", "individual_accession"):
            self.assertTrue(rec[field], f"{field} 仍为空，等于没解析")
        self.assertEqual(rec["run_accession"], "HRR1402616")

    def test_somatic_vcf_is_individual_level_not_a_gap(self):
        # 第一版把这类标成 attribution_missing（"真缺口、不要猜"）。错了：体细胞
        # 突变本就按个体出，且个体号就在文件名里，查得到。
        rec = self._record("HRI023383.svaba.somatic.indel.vcf.gz")
        self.assertEqual(rec["sample_attribution"], "individual")
        self.assertEqual(rec["individual_accession"], "HRI023383")
        self.assertGreater(rec["cohort_sample_count"], 0)

    def test_no_file_is_left_unresolved(self):
        # 全量兜底。这条一旦失败，说明有文件掉出了四级阶梯，必须查清是哪一类，
        # 而不是把 unresolved 当成可接受的结果默许下去。
        stuck = [r.get("file_name") for r in self.matcher.t2
                 if self.matcher._resolve_attribution(r, r.get("file_name"))["level"]
                 == "unresolved"]
        self.assertEqual(stuck[:5], [], f"{len(stuck)} 个文件无法解析归属")

    def test_multi_sample_levels_never_fake_single_sample_precision(self):
        # 安全方向：个体级/队列级解析出的是一组样本，绝不能挑第一个填进 sample_id
        # 冒充精确归属。调用方看到 sample_id 有值就会当成单样本来用。
        for row in self.matcher.t2:
            attribution = self.matcher._resolve_attribution(row, row.get("file_name"))
            if len(attribution["samples"]) > 1:
                rec = self.matcher._file_record("T2", row, "test")
                self.assertIsNone(rec["sample_id"],
                                  f"{row.get('file_name')} 有 "
                                  f"{len(attribution['samples'])} 个候选样本，"
                                  f"sample_id 却被填成 {rec['sample_id']}")
                return
        self.skipTest("本批数据里没有多样本归属的文件，该性质未被覆盖")

    def test_lineage_wins_over_filename_when_both_exist(self):
        # 血缘边是图谱声明的事实，文件名是命名约定的推断。0821 实测两者在 24,318
        # 个重叠案例上零冲突，但顺序必须写死——真出现分歧时以血缘边为准。
        rec = self._record("HRR1402616.BQSR.bam")
        self.assertEqual(rec["sample_attribution_via"], "lineage_edge",
                         "文件名里也有 HRR 号，但不该抢在血缘边前面")


if __name__ == "__main__":
    unittest.main(verbosity=2)
