"""两代 T1 导出的 schema 分派——走错分支不报错，只把字段清空。

0821 把默认 CSV_DIR 从 data/csv 切到 data/0812 时踩到的坑：

    data/csv   camelCase（dataName / studyAccession / runAccession），
               物理路径另存在同级 T11.csv，靠文件名 join 回来。
    data/0812  snake_case（file_name / study_accession / run_accession），
               file_path / semantic_format / data_level 全部内联，无 T11.csv。

_load_normalized_t1 原本只认 camelCase。喂给它 0812 的行，每个 row.get() 都返回
None，于是 28,229 行 T1 全部退化成空串——**不抛异常、不报警告**。T2 是原样读取的
所以照常工作，掩盖了故障；表面症状只是"配对用例找不到数据、matched_count=0"。

这类静默清空最难查，所以下面逐字段锁死，而不是只断言"行数大于 0"。
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline_router import CsvKGDataMatcher  # noqa: E402

# 下游 _file_record / _sample_role / 配对逻辑按这套键读 T1。两个分支的输出必须
# 完全一致，少一个键就是一处静默空值。
REQUIRED_T1_KEYS = {
    "study_accession", "sample_accession", "run_accession", "data_type",
    "Read Pair", "files", "file_id", "file_name", "format", "file_path",
    "file_description", "Experiment", "Platform", "data_level", "strategy",
    "individual_accession", "individual_name", "sample_name",
    "specimen_type", "specimen_types", "tissue_type", "gender",
}


class T1LoaderSchemaTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.matcher = CsvKGDataMatcher()
        if not cls.matcher.t1:
            raise unittest.SkipTest(
                f"{cls.matcher.csv_dir} 下没有 T1，跳过（不等于通过）")

    def test_dispatch_is_by_column_name_not_directory(self):
        # 判据必须是列名。目录名可以由 DATA_CSV_DIR 指到任何地方，按路径猜分支
        # 等于把配置错误变成静默的数据错误。
        inline = self.matcher._load_inline_t1([{
            "study_accession": "HRA000001", "sample_accession": "HRS000001",
            "run_accession": "HRR000001", "file_name": "HRR000001_1.fastq.gz",
            "file_path": "/data/HRR000001_1.fastq.gz", "strategy": "WES",
        }])
        self.assertEqual(inline[0]["study_accession"], "HRA000001")
        self.assertEqual(inline[0]["file_path"], "/data/HRR000001_1.fastq.gz")

    def test_both_branches_emit_the_same_key_set(self):
        camel = self.matcher._load_normalized_t1(
            [{"dataName": "x.fastq.gz", "studyAccession": "HRA000001"}], [])
        inline = self.matcher._load_inline_t1(
            [{"file_name": "x.fastq.gz", "study_accession": "HRA000001"}])
        self.assertEqual(set(camel[0]), set(inline[0]),
                         "两个分支的输出键不一致，下游会在其中一支上读到 None")
        self.assertEqual(set(inline[0]), REQUIRED_T1_KEYS)

    def test_loaded_rows_are_not_silently_blank(self):
        # 这条就是当初该失败却没失败的那一条。只数行数是不够的——退化后行数不变，
        # 变的是每一行的内容。
        total = len(self.matcher.t1)
        with_study = sum(1 for r in self.matcher.t1 if r.get("study_accession"))
        self.assertEqual(with_study, total,
                         f"{total - with_study}/{total} 行没有 study_accession，"
                         f"schema 分派可能走错了分支")

    def test_absolute_paths_survive_loading(self):
        # agent_input 要给执行端真实路径。退化时这里会全部变成裸文件名，
        # 看起来"有值"，实际不可用。
        absolute = sum(1 for r in self.matcher.t1
                       if str(r.get("file_path", "")).startswith("/"))
        self.assertGreater(absolute, len(self.matcher.t1) * 0.9,
                           f"只有 {absolute}/{len(self.matcher.t1)} 行是绝对路径")

    def test_read_pair_is_inferred_for_fastq(self):
        # 0812 那代没有 Read Pair 列，端序全靠文件名推。推不出来配对分析就做不了，
        # 而且不会报错——只会少一组可用数据。
        fastqs = [r for r in self.matcher.t1
                  if str(r.get("file_name", "")).endswith((".fastq.gz", ".fq.gz"))]
        # 这里不能 skip。T1 有几万行却一个 FASTQ 都没有，只可能是加载退化把
        # file_name 清空了——skip 会把这种情况记成"该性质未覆盖"而放过去。
        self.assertTrue(fastqs,
                        f"T1 有 {len(self.matcher.t1)} 行却没有一个 FASTQ，加载多半已退化")
        resolved = [r for r in fastqs if r.get("Read Pair")]
        self.assertGreater(len(resolved), len(fastqs) * 0.9,
                           f"只有 {len(resolved)}/{len(fastqs)} 个 FASTQ 推出了端序")

    def test_known_pair_resolves_end_to_end(self):
        # 定点核对一组：0812 里 HRR365660 是 HRA001272 的 WES 双端。
        # 先确认 run_accession 这一列整体是活的，再找那一组——否则"找不到 HRR365660"
        # 到底是换了批数据还是加载退化了，这条用例分不清，只会 skip 掉。
        with_run = [r for r in self.matcher.t1
                    if str(r.get("run_accession", "")).startswith("HRR")]
        self.assertGreater(len(with_run), len(self.matcher.t1) * 0.5,
                           f"只有 {len(with_run)}/{len(self.matcher.t1)} 行有 HRR 号，"
                           f"run_accession 列没被正确读出来")
        pair = [r for r in with_run if r["run_accession"] == "HRR365660"]
        if not pair:
            self.skipTest("run_accession 列正常，但本批数据里没有 HRR365660")
        self.assertEqual({r["Read Pair"] for r in pair}, {"R1", "R2"})
        for record in pair:
            self.assertEqual(record["study_accession"], "HRA001272")
            self.assertEqual(record["strategy"], "WES")
            self.assertTrue(record["sample_accession"].startswith("HRS"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
