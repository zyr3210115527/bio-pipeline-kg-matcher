"""未绑定的输入槽必须**说出来**，不能无声跳过。

0823 师兄报"新接入工具的三个输入 builder_param、wdl_target 全空"。根因在
`data/csv/catalog/io_slot.csv`——128 个输入槽有 95 个没抄上 WDL 绑定。但真正让这件事
拖到用肉眼发现的，是 `_execution_params` 里那句无声的 `continue`：没有 builder_param
的槽被直接跳过，回包给出 `execution_params: {}` 加一份字段完整的推荐，
`execution_params_missing` 也是空的。

空 params + 空 missing 等于宣称"这张卡零个参数、且一个都不缺"，消费方按 `not missing`
判可提交就会当成能提交。这和 `method is None` 那一支要解决的是同一个毛病，那边已经
修过一次（写入 method_not_in_catalog）；这边漏了。

所以锁三件事：

1. 未绑定的**数据**槽进 missing，reason=slot_not_bound；
2. 参考文件槽仍然不报（师兄规则 4：参考索引带卡片默认值，不是用户数据）；
3. 已绑定但没有确认路径的槽，reason 仍是 no_confirmed_path——别把两类混成一类，
   "没有绑定"要人去补目录表，"没有路径"要数据侧补 file_path，处置完全不同。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow_composer import RegisteredMethod, WorkflowComposer  # noqa: E402


def _method(inputs):
    return RegisteredMethod(
        tool_id="probe", catalog_id="T999", tool_kind="pipeline", name="probe",
        pipeline_ids=[], description="", inputs=inputs, outputs=[],
        next_tool_ids=[], input_variants={}, input_aliases={},
        exactly_one_variant=False,
    )


class SlotNotBoundIsReportedTests(unittest.TestCase):
    def setUp(self):
        # 只验 _execution_params 这一个纯函数式的方法，绕开需要图谱连接的 __init__。
        self.composer = object.__new__(WorkflowComposer)

    def _run(self, inputs, assets=()):
        return self.composer._execution_params(_method(inputs), {"assets": list(assets)})

    def test_unbound_data_slot_is_reported_not_silently_dropped(self):
        params, missing = self._run([
            {"name": "scrna_object_rds", "builder_param": "", "wdl_type": "File"},
        ])
        self.assertEqual(params, {})
        reasons = [entry["reason"] for entry in missing]
        self.assertIn(
            "slot_not_bound", reasons,
            "没有 builder_param 的数据槽被无声跳过了。回包会是 execution_params={} 且 "
            "missing=[]，也就是'零个参数且一个都不缺'——消费方按 not missing 判可提交，"
            "就把一个绑不上参数的流程当成能跑的。",
        )
        entry = next(e for e in missing if e["reason"] == "slot_not_bound")
        self.assertEqual(entry["slot"], "scrna_object_rds")
        self.assertIsNone(entry["param"], "槽本来就没有 WDL 参数名，不能编一个出来")

    def test_reference_slots_stay_silent(self):
        # 师兄规则 4：参考索引/基因组带卡片默认值，不是用户数据，报出来只会变成噪声，
        # 淹掉真正要人处理的那几条。
        _params, missing = self._run([
            {"name": "genome_annotation", "builder_param": "", "wdl_type": "File"},
        ])
        self.assertEqual(
            missing, [],
            f"参考文件槽被报成了缺失：{missing}。规则 4 说这类不报。",
        )

    def test_alias_rows_do_not_double_report(self):
        """别名行不是独立输入，报两次只会淹掉别的条目。

        bwa 的 clean_fastq_read 是 clean_fastq_read_r1 的旧槽名（variant_alias_for）。
        真实槽自己会报一条 slot_not_bound；别名再报一条，师兄那边看到的就是同一个
        缺口出现两次，而 39 条待确认里这种别名有 2 条。
        """
        _params, missing = self._run([
            {"name": "clean_fastq_read", "builder_param": "",
             "variant_alias_for": "clean_fastq_read_r1", "wdl_type": "File"},
        ])
        self.assertEqual(missing, [], f"别名行被单独报了一次：{missing}")

    def test_unbound_and_unresolved_keep_distinct_reasons(self):
        """两类失败的处置不同，不能合并成一个 reason。

        slot_not_bound 要人去 io_slot.csv 补绑定；no_confirmed_path 是绑定没问题、
        但图里没有确认路径（如 T1 FASTQ 的 file_path=NOT_FOUND），要数据侧补。混成
        一类，等于让下游分不清该找谁。
        """
        _params, missing = self._run([
            {"name": "scrna_object_rds", "builder_param": "", "wdl_type": "File"},
            {"name": "somatic_maf", "builder_param": "maf_file", "wdl_type": "File"},
        ])
        by_slot = {entry["slot"]: entry["reason"] for entry in missing}
        self.assertEqual(by_slot.get("scrna_object_rds"), "slot_not_bound")
        self.assertEqual(by_slot.get("somatic_maf"), "no_confirmed_path")


class ArrayAndIndexSlotTests(unittest.TestCase):
    """0823 第三轮：槽表按 WDL 对齐之后新出现的两个静默失败面。"""

    def setUp(self):
        self.composer = object.__new__(WorkflowComposer)

    def _run(self, inputs, assets):
        return self.composer._execution_params(_method(inputs), {"assets": list(assets)})

    def test_array_slot_returns_all_paths_not_just_one(self):
        """`Array[File]` 参数必须给全部路径。

        走单值那条路只会取一个：fastqc 的 scatter 就只跑一个 FASTQ、cnvkit 的队列只算
        一个样本。两者都不报错，只是悄悄少做——正是"错得像对"。
        """
        assets = [
            {"files": "a_R1.fq.gz", "file_path": "/data/a_R1.fq.gz",
             "read_pair": "r1", "format": "fq.gz"},
            {"files": "b_R1.fq.gz", "file_path": "/data/b_R1.fq.gz",
             "read_pair": "r1", "format": "fq.gz"},
        ]
        params, missing = self._run([
            {"name": "raw_fastq_read_r1", "builder_param": "fastqs",
             "cardinality": "array", "wdl_type": "Array[File]+"},
        ], assets)
        self.assertEqual(missing, [])
        self.assertEqual(
            params.get("fastqs"), ["/data/a_R1.fq.gz", "/data/b_R1.fq.gz"],
            f"数组参数被压成了单值：{params}",
        )

    def test_two_slots_sharing_one_array_param_union_not_overwrite(self):
        """fastqc 的 raw / clean 两个槽都对 `fastqs`，后者不能把前者冲掉。"""
        assets = [
            {"files": "raw_R1.fq.gz", "file_path": "/data/raw_R1.fq.gz",
             "read_pair": "r1", "format": "fq.gz"},
            {"files": "raw_R2.fq.gz", "file_path": "/data/raw_R2.fq.gz",
             "read_pair": "r2", "format": "fq.gz"},
        ]
        params, _missing = self._run([
            {"name": "raw_fastq_read_r1", "builder_param": "fastqs", "cardinality": "array"},
            {"name": "raw_fastq_read_r2", "builder_param": "fastqs", "cardinality": "array"},
        ], assets)
        self.assertEqual(params.get("fastqs"),
                         ["/data/raw_R1.fq.gz", "/data/raw_R2.fq.gz"])

    def test_vcf_index_is_data_not_reference(self):
        """`filtered_vcf_index` 名字里带 "index"，但它没有卡片默认值。

        被当成参考资源就会既不映射也不报缺（师兄规则 4），bcftools 于是少给一个必需
        参数还一声不吭——缺了它 `ln -sf` 读不到 .tbi，执行直接失败。
        """
        role = self.composer._role_for_input("filtered_vcf_index")
        self.assertEqual(role, "vcf_file", "VCF 的伴随索引被判成了参考资源")
        _params, missing = self._run([
            {"name": "filtered_vcf_index", "builder_param": "filtered_vcf_index"},
        ], [])
        self.assertEqual([e["reason"] for e in missing], ["no_confirmed_path"])

    def test_reference_index_slots_stay_silent(self):
        """真正的参考索引仍然不报（star 的两个 STAR 索引、rsem_index）。"""
        for name in ("rrna_star_index", "genome_star_index", "rsem_index"):
            self.assertEqual(self.composer._role_for_input(name), "reference_file", name)


if __name__ == "__main__":
    unittest.main()
