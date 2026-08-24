"""单细胞 rds 输入必须解析成对的那一个，参考白名单不能吞掉必需参数。

0824 师兄报"图谱里有三套 rds 数据，`lung_tme_annotation_cnv` 这些工具还是不能正确
返回对应的参数"。查下来是两个独立缺陷，共同点是**回包都看不出异常**：

缺陷一：`scrna_object_rds` 槽没有格式判别。`_role_for_input('scrna_object_rds')` 一条
规则都不命中，落到 `data_file`；而 `Matrix-h5`（10x 稀疏矩阵目录，format=dir）在
`_execution_asset_role` 里也是 `data_file`。两边一对上，`input_rds` 就被填成了那个 h5
目录，`missing` 是空的。所以它不是"取不到参数"，是取到了一个**错的**参数还宣称一个
都不缺——执行端 readRDS 一个目录必然失败，但在回包里看，路径合法、字段齐全、
submittable=true。同一批研究里两种文件同名同目录，只有物理格式分得开它们。
受影响的是带 `scrna_object_rds` 槽的 9 个工具。

缺陷二：`gene_order` 被参考规则静默吞掉。它的槽名叫 `genome_annotation`，命中
`_role_for_input` 的 "genome"/"annotation" 关键字被判成 `reference_file`，于是
`_execution_params` 里那句 `if role == "reference_file": continue` 把它跳过——既不进
`execution_params` 也不进 `execution_params_missing`。可它在 WDL 里是裸的
`File gene_order`、在 knowledge_card 里是 `required: true, default: None`、在执行契约里
根本没有，执行端不自带，缺了 inferCNV 跑不起来。

这是 0823 修 `filtered_vcf_index` 时踩过的同一个坑（那次是 "index" 关键字），只是从
另一个关键字进来的。名字判别在这个目录里已经错过两次，所以规则 4 改成
`REFERENCE_RESOURCE_PARAMS` 显式二元组白名单，判据是执行契约的
`managed_by: "executor"`，不是槽名长得像不像参考数据。

下面每条都锁"不能声称可提交/不能给错值"，不是只锁字段值。
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline_router as router  # noqa: E402
from workflow_composer import (  # noqa: E402
    REFERENCE_RESOURCE_PARAMS,
    RegisteredMethod,
    WorkflowComposer,
)

ROOT = Path(__file__).resolve().parent.parent

# HRA005191（NSCLC，`lung_tme_annotation_cnv` 的目标队列）在活图里的两个真实资产。
# 两者同属一个 study、同在 scRNAseq 目录下、名字都像单细胞产物，只有 format 不同。
H5_DIR = {
    "files": "Matrix-h5",
    "format": "dir",
    "file_path": "/hpcdisk1/cbb_group/data/scRNAseq/HRA005191/Matrix-h5",
}
SEURAT_RDS = {
    "files": "03_sc_obj_final_anno.rds",
    "format": "rds",
    "file_path": (
        "/hpcdisk1/cbb_group/data/scRNAseq/HRA005191"
        "/Analysis-results/NSCLC_1/03_sc_obj_final_anno.rds"
    ),
}

# lung_tme_annotation_cnv 在 io_slot.csv 里的两个输入槽，绑定本来就是对的。
LUNG_TME_SLOTS = [
    {"name": "genome_annotation", "builder_param": "gene_order",
     "required": "true", "wdl_type": "File"},
    {"name": "scrna_object_rds", "builder_param": "input_rds",
     "required": "true", "wdl_type": "File"},
]


def _method(tool_id, inputs):
    return RegisteredMethod(
        tool_id=tool_id, catalog_id="T999", tool_kind="pipeline", name=tool_id,
        pipeline_ids=[], description="", inputs=inputs, outputs=[],
        next_tool_ids=[], input_variants={}, input_aliases={},
        exactly_one_variant=False,
    )


class ScrnaObjectFormatDiscriminationTests(unittest.TestCase):
    """缺陷一：h5 目录不能冒充 Seurat rds。"""

    def setUp(self):
        # 只验 _execution_params 这条纯函数路径，绕开需要图谱连接的 __init__。
        self.composer = object.__new__(WorkflowComposer)

    def _run(self, assets):
        return self.composer._execution_params(
            _method("lung_tme_annotation_cnv", LUNG_TME_SLOTS), {"assets": list(assets)}
        )

    def test_h5_directory_never_lands_in_input_rds(self):
        """这是本轮最危险的一条：错得像对。

        修之前，只有 Matrix-h5 的队列会返回
        `{'input_rds': '/hpcdisk1/.../HRA005191/Matrix-h5'}` 且 `missing: []`。
        路径存在、字段齐全、看不出任何异常，但执行端 readRDS 一个目录必然失败。
        宁可报缺，也不给一个跑不通的值。
        """
        params, missing = self._run([H5_DIR])
        self.assertNotIn(
            H5_DIR["file_path"], json.dumps(params, ensure_ascii=False),
            f"10x 的 Matrix-h5 目录被填进了 execution_params：{params}。"
            "它不是 Seurat 对象，执行端 readRDS 会失败——而回包看上去完全正常。",
        )
        self.assertNotIn("input_rds", params)
        by_param = {e.get("param"): e.get("reason") for e in missing}
        self.assertEqual(
            by_param.get("input_rds"), "no_confirmed_path",
            f"没有 rds 资产时 input_rds 必须报缺，实际 missing={missing}",
        )

    def test_real_rds_resolves_even_when_h5_is_also_present(self):
        """两者同时在场时要挑对那一个，不能按列表顺序撞运气。"""
        params, missing = self._run([H5_DIR, SEURAT_RDS])
        self.assertEqual(params.get("input_rds"), SEURAT_RDS["file_path"], params)
        self.assertNotIn(
            "input_rds", {e.get("param") for e in missing},
            "rds 就在资产里却报了缺",
        )

    def test_role_is_decided_by_format_not_by_name(self):
        """名字判别分不开这两个文件，格式判别可以。

        `Matrix-h5` 和 `03_sc_obj_final_anno.rds` 都在 scRNAseq 目录下、都是单细胞
        产物，名字里都没有"这是不是 Seurat 对象"的信号。所以这条规则必须落在
        format/后缀上——真改成按文件名猜，这个测试就会挂。
        """
        self.assertEqual(self.composer._execution_asset_role(SEURAT_RDS), "scrna_object")
        self.assertNotEqual(
            self.composer._execution_asset_role(H5_DIR), "scrna_object",
            "h5 目录被判成了单细胞对象",
        )
        self.assertEqual(router._role_of_file(SEURAT_RDS), "scrna_object")
        self.assertNotEqual(router._role_of_file(H5_DIR), "scrna_object")

    def test_rds_substring_does_not_hijack_ordinary_files(self):
        """`_role_for_input` 也被拿**文件名**调用，所以判后缀不判子串。

        `"rds"` 作为子串会命中 `…records.tsv` 这类普通表格。真按子串判，一张
        records 表就会被当成 Seurat 对象喂给 input_rds——又是一个"错得像对"。
        """
        self.assertNotEqual(
            self.composer._role_for_input("sample_records_table"), "scrna_object",
            "'records' 里的 rds 子串把普通表格判成了单细胞对象",
        )
        self.assertNotEqual(
            self.composer._execution_asset_role(
                {"files": "HRA005191-records.tsv", "format": "tsv",
                 "file_path": "/d/HRA005191-records.tsv"}
            ),
            "scrna_object",
        )


class ReferenceAllowlistTests(unittest.TestCase):
    """缺陷二：规则 4 只对执行端自带的资源生效，且必须是显式白名单。"""

    def setUp(self):
        self.composer = object.__new__(WorkflowComposer)

    def test_gene_order_is_reported_missing_not_swallowed(self):
        """`gene_order` 必须报缺——既不能映射一个假路径，也不能一声不吭。

        它的槽名是 `genome_annotation`，会命中 "genome"/"annotation" 关键字。修之前
        这条被 `if role == "reference_file": continue` 直接跳过，于是回包里它既不在
        execution_params 也不在 missing——查回包的人根本不知道少了一个必需输入。
        """
        _params, missing = self.composer._execution_params(
            _method("lung_tme_annotation_cnv", LUNG_TME_SLOTS),
            {"assets": [SEURAT_RDS]},
        )
        by_param = {e.get("param"): e for e in missing}
        self.assertIn(
            "gene_order", by_param,
            f"gene_order 被参考规则静默吞掉了：missing={missing}。它在 WDL 里是裸的 "
            "File gene_order、卡片里 default 是 None、执行契约里没有——执行端不自带，"
            "缺了 inferCNV 跑不起来。不报缺就等于说'不缺'。",
        )
        self.assertEqual(by_param["gene_order"]["reason"], "no_confirmed_path")
        self.assertNotEqual(
            by_param["gene_order"]["role"], "reference_file",
            "报缺条目的 role 仍写着 reference_file，消费方会当成'执行端自带、可忽略'"
            "——正好是这条被漏掉两轮的原因。",
        )

    def test_lung_tme_never_claims_submittable_while_missing_a_required_input(self):
        """验收标准：不能同时 submittable=true 且漏掉卡片声明的必需 File 输入。

        `submittable` 的口径是 `bool(params) and not missing`（见 workflow_composer
        对 alternatives 的赋值），这里按同样口径核。
        """
        for label, assets in (
            ("只有 h5 目录", [H5_DIR]),
            ("图里有 rds", [H5_DIR, SEURAT_RDS]),
        ):
            with self.subTest(label):
                params, missing = self.composer._execution_params(
                    _method("lung_tme_annotation_cnv", LUNG_TME_SLOTS), {"assets": assets}
                )
                submittable = bool(params) and not missing
                required = {"input_rds", "gene_order"}
                if submittable:
                    self.assertEqual(
                        required - set(params), set(),
                        f"[{label}] 宣称可提交，却漏了 {required - set(params)}",
                    )

    def test_executor_managed_resources_stay_silent(self):
        """真正由执行端自带的 5 个资源仍然不报，否则全是噪声。"""
        for tool_id, param, slot in (
            ("star", "rrna_star_index", "rrna_star_index"),
            ("star", "genome_star_index", "genome_star_index"),
            ("rsem", "rsem_index", "rsem_index"),
            ("featurecounts", "gtf_file", "genome_annotation"),
            ("gatk", "interval_list", "interval_list"),
        ):
            with self.subTest(f"{tool_id}.{param}"):
                _p, missing = self.composer._execution_params(
                    _method(tool_id, [{"name": slot, "builder_param": param,
                                       "required": "true", "wdl_type": "File"}]),
                    {"assets": []},
                )
                self.assertEqual(
                    missing, [],
                    f"{tool_id}.{param} 是执行端自带的参考资源，报出来只会淹掉真要处理的条目",
                )

    def test_allowlist_is_keyed_by_tool_and_param_not_by_name(self):
        """白名单必须是二元组。

        同一个参数名在不同卡片下归属可以不同，只按参数名建集合就会把别的卡片一起
        放行。而 `gene_order` 明确不在表内——它是这轮缺陷的原点。
        """
        for entry in REFERENCE_RESOURCE_PARAMS:
            self.assertIsInstance(entry, tuple, entry)
            self.assertEqual(len(entry), 2, entry)
        params_only = {param for _tool, param in REFERENCE_RESOURCE_PARAMS}
        self.assertNotIn(
            "gene_order", params_only,
            "gene_order 进了参考白名单。执行契约里没有它、两张卡的 default 都是 None，"
            "它必须由用户提供。",
        )

    def test_allowlist_matches_the_execution_contract(self):
        """白名单的判据是契约里的 managed_by=executor，不是有人觉得它像参考数据。

        契约是原子卡那 5 条；整卡（rnaseq_singletask / wes_somatic_pair）是同一批物理
        资源的镜像，允许多出来，但不允许出现契约里标着 managed_by=mcp 的参数——那些
        是用户数据，放进白名单就等于把必需输入静默吞掉。
        """
        contract = json.loads(
            (ROOT / "config" / "knowledge_card_execution_contracts.json").read_text(
                encoding="utf-8"
            )
        )["tools"]
        mcp_managed = {
            (tool_id, name)
            for tool_id, spec in contract.items()
            for name, item in (spec.get("inputs") or {}).items()
            if item.get("managed_by") == "mcp"
        }
        leaked = REFERENCE_RESOURCE_PARAMS & mcp_managed
        self.assertEqual(
            leaked, set(),
            f"这些是 managed_by=mcp 的用户数据，却进了参考白名单：{leaked}",
        )
        executor_managed = {
            (tool_id, name)
            for tool_id, spec in contract.items()
            for name, item in (spec.get("inputs") or {}).items()
            if item.get("managed_by") == "executor"
            and str(item.get("type") or "").startswith("File")
        }
        self.assertTrue(
            executor_managed <= REFERENCE_RESOURCE_PARAMS,
            f"契约里 managed_by=executor 的 File 输入没全部进白名单："
            f"{executor_managed - REFERENCE_RESOURCE_PARAMS}",
        )


if __name__ == "__main__":
    unittest.main()
