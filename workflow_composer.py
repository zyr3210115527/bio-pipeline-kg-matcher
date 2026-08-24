"""Two-tier workflow planning over the Neo4j pipeline and atomic-tool catalog."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from pipeline_router import (
    PipelineDef,
    PipelineRouter,
    _force_rule,
    _lazy_call_llm,
    _role_satisfies,
    _sample_role,
)
from knowledge_card_execution import KnowledgeCardExecutionRegistry
from neo4j_observability import Neo4jClient
from question_benchmark import (
    exact_reference,
    prompt_examples,
    reference_pipeline_ids,
)
from runtime_config import initialize_runtime


initialize_runtime()


METHOD_CATALOG_STATUS = {
    "status": "work_in_progress",
    "scope": "Neo4j curated tool catalog and reviewed NEXT relationships",
    "source": "neo4j",
    "is_complete_internal_tool_decomposition": False,
}

EXECUTION_MANAGED_ASSET_ROLES = {"reference_file"}

# 师兄规则 4（"参考/索引资源自带默认值，既不映射进 execution_params 也不报缺"）的
# 适用范围，写成 (tool_id, builder_param) 的显式二元组白名单。
#
# 依据是 `config/knowledge_card_execution_contracts.json` 里 `managed_by: "executor"`
# 的 File 输入——执行端在容器里自带这些路径，正好下面 5 条。不是"名字里带
# index/genome/gtf/annotation 就是参考资源"。
#
# 为什么不能按名字猜：`gene_order` 的槽名是 `genome_annotation`，命中
# `_role_for_input` 的 "genome"/"annotation" 关键字被判成 reference_file，于是
# `lung_tme_annotation_cnv` / `dataset_downstream` 这两张卡**已经绑好 builder_param**
# 的必需输入被无声跳过——既不进 execution_params 也不进 missing。可它在 WDL 和
# knowledge_card 里都是 `required: true, default: None`，执行端没有它，缺了必然失败。
# 这就是 0823 修 `filtered_vcf_index` 时踩的同一个坑，只是从另一个关键字进来的。
# 名字判别在这个目录里已经错过两次，所以改成白名单，新工具接入时手动加一行。
#
# 三条硬约束（改这张表前先看）：
#   1. 只有执行端确实自带的资源才能进来。判据优先级：执行契约的
#      `managed_by: "executor"` > 原子卡 `interface.params[].default` 非空。
#      "看起来像参考数据"不是判据。
#   2. 键的第二位是 builder_param（真实 WDL 参数名），不是槽名。同一个参数名在不同
#      卡片下归属可以不同，所以键必须带 tool_id，不能只按参数名建集合。
#   3. 这张表只决定"不报缺"，不决定"不校验"。
REFERENCE_RESOURCE_PARAMS = {
    # 执行契约里 managed_by="executor" 的 5 个 File 输入（原子卡）。
    # star/rsem/featurecounts 三张原子卡还带着具体默认路径
    # （/cromwell-share/.../reference_data/…），是执行端自带的直接证据。
    ("featurecounts", "gtf_file"),
    ("gatk", "interval_list"),
    ("rsem", "rsem_index"),
    ("star", "rrna_star_index"),
    ("star", "genome_star_index"),
    # 整卡是上面同一批物理资源的镜像：同一个 builder_param、同一份参考数据，
    # 只是整卡的 knowledge_card 没把默认值抄下来（default: None）。按资源归属
    # 而不是按卡片字面值判，否则 rnaseq_singletask / wes_somatic_pair 会凭空多出
    # 5 个报缺、被判成永不可提交。
    ("rnaseq_singletask", "gtf_file"),
    ("rnaseq_singletask", "rrna_star_index"),
    ("rnaseq_singletask", "rsem_index"),
    ("rnaseq_singletask", "star_genome_index"),
    ("wes_somatic_pair", "interval_list"),
    # 刻意不在表内：`dataset_downstream` / `lung_tme_annotation_cnv` 的 `gene_order`。
    # 它的槽名叫 `genome_annotation`，命中关键字启发式的 "genome"/"annotation" 被
    # 当成参考资源吞掉，但执行契约里没有它、两张卡的 default 都是 None、WDL 里是
    # 裸的 `File gene_order`。执行端不自带，缺了 inferCNV 跑不起来，必须报缺。
}


def _evidence_asset(
    item: Dict[str, Any],
    role_of: Optional[Any] = None,
) -> Dict[str, Any]:
    """把图谱证据文件包成 recommendations[].data.assets[] 的一项。

    v2 里 candidates[].assets 用 asset_id / role / path，而这条证据链一直用内部
    形状 file_id / input_role / file_path。schema 对本字段是自由对象，所以两套并存
    不算违约——但消费方照着 candidates 的写法去读 path，拿到的是 None 而不是报错，
    又是一个"安静的空值"。这里加性补齐三个规范键，既有键一个都不动。

    role_of 是 matcher._file_role：组合匹配那条路不走 _with_input_role，item 里没有
    input_role。补个空字符串等于把"没解析出角色"和"角色是空"混成一样，所以宁可现算。
    """
    role = str(item.get("input_role") or "")
    if not role and role_of is not None:
        try:
            role = str(role_of(item) or "")
        except Exception:
            role = ""
    return {
        "name": item.get("files"),
        "graph_status": "available",
        **item,
        "asset_id": item.get("file_id") or item.get("files") or "",
        "role": role,
        "path": item.get("file_path") or "",
    }


CAPABILITY_DATA_FILTERS: Dict[str, Dict[str, Any]] = {
    "maf": {
        "aliases": ("maf", "突变文件", "体细胞突变数据"),
        "slot_terms": ("somatic_maf", "maf"),
        "label": "MAF",
    },
    "clinical": {
        "aliases": ("clinical", "临床数据", "临床表", "临床信息"),
        "slot_terms": ("clinical",),
        "label": "Clinical",
    },
    "metainfo": {
        "aliases": ("metainfo", "meta info", "sample metadata", "样本元数据", "样本信息"),
        "slot_terms": ("metainfo", "sample_meta", "metadata"),
        "label": "MetaInfo",
    },
    "fastq": {
        "aliases": ("fastq", "fq.gz", "原始测序", "原始 reads", "原始reads"),
        "slot_terms": ("fastq", "raw_fastq_read", "clean_fastq_read", "fq.gz"),
        "label": "FASTQ",
    },
    "count_matrix": {
        "aliases": ("count matrix", "count矩阵", "count 矩阵", "counts矩阵", "计数矩阵"),
        "slot_terms": ("count_matrix", "expression_count_matrix"),
        "label": "count matrix",
    },
    "expression_matrix": {
        "aliases": ("表达矩阵", "tpm", "fpkm", "expression matrix"),
        "slot_terms": ("expression_matrix", "expression_abundance", "expression_tpm", "tpm", "fpkm"),
        "label": "表达矩阵",
    },
    "matrix": {
        "aliases": ("矩阵文件", "matrix 文件", "matrix file", "哪些矩阵", "什么矩阵"),
        "slot_terms": ("matrix", "expression_"),
        "label": "矩阵",
    },
    "bam": {
        "aliases": ("bam", "比对文件"),
        "slot_terms": ("bam",),
        "label": "BAM",
    },
    "vcf": {
        "aliases": ("vcf", "变异结果"),
        "slot_terms": ("vcf",),
        "label": "VCF",
    },
}

CAPABILITY_TOPIC_FILTERS: Dict[str, Dict[str, Any]] = {
    "survival": {"aliases": ("生存", "survival", "pfs"), "terms": ("survival", "pfs"), "label": "生存分析"},
    "enrichment": {"aliases": ("富集", "go", "kegg", "reactome"), "terms": ("enrichment", "diff_expr_go", "diff_expr_kegg", "富集"), "label": "富集分析"},
    "clustering": {"aliases": ("聚类", "分型", "cluster"), "terms": ("cluster", "聚类", "分型"), "label": "聚类/分型"},
    "coexpression": {"aliases": ("共表达", "wgcna"), "terms": ("wgcna", "共表达"), "label": "共表达"},
    "immune": {"aliases": ("免疫浸润", "cibersort", "iobr"), "terms": ("immune", "iobr", "免疫浸润"), "label": "免疫浸润"},
    "mutation_landscape": {"aliases": ("突变景观", "oncoplot"), "terms": ("landscape", "oncoplot", "突变景观"), "label": "突变景观"},
    "rnaseq_upstream": {"aliases": ("rna-seq 上游", "rnaseq 上游", "表达定量"), "terms": ("rnaseq_singletask", "rna-seq", "表达定量"), "label": "RNA-seq 上游"},
    "ubam": {"aliases": ("ubam", "未比对 bam", "unmapped bam"), "terms": ("unmapped_bam", "ubam"), "label": "uBAM"},
    "single_cell": {"aliases": ("单细胞", "single-cell", "scrna"), "terms": ("cellranger", "single-cell", "scrna"), "label": "单细胞"},
    "proteomics": {"aliases": ("蛋白质组", "proteomics", "mzml"), "terms": ("proteomics", "mzml"), "label": "蛋白质组"},
    "epigenomics": {"aliases": ("atac-seq", "chip-seq", "cut&tag", "表观组"), "terms": ("atac", "chip", "cut&tag", "epigen"), "label": "表观组"},
    "microbiome": {"aliases": ("微生物组", "宏基因组", "16s", "metagenom"), "terms": ("microbiome", "metagenom", "16s"), "label": "微生物组"},
}

@dataclass
class RegisteredMethod:
    tool_id: str
    catalog_id: str
    tool_kind: str
    name: str
    pipeline_ids: List[str]
    description: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    next_tool_ids: List[str]
    input_variants: Dict[str, List[str]]
    input_aliases: Dict[str, str]
    exactly_one_variant: bool

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "catalog_id": self.catalog_id,
            "tool_kind": self.tool_kind,
            "name": self.name,
            "pipeline_ids": self.pipeline_ids,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "allowed_next_tool_ids": self.next_tool_ids,
            "input_variants": self.input_variants,
            "exactly_one_variant": self.exactly_one_variant,
        }


class RegisteredMethodCatalog:
    """Runtime methods loaded exclusively from Neo4j."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        owned_client = client is None
        self.client = client or Neo4jClient()
        try:
            payload = self.client.tool_catalog()
        finally:
            if owned_client:
                self.client.close()
        self.connected = bool(payload.get("connected"))
        self.error = payload.get("error")
        next_by_id: Dict[str, List[str]] = {}
        self.next_edges: Set[Tuple[str, str]] = set()
        self.data_edges: Set[Tuple[str, str, str, str]] = set()
        for edge in payload.get("next_edges") or []:
            source = str(edge.get("source_tool_id") or "")
            target = str(edge.get("target_tool_id") or "")
            if source and target:
                if target not in next_by_id.setdefault(source, []):
                    next_by_id[source].append(target)
                self.next_edges.add((source, target))
                if str(edge.get("kind") or "").lower() == "data":
                    output = str(edge.get("output") or "")
                    input_name = str(edge.get("input") or "")
                    if output and input_name:
                        self.data_edges.add((source, output, target, input_name))
        all_methods: Dict[str, RegisteredMethod] = {}
        for item in payload.get("tools") or []:
            tool_id = str(item.get("tool_id") or "")
            if not tool_id:
                continue
            tool_kind = str(item.get("tool_kind") or "unknown")
            try:
                input_variants = json.loads(str(item.get("input_variants_json") or "{}"))
                input_aliases = json.loads(str(item.get("input_aliases_json") or "{}"))
            except json.JSONDecodeError:
                input_variants, input_aliases = {}, {}
            all_methods[tool_id] = RegisteredMethod(
                tool_id=tool_id,
                catalog_id=str(item.get("catalog_id") or ""),
                tool_kind=tool_kind,
                name=str(item.get("tool_name") or tool_id),
                pipeline_ids=[tool_id] if tool_kind in {"pipeline", "task_pipeline"} else [],
                description=str(item.get("description") or ""),
                inputs=[self._slot_spec(slot) for slot in item.get("inputs") or []],
                outputs=[self._slot_spec(slot) for slot in item.get("outputs") or []],
                next_tool_ids=next_by_id.get(tool_id, []),
                input_variants={
                    str(name): [str(value) for value in values]
                    for name, values in input_variants.items()
                    if isinstance(values, list)
                },
                input_aliases={str(name): str(value) for name, value in input_aliases.items()},
                exactly_one_variant=bool(item.get("exactly_one_variant")),
            )
        self.all_methods = all_methods
        self.methods = {
            tool_id: method
            for tool_id, method in all_methods.items()
            if method.tool_kind == "atomic"
        }
        self.pipeline_methods = {
            tool_id: method
            for tool_id, method in all_methods.items()
            if method.tool_kind in {"pipeline", "task_pipeline"}
        }
        self.pipeline_steps: Dict[str, List[Dict[str, Any]]] = {}
        for step in payload.get("pipeline_steps") or []:
            pipeline_id = str(step.get("pipeline_id") or "")
            tool_id = str(step.get("tool_id") or "")
            method = self.methods.get(tool_id)
            if not pipeline_id or not method:
                continue
            self.pipeline_steps.setdefault(pipeline_id, []).append({
                **step,
                "description": method.description,
                "inputs": method.inputs,
                "outputs": method.outputs,
            })

    @staticmethod
    def _slot_spec(slot: Dict[str, Any]) -> Dict[str, Any]:
        artifacts = [str(value) for value in slot.get("artifacts") or [] if value]
        return {
            "name": str(slot.get("slot_name") or slot.get("slot_id") or "data_file"),
            "type": str(slot.get("wdl_type") or "File"),
            "is_file": True,
            # Real PipelineBuilder WDL parameter name + fully-qualified WDL key,
            # sourced from the workflow knowledge cards (interface.params name/target).
            # Empty for slots that have no direct file parameter (e.g. sample-lookup inputs).
            "builder_param": str(slot.get("builder_param") or ""),
            "wdl_target": str(slot.get("wdl_target") or ""),
            "optional": not bool(slot.get("required")),
            "artifact": artifacts[0] if artifacts else None,
            "formats": [str(value) for value in slot.get("formats") or [] if value],
            "description": str(slot.get("description") or ""),
            "dimension": str(slot.get("dimension") or ""),
            "dimension_value": str(slot.get("dimension_value") or ""),
            "variant": str(slot.get("variant") or ""),
            "variant_alias_for": str(slot.get("variant_alias_for") or ""),
            # "array" 表示 WDL 侧是 Array[File]（fastqc 的 fastqs、multiqc 的
            # qc_files、cnvkit 的 tumor_bams…）。单文件槽装不下数组，只补参数名没用：
            # 会给出一个字符串路径，执行端按数组解就崩，或者更糟——只跑了第一个样本。
            "cardinality": str(slot.get("cardinality") or ""),
        }

    def capabilities(self, include_pipelines: bool = False) -> List[Dict[str, Any]]:
        source = self.all_methods if include_pipelines else self.methods
        return [source[key].as_dict() for key in sorted(source)]

    def unavailable_state(self, atomic_only: bool = False) -> Optional[str]:
        """目录为空时返回一句"空成什么样"的描述；非空返回 None。

        目录只从图谱来，所以目录一空，**所有**关于工具的判断都失去前提：既不能说
        某个 tool_id 未知（我们什么都不认识），也不能说某类分析"尚未原子化"（我们
        不知道有没有）。三处调用点都从这里取词，免得日后各改各的又飘回去。

        atomic_only=True 只看可编排的原子工具——原子层为空时，"拆不成原子链"这种
        结论同样没有依据，哪怕 pipeline 节点还在。
        """
        source = self.methods if atomic_only else self.all_methods
        if source:
            return None
        if not self.connected:
            state = "图谱未连接"
        elif atomic_only and self.all_methods:
            state = "图谱已连接但未返回可编排的原子工具"
        else:
            state = "图谱已连接但未返回工具"
        return f"{state}（{self.error or 'unknown'}）"


class Neo4jPipelineCatalog:
    """PipelineRouter-compatible catalog built only from Neo4j tool contracts."""

    def __init__(self, methods: RegisteredMethodCatalog):
        self.pipelines: Dict[str, PipelineDef] = {}
        for pipeline_id, method in methods.pipeline_methods.items():
            registered_steps = methods.pipeline_steps.get(pipeline_id) or []
            steps = [
                {
                    "step_order": step.get("step_order"),
                    "step_id": step.get("step_id"),
                    "call_name": step.get("tool_id"),
                    "task_name": step.get("tool_id"),
                    "tool_id": step.get("tool_id"),
                    "description": step.get("description"),
                    "inputs": [item["name"] for item in step.get("inputs") or []],
                    "outputs": [item["name"] for item in step.get("outputs") or []],
                    "depends_on": step.get("depends_on") or [],
                    "source": "neo4j",
                }
                for step in registered_steps
            ]
            if not steps:
                steps = [{
                    "step_order": 1,
                    "step_id": pipeline_id,
                    "call_name": pipeline_id,
                    "task_name": pipeline_id,
                    "tool_id": pipeline_id,
                    "description": method.description,
                    "inputs": [item["name"] for item in method.inputs],
                    "outputs": [item["name"] for item in method.outputs],
                    "depends_on": [],
                    "source": "neo4j",
                }]
            self.pipelines[pipeline_id] = PipelineDef(
                pipeline_id=pipeline_id,
                name=method.name,
                directory=f"neo4j://tool/{pipeline_id}",
                keywords=[pipeline_id, method.name],
                description=method.description,
                repo_dir=Path("."),
                inputs=[{
                    "key": item["name"],
                    "type": "file_path",
                    "required": not item["optional"],
                    "description": item.get("description"),
                    "artifact": item.get("artifact"),
                    "formats": item.get("formats") or [],
                } for item in method.inputs],
                outputs=[{
                    "name": item["name"],
                    "description": item.get("description"),
                    "artifact": item.get("artifact"),
                    "formats": item.get("formats") or [],
                } for item in method.outputs],
                steps=steps,
            )

    def capabilities(self) -> List[Dict[str, Any]]:
        return [self.pipelines[key].as_capability() for key in sorted(self.pipelines)]


class WorkflowComposer:
    CUSTOM_HINTS = (
        "自定义", "修改内部", "改内部", "改成", "替换", "替代", "代替", "换成",
        "去掉", "移除", "删掉", "删除", "跳过", "省略", "插入", "添加", "新增",
        "增加一步", "新增一步", "不要用", "不用预制", "调整顺序", "重排", "提前到",
        "改流程", "自助餐",
    )
    CAPABILITY_BROWSE_HINTS = (
        "有哪些流程", "哪些流程", "所有流程", "流程列表", "流程清单", "列出流程",
        "有哪些pipeline", "哪些pipeline", "pipeline列表", "pipeline清单",
        "有哪些工具", "哪些工具", "所有工具", "工具列表", "工具清单", "列出工具",
        "有哪些方法", "哪些方法", "原子工具", "atomic tool",
    )
    CAPABILITY_GENERIC_PATTERNS = (
        r"^(?:你们|这个系统|系统|平台|这里)?(?:能|可以)(?:做|支持)(?:些)?什么[？?]?$",
        r"^(?:你们|这个系统|系统|平台|这里)?(?:有|具备)什么(?:能力|流程|工具)[？?]?$",
        r"^(?:支持|覆盖)哪些(?:分析|能力|输入|输出|格式)[？?]?$",
    )
    RECOMMENDATION_HINTS = (
        "哪个流程", "哪一个流程", "选哪个", "该选", "怎么选", "推荐流程",
        "推荐哪个", "用什么流程", "适合什么流程", "适合哪个",
    )

    def __init__(
        self,
        router: Optional[PipelineRouter] = None,
        method_catalog: Optional[RegisteredMethodCatalog] = None,
        execution_registry: Optional[KnowledgeCardExecutionRegistry] = None,
    ):
        self.registered_methods = method_catalog or RegisteredMethodCatalog()
        self.execution_registry = execution_registry or KnowledgeCardExecutionRegistry()
        self.router = router or PipelineRouter(
            catalog=Neo4jPipelineCatalog(self.registered_methods)
        )

    def plan(
        self,
        nl_text: Any,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        text = "" if nl_text is None else str(nl_text).strip()
        capability_intent = self._capability_intent(text)
        if capability_intent:
            return self._capability_plan(
                text,
                capability_intent,
                {
                    "used": False,
                    "status": "deterministic_capability_rule",
                    "model": None,
                    "calls": 0,
                    "stages": ["capability_classification"],
                },
            )
        decision, planner_metadata = self._top3_llm_decision(text)
        return self._top3_plan(text, decision, planner_metadata, top_k)

    def _top3_llm_decision(
        self, text: str
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Ask the model once for ranked atomic chains."""
        if not text or _force_rule():
            return None, {
                "used": False,
                "status": "force_rule" if _force_rule() else "empty_query",
                "calls": 0,
                "stages": [],
            }
        prompt = '''你是生信工作流候选链规划器。你只负责流程编排，不执行任务，也不讨论线程、内存等运行参数。

一次性生成 1 到 5 条按匹配程度排序的候选链。所有候选都必须只由下方 Neo4j 目录中的 atomic tool 组成；禁止输出 pipeline/task_pipeline 节点。候选数量策略：如果用户明确限定了唯一方法、唯一终产物或“只要/只能”某个方案，可以只返回 1 条；否则只要目录中存在 2 条以上完整、数据和 NEXT 合同都不同的合法方案，必须返回至少 2 条，优先返回 2 到 3 条。特别是用户没有明确提出 TMB 或其他单一终点时，不得擅自替用户收敛到一个方案，应返回不同终点/工具侧重的完整候选，并在 match_note 说明差异。严禁为了凑数复制链、截短链或返回无数据的链。为保证 JSON 完整，analysis 每个字段只写一句短句，match_note 和 reason 各不超过一句，不重复抄写规则或目录。

只输出一个 JSON 对象，不要 Markdown：
{
        "analysis": {
    "sample_layout": "单样本或配对样本及角色",
    "data_path": "输入到目标产物的数据形态变化",
    "coverage": "每条候选覆盖目标的方式",
    "checks": "闭集、槽位、NEXT、样本维度和最终产物自检"
  },
  "recommendations": [
    {"rank": 1, "pipeline_id": "业务流程 id", "match_note": "为何匹配用户目标"}
  ],
  "disease": {
    "status": "matched | not_available | unspecified",
    "term": "用户原话里指的癌种，没提就 null",
    "study_accessions": ["匹配到的队列编号，只能来自下方队列清单"]
  },
  "candidates": [
    {"rank": 1, "match_note": "推荐理由和侧重", "steps": [
      {
        "step_id": "唯一且稳定的标识",
        "tool_id": "目录中的 atomic tool id",
        "inputs": {
          "精确注册输入名": {"asset_role": "数据角色"}
          或 "精确注册输入名": {"from": {"step_id": "前序步骤", "output": "精确注册输出名"}}
        },
        "depends_on": ["仅用于顺序依赖的前序步骤"],
        "reason": "步骤作用"
      }
    ]}
  ],
  "unsupported_reason": null,
  "unsupported_kind": null
}

候选规则：
0b. **"拆不出原子链"永远不是清空 recommendations 的理由。**这两个字段各管各的：recommendations 回答"目录里有没有能做这件事的业务流程"，candidates 回答"能不能拆成可执行的原子步骤"。目录里登记了匹配的流程，就必须写进 recommendations，哪怕 candidates 只能为空、哪怕 unsupported_reason 写的是"尚未原子化"。WGCNA、无监督聚类、免疫浸润、驱动基因性别分层、突变景观这些都属于这种情况：整卡是现成的，原子层没有对应工具，正确输出是 recommendations 非空 + candidates 为空。用户换个说法、用繁体、写错别字、或者只描述目的而不点工具名（如"挖和分级挂钩的模块与枢纽基因"就是 WGCNA），都不改变这一点。
0a. **`disease` 字段必须输出，任何情况下都不能省略、不能为 null。**它决定后续能不能绑队列：漏掉这个字段，系统就不知道该用哪个癌种的数据，只能什么都不给。三种取值见下方"癌种判定"。即使用户没提癌种，也要显式输出 `{"status": "unspecified", "term": null, "study_accessions": []}`。
0. recommendations 是业务流程推荐，pipeline_id 只能来自下方“业务 pipeline 目录”；按匹配度给 1 到 3 条，不得用 atomic tool 代替。candidates 是可执行 atomic 链，两者含义不同。业务流程必须同时匹配用户明确给出的输入类型、样本布局和最终目标；只覆盖部分目标、只消费同类数据、或会执行用户明确排除步骤的流程不能推荐。若没有完整匹配项，recommendations 必须为空。即使完整匹配的业务流程尚未原子化，也应保留正确 recommendation，同时令 candidates 为空。
1. rank 必须唯一，1 最贴合；第一条必须是覆盖完整目标的首选链，其余必须是覆盖同一完整目标的不同工具组合、终点侧重或数据资产组合。用户未指定单一终点时，若存在合法替代方案必须保留 rank 2/3；不要为了凑数复制、截短或给出明显不完整的链。
2. 每个 input 名、from.output 名、tool_id 必须逐字匹配目录。tool_id 只能取每行开头 `-` 后、第一根 `|` 前的小写名称（如 fastp、star、samtools）；T001/T002 之类编号不是 tool_id，绝对不能输出。from 只能引用前序 step；每条 from 和 depends_on 都必须存在对应 NEXT 边，数据连接还必须匹配目录中的 output->input 数据边。
3. 除首个根步骤外，每步必须通过 from 或 depends_on 与前序相连。
4. raw count 与 TPM/FPKM 不可互换；uBAM 不等于 aligned BAM；STAR transcriptome_bam 只给 RSEM，aligned_bam 才能给 SAMtools。STAR 的 clean_fastq_read 是可承载双端 R1/R2 的成对 reads bundle；不要因为目录只有一个语义槽就把双端 RNA-seq 判为不支持。
4a. candidates 先按 Neo4j 内部 tool/slot/NEXT 合同生成；MCP 会把通过的链转换为公开执行端 tool_id 和 Knowledge Card I/O，并原样回验。不得输出执行端命名空间中的 input/output，也不得混用两套 tool_id；候选必须在公开合同回验后仍然成立。
5. reference/index/annotation 等执行端管理资产使用 reference_file。用户样本数据必须明确 asset_role；不要把运行参数当资产。
6. 用户写出的“只要、不要、不做、不能修改、已有、只有”都是硬约束。不得增加被排除步骤，不得用其他 assay 的流程兜底，也不得把已有结果倒推成原始输入。若输入与方法冲突（例如 MAF 做 STAR、RNA-seq 用 DNA 体细胞流程），recommendations 和 candidates 都必须为空并说明冲突。
6a. 用户不需要写出每一步工具名。若用户只描述 assay、输入数据和最终目标（例如“完整 bulk RNA-seq 分析并得到表达矩阵”），必须根据 Neo4j 的 tool、slot、artifact 和 NEXT/data 边反推出完整合法链；不能因为没有出现 STAR、SAMtools 等字样就拒绝或只返回空流程。只有在存在多个终点或方法分支时，才按用户明确约束和候选匹配度排序。
6b. **用户逐字点名的工具，目录里没有，就不许拿目录里的同类工具顶替。**点名的形式不限于第 6 条那几个词：“把 A 换成 B”“用 B 代替 A”“比对改用 B”“用 B 做定量”都是点名，一样是硬约束。这类需求正确的输出是 candidates 为空 + unsupported_kind=`not_atomized`，unsupported_reason 里写清点名的是哪个工具、目录里没有它。绝对禁止的做法是照常生成一条标准链、还把用户要求换掉的那个工具留在链里，然后标 ready——用户要 Salmon 拿到 RSEM、要 HISAT2 拿到 STAR，链本身合法、终产物也对得上，光看回包发现不了，这是最难查的一类错。注意两处不适用：其一，用户点的工具目录里**有**（如 fastp 换 trim_galore），照常按新工具生成链；其二，MultiQC 见下方边界条目，那条要求略去该步、其余照常，优先级高于本条。本条也不跟 6a 冲突——6a 管的是用户**没**点工具名的情形。另外，这种情况下 recommendations 同样要看第 6 条：如果目录里唯一匹配的业务流程内部就是用被点名要换掉的那个工具跑的（如 rnaseq_singletask 内置 STAR/RSEM），它并不满足用户的要求，不能作为推荐端出去，recommendations 也应为空。这一点不与 0b 冲突——0b 说的是业务流程**确实能做**这件事、只是没原子化；这里是业务流程根本做的就是用户排除掉的那套。
7. 不得从“一对双端 FASTQ”推断 tumor/normal。只有用户明确说明 tumor-normal 配对，或明确给出两个样本及其 tumor/normal 角色时，才能推荐 wes_somatic_pair 或生成四 FASTQ 配对链；缺少角色时应说明样本布局不足，不能自行补角色。
8. 最终产物是完整性门禁：若用户要求的最后产物需要未登记工具或当前合同无法到达，整条 candidates 必须为空，不能返回只做到上游中间产物的前缀链。pipeline recommendation 只是业务信息，不等于 atomic candidate 可执行。唯一例外是 MultiQC/QC 汇总，见下方边界条目。
9. 图谱只到文件级，没有基因、位点、通路这类内容维度，因此无法判断用户提到的基因或靶点是否真实存在、是否出现在表达矩阵里。match_note 里不得出现“可将目标基因替换为 XXX”“支持该基因”这类断言，也不得默认用户写出的符号就是合法基因名。需要提到时只能陈述流程本身按指定基因分层，不对该符号的有效性表态。

当前目录/执行合同的已知边界：
- 这些边界是 candidates 生成前的强制短路条件，优先级高于目录中显示的 NEXT。命中后必须直接输出 `"candidates": []`，不得先尝试构造步骤、不得输出“理论可行但会被校验器拒绝”的候选。
- paired-end FASTQ 的 FastQC 当前只有单一泛化 raw_fastq_read 槽，无法忠实表达 R1/R2 两个独立输入；禁止创建 fastqc_r1/fastqc_r2 两个并行根，也禁止只取一个 mate 冒充双端质控。若用户只要求双端 FastQC/质控且不允许修剪，candidates 为空。
- 当前 Knowledge Card 合同尚不能把 GATK 的 VCF 及 index 按 BCFtools 所需槽位传递。仅当用户明确要求过滤 VCF、标准化 VCF 或功能注释 VCF（即路径必须经过 GATK -> BCFtools 或 GATK -> BCFtools -> SnpEff）时才命中本条，此时 candidates 必须为空，即使 Neo4j 目录显示这些 NEXT 也不能生成这些步骤。反过来，只要终点是 GATK 直接产出的变异 VCF（包括 tumor-normal 配对的体细胞突变检测/somatic variant calling），就不属于本条边界，必须照常生成到 GATK 为止的完整链，不得以"后续还要过滤"为由清空 candidates。
- 单样本 GATK 的 sorted_dedup_bam 目录槽虽存在，但当前外部 Knowledge Card 只支持 tumor-normal 四槽形式；单样本 GATK candidates 为空。
- 仅针对"从配对 tumor-normal FASTQ 做体细胞变异检测"这一种需求：它由业务流程 wes_somatic_pair 以整卡形式交付，一次提交四个 FASTQ 加 interval_list，内部完成质控、比对、Mutect2、过滤、注释和 QC 汇总。这类需求只给出 wes_somatic_pair 的 recommendation，candidates 为空，不要再拆成 fastp/bwa/samtools/gatk 的原子链。本条不影响其他任何流程：CNV、表达、富集、生存、单细胞等业务流程照常按第 0 条推荐，不要因为输入是 BAM 或没写明 tumor/normal 就拒绝推荐它们。
- 多样本 QC 汇总（MultiQC）不属于原子链的表达范围，目录里也没有它。任何 candidate 都不得输出 tool_id 为 multiqc 的步骤，也不得让任何步骤 depends_on 或 from 引用 multiqc。用户即使逐字点名 MultiQC 或“QC 汇总报告”，也只是把这一步从链中略去、其余步骤照常完整生成；绝不能因为无法表达 MultiQC 就令 candidates 为空，本条不受第 8 条最终产物门禁约束。各步骤自身的 QC 报告仍由执行端产出。
- FastQC 输出的是 quality_control_report，不是 reads。`FastQC -> STAR` 没有 NEXT 且数据类型不相容，绝对禁止；若需要先做 FastQC 再做 STAR，中间必须使用目录允许的 fastp 或 trim_galore，并由其 clean_fastq_read 连接 STAR。任何 depends_on 也必须逐项出现在 source 的 order_next/data_next 中，不能用“仅表示顺序”为理由越过 NEXT。

配对 tumor/normal 的硬约束：
- GATK 输入有两个互斥变体。单样本分析必须且只能绑定 sorted_dedup_bam，禁止使用 tumor_bam/tumor_bai/normal_bam/normal_bai；只有明确的 tumor-normal 配对分析才使用下面的四槽变体。
- step 是“工具 x 样本”实例。fastqc/fastp/trim_galore/bwa/star/samtools 等单样本步骤必须分别生成 _tumor 和 _normal 两条链，不能提前合并，也不能交叉引用。
- 两侧都完成独立比对和 BAM 处理后才能汇合。汇合 GATK 只出现一次，并且必须同时精确绑定 tumor_bam、tumor_bai、normal_bam、normal_bai 四个注册槽；后续 bcftools/snpeff 等汇合步骤也只出现一次。
- 每个样本的 R1/R2 必须保持 mate 和 sample_role 一致，不能按文件列表位置猜测。

不支持规则：
- 若完整需求需要当前 atomic 目录尚未拆出的能力，例如差异表达、GO/KEGG/Reactome 富集、WGCNA 共表达网络、生存分析或其他未登记方法，candidates 必须为空，并在 unsupported_reason 明确说明“这类分析尚未原子化，暂不支持”。
- 若目录槽位或 NEXT 边无法忠实表达目标，也返回空 candidates 和具体 unsupported_reason；禁止编造工具、槽位、边或内部步骤。
- candidates 非空时 unsupported_reason 必须为 null。
- candidates 为空时必须用一句具体原因填写 unsupported_reason；不能只写“无法生成”，应指出是输入冲突、样本角色不足、未原子化、槽位缺失或执行合同缺口。recommendations 非空也不能省略该原因，因为业务流程信息不等于原子候选可执行。
- 同时必须填 unsupported_kind，只能取下面五个值之一。它区分的是"这个结论要不要看工具目录才成立"，服务端据此决定目录不可用时能不能沿用你这句话：
  - `out_of_scope`：不看目录也成立。请求根本不是可编排的生信分析——闲聊、常识问答、写代码、医疗诊断建议，或者要查病人个体的年龄/性别/病史/联系方式这类隐私信息（本服务只做流程编排，不提供个体层面的临床数据查询）。
  - `no_data`：不看目录也成立。图谱里没有用户点名的队列/癌种/样本。
  - `input_conflict`：不看目录也成立。用户给的输入和想要的产物自相矛盾（如只有 MAF 却要做比对）。
  - `not_atomized`：**要看目录**。目录里没有能覆盖这个需求的 atomic tool。
  - `contract_gap`：**要看目录**。目录里有工具，但槽位或 NEXT 边表达不了这条链。
- candidates 非空时 unsupported_kind 必须为 null。

癌种判定（disease 字段，必填）：
- 举例：`肝癌 HER2 表达和 PFS` → `{"status":"matched","term":"肝癌","study_accessions":["HRA001272","HRA001748","HRA001749","HRA006499"]}`；`NSCLC 的 TPM 做免疫浸润` → `{"status":"matched","term":"NSCLC","study_accessions":["HRA005191"]}`；`肝硬化患者的免疫浸润` → `{"status":"not_available","term":"肝硬化","study_accessions":[]}`；`双端 RNA-seq FASTQ 做上游分析` → `{"status":"unspecified","term":null,"study_accessions":[]}`。
- 这一层只做语义识别，不要用关键词去猜。零宽字符、全角半角、繁体、错别字、中英混写、缩写（NSCLC=非小细胞肺癌、HCC=肝细胞癌、ESCC=食管鳞癌、AML=急性髓系白血病、GBM=胶质母细胞瘤、NPC=鼻咽癌、CRC=结直肠癌）都要能认出来。
- `study_accessions` 只能从下方“可用队列清单”里选，一个字都不能编。同一癌种对应多个队列时全部列出。
- 用户说的癌种在清单里没有（如胰腺癌、前列腺癌、卵巢癌、乳腺癌、胃癌）→ `not_available`，`study_accessions` 为空数组。
- 用户说的根本不是癌种（肝硬化、糖尿病、健康人群）→ 同样 `not_available`，别硬往器官相近的癌种上靠。肝硬化不是肝癌。
- 一句话里出现多个癌种时，以用户真正要分析的那个为准。例如“前列腺癌能不能参考肝癌那套流程”问的是前列腺癌，应判 not_available，不能给肝癌队列。
- 用户完全没提癌种 → `unspecified`，`study_accessions` 为空数组；这不是错误，只是不施加队列过滤。

可用队列清单（癌种判定的唯一合法取值范围）：
''' + "\n".join(self._cohort_menu_lines()) + '''

Neo4j atomic 方法目录：
''' + "\n".join(self._method_menu_lines()) + '''

业务 pipeline 目录（其中 missing_from_neo4j 仅可作为信息推荐，不可进入 candidates）：
''' + "\n".join(self._business_pipeline_menu_lines()) + '''

已审核的“问题 => 业务 pipeline”参考样例：
''' + prompt_examples()
        raw = _lazy_call_llm(prompt, f"用户需求：{text}")
        if not isinstance(raw, dict):
            return None, {
                "used": False,
                "status": "failed_or_unavailable",
                "calls": 1,
                "stages": ["atomic_candidate_generation"],
            }
        decision, metadata = self._consume_llm_result(
            raw, "atomic_candidate_generation"
        )
        metadata["calls"] = 1
        return decision, metadata

    def _top3_plan(
        self,
        text: str,
        decision: Optional[Dict[str, Any]],
        metadata: Dict[str, Any],
        top_k: int,
    ) -> Dict[str, Any]:
        intent = self.router._rule_intent(text)
        # 癌种以规划器的语义判定为准，关键词表退居降级路径。规则法认不出零宽字符、
        # 缩写、繁体和错别字，也分不清「肝硬化」和「肝癌」，每补一种写法就要加一张
        # 表；这一层本来就在调 LLM，判定跟着同一次调用回来，不额外多一个往返。
        disease = self._llm_disease(decision) or {
            # 规划器没跑或没给出可解析的判定时，只能说"不知道"，不能退回关键词猜测。
            "status": "unspecified", "term": None,
            "study_accessions": [], "source": "unavailable",
        }
        intent = {
            **intent,
            "disease_status": disease["status"],
            "disease_studies": disease["study_accessions"],
            "disease_term": disease["term"],
            "disease_source": disease["source"],
        }
        raw_candidates = (decision or {}).get("candidates") or []
        raw_candidates = self._strip_multiqc_from_candidates(raw_candidates)
        normalized = self._normalize_ranked_candidates(raw_candidates)
        accepted: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        for raw_candidate in normalized:
            methods, validation = self._validate_custom_steps(
                raw_candidate.get("steps") or []
            )
            if not validation.get("ok"):
                rejected.append({
                    "rank": raw_candidate["rank"],
                    "stage": "validation",
                    "errors": list(validation.get("errors") or []),
                })
                continue
            candidate, rejection = self._build_top3_candidate(
                text, intent, raw_candidate, methods, validation
            )
            if candidate:
                accepted.append(candidate)
            elif rejection:
                rejected.append(rejection)
        accepted.sort(key=lambda item: item["rank"])
        accepted = accepted[: min(3, max(1, int(top_k)))]
        recommendations = self._build_recommendations(
            text,
            intent,
            decision or {},
            min(3, max(1, int(top_k))),
        )

        # Keep the common reviewed RNA-seq upstream path usable whenever no LLM
        # candidate survives, not only when the LLM returned nothing at all: the
        # same query otherwise flips between ready and information depending on
        # which chain the model happened to emit. The chain is still built from
        # the Neo4j atomic registry and passes the same data/contract gates as
        # an LLM-produced candidate, so this cannot admit an invalid chain.
        #
        # 但"合法"不等于"是这道题的答案"。0822 实测：问「用 HISAT2 代替 STAR 做比对」，
        # 规划器完全判对了——analysis.checks 原话是"用户逐字点名 HISAT2，目录无该工具，
        # 按硬约束清空 candidates"，candidates 交的就是空。然后这段回退凭关键词
        # （命中 rna-seq、没命中 maf/vcf/wes）把标准链塞了回去，链里赫然还是 star，
        # 整个回包标 ready、unsupported_reason 为 null。用户要 HISAT2 拿到 STAR，
        # 要 Salmon 拿到 RSEM，链合法、终产物也对得上，光看回包发现不了。
        #
        # 所以判据不是"规划器交没交链"，而是"规划器有没有**主动**拒答"：它给了拒答
        # 理由（unsupported_reason / unsupported_kind），就是看着这道题做的决定，必须
        # 原样透出去；它什么都没产出（decision 为 None、解析失败、API 挂了），才是这段
        # 回退要兜的"空输出"——test_16 锁的正是后者（self.top3(None)），test_15 锁的是
        # 前者。两条测试早就把意图分清了，缺的只是一个能区分它们的判据。
        if not accepted and not self._planner_declined(decision) and self._eligible_rnaseq_fallback(
            text, intent, recommendations
        ):
            fallback = {
                "rank": 1,
                "match_note": "确定性回退：双端 RNA-seq FASTQ 的质控、比对、表达定量和计数流程。",
                "steps": self._deterministic_rnaseq_candidate_steps(),
            }
            fallback_methods, fallback_validation = self._validate_custom_steps(fallback["steps"])
            if fallback_validation.get("ok"):
                candidate, rejection = self._build_top3_candidate(
                    text, intent, fallback, fallback_methods, fallback_validation
                )
                if candidate:
                    accepted.append(candidate)
                    metadata = dict(metadata)
                    metadata["deterministic_fallback"] = "rnaseq_upstream_from_neo4j_contract"
                elif rejection:
                    rejected.append(rejection)

        unsupported_reason = str(
            (decision or {}).get("unsupported_reason") or ""
        ).strip() or None
        # 规划器给的拒答理由分两类：一类不看工具目录也成立（隐私查询、非生信、
        # 图里没这个队列、输入自相矛盾），一类必须看目录才成立（未原子化、槽位
        # 表达不了）。目录为空时只有后者会被污染，前者照说不误。
        unsupported_kind = str(
            (decision or {}).get("unsupported_kind") or ""
        ).strip().lower()
        atomic_unavailable_reason = unsupported_reason
        if accepted:
            selection_status = "ready"
            unsupported_reason = None
        elif recommendations:
            selection_status = "information"
            unsupported_reason = None
        elif unsupported_reason:
            selection_status = "unsupported"
        else:
            selection_status = "no_candidate"
            # 这句会原样显示给终端用户，所以说的是"这个需求怎么了"，而不是内部哪个
            # 环节没产出。规划器空转对用户没有意义，他要知道的是该改问法还是换需求。
            unsupported_reason = (
                "已有工具能覆盖这个需求的一部分，但拼不出一条从你的输入到目标结果的完整链路，"
                "请补充输入数据类型或缩小分析目标。"
                if normalized else
                "没能把这个需求对应到任何已登记的分析能力；如果确实是生信分析需求，"
                "请说明输入数据类型（如 FASTQ / BAM / 表达矩阵 / MAF）和想要的结果。"
            )
        if not accepted and not atomic_unavailable_reason and rejected:
            rejected_stages = ", ".join(sorted({
                str(item.get("stage") or "validation") for item in rejected
            }))
            atomic_unavailable_reason = (
                f"LLM 生成的原子候选未通过 {rejected_stages}；"
                "业务流程推荐仅作为信息展示。"
            )
        # 癌种对不上时，用户要听到的是"没有这个癌种的队列"，而不是"没有完整的
        # 数据组合"——后者会让人以为再补一句输入格式就能跑起来。
        unavailable_disease = (
            intent.get("disease_term") if intent.get("disease_status") == "not_available" else None
        )
        if not accepted and unavailable_disease:
            atomic_unavailable_reason = (
                f"图谱里没有登记「{unavailable_disease}」的队列，"
                "不能用其它癌种的数据代替，因此没有可提交的链路。"
            )
            if selection_status != "information":
                unsupported_reason = atomic_unavailable_reason

        # 原子目录空的时候，"当前原子目录中没有对应工具"这类话一句都不能算数。
        # 0822 实测："HRA001272 的 RNA-seq 做 GO/KEGG 富集"拿到的回答是「差异表达与
        # GO/KEGG 通路富集这类分析尚未原子化，当前原子目录中没有对应工具」——具体、
        # 笃定、听着完全在理，但那会儿 registered_method_count=0，它根本不知道富集
        # 有没有原子化。用户会照这句话得出"产品不支持富集"的结论，比报错还糟。
        #
        # 但也不能一律改口。问"HRA001272 里病人的年龄分别是多少"该答的是"本服务不
        # 提供个体隐私数据"，改成"图谱没连上，恢复后重试"等于暗示连上就给查——那是
        # 拿一个错误答案换另一个错误答案。所以只覆盖依赖目录的那两类结论。
        CATALOG_DEPENDENT_KINDS = {"", "not_atomized", "contract_gap"}
        atomic_catalog_state = self.registered_methods.unavailable_state(atomic_only=True)
        if (
            not accepted
            and atomic_catalog_state
            and unsupported_kind in CATALOG_DEPENDENT_KINDS
        ):
            atomic_unavailable_reason = (
                f"原子工具目录为空（{atomic_catalog_state}），"
                "无法判断这个需求能否拆成原子链——这不是需求本身不受支持，"
                "请先恢复 Neo4j 图谱连接后重试。"
            )
            if selection_status in ("unsupported", "no_candidate"):
                unsupported_reason = atomic_unavailable_reason

        result = {
            "schema_version": "tool-chain/v2",
            "selection_status": selection_status,
            "candidate_count": len(accepted),
            "candidates": accepted,
            "recommendation_count": len(recommendations),
            "recommendations": recommendations,
            "unsupported_reason": unsupported_reason,
            "intent": {
                **intent,
                "query_text": text,
                "analysis_goal": intent.get("analysis_goal"),
                "requested_outputs": intent.get("requested_outputs") or [],
            },
            "planner_metadata": metadata,
            "analysis": (decision or {}).get("analysis"),
            "extensions": {
                "rejected_candidates": rejected,
                "unsupported_kind": unsupported_kind or None,
                "atomic_candidate_unavailable_reason": (
                    atomic_unavailable_reason if not accepted else None
                ),
                "method_catalog_status": {
                    **METHOD_CATALOG_STATUS,
                    "registered_method_count": len(self.registered_methods.methods),
                    # 给调用方一个可判定的标志，别让人去正则匹配上面那句中文。
                    "catalog_unavailable": not self.registered_methods.methods,
                    "graph_connected": self.registered_methods.connected,
                    "graph_error": self.registered_methods.error,
                },
            },
        }
        if accepted:
            result["answer"] = f"返回 {len(accepted)} 条通过校验且数据完整的原子工具候选链。"
        elif recommendations:
            result["answer"] = f"返回 {len(recommendations)} 条业务流程及其 Neo4j 数据信息。"
        else:
            result["answer"] = unsupported_reason
        return result

    def _allowed_pipeline_ids(self) -> List[str]:
        """Every business pipeline the model may recommend.

        The benchmark reference list alone would hide the pipelines 0811 added
        (cnvkit_cnv_clinical, km_survival, the WGCNA and scRNA families...),
        so a request they answer would come back unsupported even though the
        catalog registers them. Union the two and keep the order stable.
        """
        return sorted(
            set(reference_pipeline_ids()) | set(self.registered_methods.pipeline_methods)
        )

    def _business_pipeline_menu_lines(self) -> List[str]:
        known = self.registered_methods.pipeline_methods
        # 目录整个不可用时，"这条 pipeline 没在 Neo4j 里"对**任何**一条都不成立——
        # 我们不是查过之后没找到，是压根没查成。可 pipeline_id 本身来自本地
        # benchmark，不依赖图谱，所以清单照发，只是把注册状态标成"无从判断"。
        # 0822 实测这处标注会直接改变答案：目录空时"我有比对好的 BAM 和临床数据，
        # 想做 CNV 分析"连着三次拿到 rec=[]，而 cnvkit_cnv_clinical 就明晃晃在单子上。
        # 满屏 missing_from_neo4j 被模型读成了"这些都用不了"。
        catalog_state = self.registered_methods.unavailable_state()
        lines: List[str] = []
        if catalog_state:
            lines.append(
                f"（注意：{catalog_state}，下列流程的注册状态一律无从判断，"
                "不代表它们不可用。请照常按需求推荐，只是都当作信息推荐、不要进 candidates。）"
            )
        for pipeline_id in self._allowed_pipeline_ids():
            method = known.get(pipeline_id)
            if method:
                lines.append(
                    f"- {pipeline_id} | registered | {method.name} | {method.description}"
                )
            elif catalog_state:
                lines.append(f"- {pipeline_id} | 注册状态未知(目录不可用)")
            else:
                lines.append(f"- {pipeline_id} | missing_from_neo4j")
        return lines

    def _cohort_menu_lines(self) -> List[str]:
        """The closed set of cohorts the planner may bind a disease to.

        Handing the model the actual cohorts, rather than asking it for a free
        text disease name, is what makes the answer checkable: anything outside
        this list is a hallucination and gets dropped in `_llm_disease`.
        """
        study_by_id = getattr(self.router.matcher, "study_by_id", {}) or {}
        lines: List[str] = []
        for accession in sorted(study_by_id):
            row = study_by_id[accession] or {}
            tumor_type = str(row.get("tumor_type") or "").strip() or "未标注"
            title = str(row.get("title") or "").strip()
            lines.append(f"- {accession} | {tumor_type}" + (f" | {title[:40]}" if title else ""))
        return lines

    def _llm_disease(self, decision: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate the planner's disease call against the cohorts that exist.

        The model is good at reading `NSCLC`, 繁体, a typo or a zero-width space
        as a disease; it is not authoritative about which cohorts we hold. So
        the semantic half is taken from the model and the factual half is
        re-checked here: an accession that is not in the graph is dropped, and
        a `matched` verdict with nothing left standing degrades to
        `not_available` rather than silently binding whatever the retriever
        finds next.
        """
        raw = (decision or {}).get("disease")
        if not isinstance(raw, dict):
            return None
        status = str(raw.get("status") or "").strip().lower()
        if status not in {"matched", "not_available", "unspecified"}:
            return None
        study_by_id = getattr(self.router.matcher, "study_by_id", {}) or {}
        requested = [str(item).strip() for item in (raw.get("study_accessions") or []) if item]
        studies = [item for item in requested if item in study_by_id]
        hallucinated = sorted(set(requested) - set(studies))
        if status == "matched" and not studies:
            status = "not_available"
        return {
            "status": status,
            "term": str(raw.get("term") or "").strip() or None,
            "study_accessions": studies,
            "hallucinated_study_accessions": hallucinated,
            "source": "llm",
        }

    def _normalize_recommendation_values(self, values: Any) -> List[Dict[str, Any]]:
        if not isinstance(values, list):
            return []
        allowed = set(self._allowed_pipeline_ids())
        prepared: List[Dict[str, Any]] = []
        seen: Set[str] = set()
        for index, item in enumerate(values[:5], 1):
            if not isinstance(item, dict):
                continue
            pipeline_id = str(item.get("pipeline_id") or "").strip()
            if pipeline_id not in allowed or pipeline_id in seen:
                continue
            seen.add(pipeline_id)
            try:
                rank = max(1, int(item.get("rank") or index))
            except (TypeError, ValueError):
                rank = index
            prepared.append({
                "rank": rank,
                "pipeline_id": pipeline_id,
                "match_note": str(item.get("match_note") or "").strip(),
            })
        prepared.sort(key=lambda item: item["rank"])
        for rank, item in enumerate(prepared, 1):
            item["rank"] = rank
        return prepared

    @staticmethod
    def _planner_declined(decision: Optional[Dict[str, Any]]) -> bool:
        """规划器是不是**主动**拒的答。

        两处确定性回退（原子链回退、业务推荐回退）都拿它当闸门，区分的是同一件事：
        规划器交空，是"它看着这道题决定不给"，还是"它根本没产出"。前者必须照原样
        透出去，后者才轮到确定性规则兜底。

        判据是它有没有留下拒答理由。提示词里写死了"candidates 为空时必须用一句具体
        原因填写 unsupported_reason"并同时要求填 unsupported_kind，所以有理由 = 它
        做过判断；decision 整个是 None（解析失败、API 挂了）时两个字段都取不到，
        自然为 False。
        """
        if not decision:
            return False
        return bool(
            str(decision.get("unsupported_reason") or "").strip()
            or str(decision.get("unsupported_kind") or "").strip()
        )

    def _build_recommendations(
        self,
        text: str,
        intent: Dict[str, Any],
        decision: Dict[str, Any],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        reference = exact_reference(text)
        recommendation_source = "llm+neo4j"
        if reference:
            recommendation_source = "reviewed_reference+neo4j"
            values = [{
                "rank": 1,
                "pipeline_id": reference["expected_pipeline_id"],
                "match_note": "命中已审核的 96 例问题-数据-工具基准。",
            }]
        else:
            values = self._normalize_recommendation_values(
                decision.get("recommendations") or []
            )
            # 规划器主动给了拒答理由，就是它**看着**这道题决定不推荐的（点名了目录里
            # 没有的工具、输入自相矛盾、癌种不在库里）。这种时候按关键词补一条
            # rnaseq_singletask，等于把它排除掉的东西又端回来：0822 实测问「用 HISAT2
            # 代替 STAR」，规划器 recommendations 和 candidates 都交了空、理由写的是
            # "现有 RNA-seq 上游流程均依赖 STAR，会执行用户排除的步骤"，这条规则却
            # 补上了 rnaseq_singletask——正是那条依赖 STAR 的流程。附带把顶层
            # selection_status 从 unsupported 顶成了 information，"做不了"变成"给你推荐"。
            #
            # 规划器什么都没说就交空（漏填、解析失败、API 挂了），才是这条确定性规则
            # 要兜的；它明确说了为什么不推荐，就得听它的。
            if (
                not values
                and not self._planner_declined(decision)
                and self._deterministic_pipeline_recommendation(text, intent)
            ):
                values = [{
                    "rank": 1,
                    "pipeline_id": "rnaseq_singletask",
                    "match_note": "确定性规则识别为双端 bulk RNA-seq 上游质控和表达定量。",
                }]
                recommendation_source = "deterministic_rule+neo4j"
        recommendations: List[Dict[str, Any]] = []
        for value in values[:top_k]:
            pipeline_id = value["pipeline_id"]
            method = self.registered_methods.pipeline_methods.get(pipeline_id)
            data = self._recommendation_data(
                intent,
                pipeline_id,
                reference if reference and pipeline_id == reference.get("expected_pipeline_id") else None,
            )
            match_key = json.dumps(
                {"query": text, "pipeline_id": pipeline_id, "rank": value["rank"]},
                ensure_ascii=False,
                sort_keys=True,
            )
            execution_params, execution_params_missing = self._execution_params(method, data)
            # Resolve params for every offered data set too, so switching the
            # selection in the UI does not need another round trip and the
            # picker can grey out the ones that cannot actually be submitted.
            for alternative in data.get("alternatives") or []:
                alt_params, alt_missing = self._execution_params(method, alternative)
                alternative["execution_params"] = alt_params
                alternative["execution_params_missing"] = alt_missing
                alternative["submittable"] = bool(alt_params) and not alt_missing
            recommendations.append({
                "rank": value["rank"],
                "match_id": "recommendation-" + hashlib.sha256(
                    match_key.encode("utf-8")
                ).hexdigest()[:16],
                "pipeline_id": pipeline_id,
                "match_note": value.get("match_note") or "",
                "tool": self._recommendation_tool(pipeline_id, method),
                "data": data,
                "execution_params": execution_params,
                "execution_params_missing": execution_params_missing,
                "unvalidated_parameters": self._unvalidated_parameters(text, method),
                "source": recommendation_source,
                "reference_case_id": reference.get("case_id") if reference else None,
            })
        return recommendations

    # 一眼看去像基因符号、但其实是检测方法或指标的词。图谱里没有基因维度，
    # 只能靠这份排除表把明显不是基因的词滤掉，剩下的一律按"未校验"申报。
    _NON_GENE_TOKENS = frozenset({
        "PFS", "OS", "DFS", "EFS", "TMB", "MSI", "CNV", "SNV", "SV", "QC",
        "RNA", "DNA", "MRNA", "CDNA", "WES", "WGS", "WXS", "MAF", "BAM", "SAM",
        "VCF", "TPM", "FPKM", "RPKM", "FASTQ", "FQ", "KM", "HR", "CI", "TSV",
        "CSV", "XLS", "XLSX", "PDF", "PNG", "GO", "KEGG", "GSEA", "WGCNA",
        "IOBR", "STAR", "RSEM", "GATK", "BWA", "ID", "AI", "UI", "API",
    })
    # 长度放到 24：HGNC 符号最长十几个字符，而用户手打的目标基因未必是合法符号
    # （`FAKEGENE404` 就有 11 位）。这里的作用是把用户写了什么原样带出来交给下游
    # 校验，不是判断它是否合法，所以宁可宽一点也不要漏。
    _GENE_TOKEN_RE = re.compile(r"\b([A-Z][A-Z0-9-]{1,23})\b")
    # 真正接受"用户指定某个基因"的流程，描述里都会明说是特定/指定/目标基因。
    # 只搜"基因"会把 25 个流程全捞进来——基因表达矩阵、差异基因、hub 基因、
    # 突变基因 Oncoplot 说的都是分析内容，不是可传参数。
    _GENE_PARAM_RE = re.compile(
        r"(特定|指定|目标|某个|自选)基因|基因（默认|按基因|target\s+gene|gene\s+of\s+interest",
        re.I,
    )

    def _unvalidated_parameters(
        self,
        text: str,
        method: Optional[RegisteredMethod],
    ) -> List[Dict[str, Any]]:
        """Declare the parameters this backend cannot check.

        Several pipelines take a target gene and stratify samples by its
        expression. The graph stops at the file level -- there are no gene,
        locus or pathway nodes, and nothing here opens a TPM matrix -- so
        whether `XXX6` is a real gene, and whether it appears in the matrix
        the pipeline will read, is simply not knowable from this side.

        Silence would let a made-up symbol travel all the way into a
        submission looking exactly like a verified one. Instead the gap is
        stated in the payload, so whoever builds the submission has to either
        check it or show the user that nobody did.
        """
        if not method:
            return []
        description = f"{method.description or ''} {method.name or ''}"
        if not self._GENE_PARAM_RE.search(description):
            return []
        declared = {
            str(slot.get("builder_param") or slot.get("name") or "")
            for slot in (method.inputs or [])
        }
        if "gene" in declared:
            return []  # 真按槽位声明了就不用这条旁路
        symbols = [
            token for token in self._GENE_TOKEN_RE.findall(str(text or ""))
            if token not in self._NON_GENE_TOKENS
            and not token.startswith("HRA")
            and not token.startswith("HRS")
        ]
        return [{
            "parameter": "gene",
            "value_from_question": symbols[0] if symbols else None,
            "validated": False,
            "reason": (
                "图谱只到文件级，没有基因维度，本服务无法确认该符号是真实基因、"
                "也无法确认它出现在流程要读取的表达矩阵里。"
            ),
            "action": "提交前请由执行端或调用方校验；未校验就执行可能得到空结果或报错。",
        }]

    @staticmethod
    def _deterministic_pipeline_recommendation(
        text: str,
        intent: Dict[str, Any],
    ) -> bool:
        normalized = re.sub(r"\s+", "", str(text or "").lower())
        if any(term in normalized for term in ("maf", "vcf", "wes", "体细胞突变", "肿瘤-正常")):
            return False
        if "rna" not in normalized and "rnaseq" not in normalized:
            return False
        if "fastqc" in normalized and not any(
            term in normalized for term in ("定量", "表达", "star", "rsem", "完整流程")
        ):
            return False
        if not any(term in normalized for term in ("fastq", "fq.gz", "表达定量", "上游", "star", "rsem")):
            return False
        return str(intent.get("omics_type") or "").lower() in {"bulk rna-seq", "rna-seq", "rnaseq"}

    def _recommendation_tool(
        self,
        pipeline_id: str,
        method: Optional[RegisteredMethod],
    ) -> Dict[str, Any]:
        if not method:
            return {
                "tool_id": pipeline_id,
                "catalog_status": "missing_from_neo4j",
                "source": "neo4j",
            }
        return {
            "tool_id": method.tool_id,
            "catalog_id": method.catalog_id,
            "tool_kind": method.tool_kind,
            "name": method.name,
            "description": method.description,
            "inputs": method.inputs,
            "outputs": method.outputs,
            "catalog_status": "registered",
            "source": "neo4j",
        }

    def _reject_disease_mismatch(
        self,
        intent: Dict[str, Any],
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Refuse a cohort that is not the cancer the user asked about.

        Retrieval already filters cohorts by disease, but two paths get around
        it. A benchmark hit resolves its files by name and never goes through
        the filter at all. And a disease the alias table cannot map leaves the
        filter with nothing to match on, so every cohort passes -- that is how
        a question about 胰腺癌 came back bound to a glioma cohort, with all
        three parameters filled and ready to submit.

        A wrong cohort is worse than no cohort: the run succeeds and produces
        numbers about the wrong disease. So the binding is dropped rather than
        flagged, and the reason says which cohort was rejected and why.
        """
        studies = [str(item) for item in data.get("study_accessions") or [] if item]
        if not studies:
            return data
        matcher = self.router.matcher

        # 规划器判定优先：它认得缩写、繁体、错别字和零宽字符，也认得
        # 「肝硬化不是肝癌」。这里只核对它给的队列真实存在（已在 _llm_disease
        # 做过），并按判定决定绑不绑。
        status = intent.get("disease_status")
        if status:
            if status == "unspecified":
                return data
            allowed = set(intent.get("disease_studies") or [])
            mismatched = [study for study in studies if study not in allowed]
            if status == "matched" and not mismatched:
                return data
            study_by_id = getattr(matcher, "study_by_id", {}) or {}
            named = ", ".join(
                f"{study}（{study_by_id.get(study, {}).get('tumor_type') or '癌种未标注'}）"
                for study in (mismatched or studies)
            )
            term = intent.get("disease_term") or "该疾病"
            if status == "not_available":
                reason = (
                    f"问题问的是{term}，图谱里没有这个癌种的队列，"
                    f"不能拿 {named} 顶替。"
                )
            else:
                reason = f"问题问的是{term}，但匹配到的队列是 {named}，不予绑定。"
            return self._no_cohort_result_from(data, studies, reason)

        return data

    @staticmethod
    def _no_cohort_result_from(
        data: Dict[str, Any],
        rejected: Sequence[str],
        reason: str,
    ) -> Dict[str, Any]:
        """Strip the cohort binding but keep why it was stripped."""
        return {
            **data,
            "status": "cohort_disease_mismatch",
            "assets": [],
            "matched_count": 0,
            "alternatives": [],
            "rejected_study_accessions": list(rejected),
            "study_accessions": [],
            "cohort_rejection_reason": reason,
        }

    def _recommendation_data(
        self,
        intent: Dict[str, Any],
        pipeline_id: str,
        reference: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if reference:
            resolved = self.router.matcher.lookup_files(
                reference.get("expected_data") or []
            )
            return self._reject_disease_mismatch(intent, {
                **resolved,
                "source": "neo4j",
                "reference_asset_names": list(reference.get("expected_data") or []),
            })

        evidence_matcher = getattr(
            self.router.matcher, "neo4j_matcher", self.router.matcher
        )
        matched = evidence_matcher.match(
            intent, [{"pipeline_id": pipeline_id}], limit=100
        )
        combinations = matched.get("data_combinations") or []
        if not combinations:
            assets, studies, missing_roles = self._partial_recommendation_assets(
                evidence_matcher, matched, pipeline_id
            )
            return {
                "status": "missing_from_graph",
                "source": "neo4j",
                "assets": assets,
                "matched_count": len(assets),
                "expected_count": evidence_matcher._required_file_count(pipeline_id),
                "missing_asset_names": [],
                "missing_data_roles": missing_roles,
                "study_accessions": studies,
            }
        files = combinations[0].get("files") or []
        assets = [_evidence_asset(item, evidence_matcher._file_role) for item in files]
        studies = sorted({str(item.get("study_accession")) for item in files if item.get("study_accession")})
        return self._reject_disease_mismatch(intent, {
            "status": "available",
            "source": "neo4j",
            "assets": assets,
            "matched_count": len(assets),
            "expected_count": len(assets),
            "missing_asset_names": [],
            "study_accessions": studies,
            "alternatives": self._dataset_alternatives(evidence_matcher, combinations),
        })

    def _study_role_counts(self, matcher: Any) -> Dict[str, Dict[str, int]]:
        """Per study, how many T1 files resolve to a tumor / normal sample role.

        Cached on the matcher: the caller may ask for several pipelines in one
        request and this walks every T1 row.
        """
        cached = getattr(matcher, "_study_role_counts_cache", None)
        if cached is not None:
            return cached
        counts: Dict[str, Dict[str, int]] = {}
        for row in getattr(matcher, "t1", []) or []:
            study = str(row.get("study_accession") or "")
            if not study:
                continue
            role = _sample_role(row)
            bucket = counts.setdefault(study, {"tumor": 0, "normal": 0, "unresolved": 0})
            bucket[role if role in {"tumor", "normal"} else "unresolved"] += 1
        try:
            matcher._study_role_counts_cache = counts
        except Exception:  # noqa: BLE001 - a matcher that rejects attributes still works
            pass
        return counts

    def _dataset_alternatives(
        self,
        matcher: Any,
        combinations: Sequence[Dict[str, Any]],
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Expose the other data sets this recommendation could have run on.

        The matcher already ranks every complete combination; only the first was
        ever returned, so the caller had no way to offer a different study. Each
        entry carries what a picker needs: study identity for display, the files
        themselves, and whether tumor/normal roles can be resolved for that study
        (which decides if a paired or grouped analysis is actually runnable).
        """
        role_counts = self._study_role_counts(matcher)
        study_by_id = getattr(matcher, "study_by_id", {}) or {}
        alternatives: List[Dict[str, Any]] = []
        for index, combination in enumerate(combinations[:limit]):
            files = combination.get("files") or []
            if not files:
                continue
            studies = sorted({
                str(item.get("study_accession"))
                for item in files if item.get("study_accession")
            })
            study = studies[0] if len(studies) == 1 else ""
            meta = study_by_id.get(study) or {}
            roles = role_counts.get(study) or {"tumor": 0, "normal": 0, "unresolved": 0}
            # Paired analyses yield several combinations inside one study, one
            # per patient, so the study alone would render as N identical rows.
            individual = str(combination.get("individual_accession") or "")
            label = " · ".join(
                part for part in (
                    study or "unknown",
                    str(meta.get("tumor_type") or ""),
                    f"个体 {individual}" if individual else "",
                ) if part
            )
            alternatives.append({
                "study_accession": study,
                "study_title": str(meta.get("title") or ""),
                "tumor_type": str(meta.get("tumor_type") or ""),
                "individual_accession": individual,
                "label": label,
                "selected": index == 0,
                "assets": [_evidence_asset(item, matcher._file_role) for item in files],
                "matched_count": len(files),
                "study_accessions": studies,
                "sample_roles": dict(roles),
                "role_resolved": roles["tumor"] > 0 and roles["normal"] > 0,
            })
        return alternatives

    @staticmethod
    def _real_execution_path(asset: Dict[str, Any]) -> str:
        """Return the asset's real filesystem path, or "" if it is not a
        confirmed path. ``data.assets`` from the graph carry ``file_path`` that
        for T2 products (maf/tsv/xlsx…) is a real ``/...`` path, but for T1
        fastq is either ``NOT_FOUND`` or the ``"<name> (<n> bytes)"`` placeholder
        (no real location in the upstream CSV). We never fabricate a path."""
        path = str(asset.get("file_path") or "").strip()
        if not path.startswith("/"):
            return ""
        if "NOT_FOUND" in path:
            return ""
        if re.search(r"\(\d+\s*bytes\)\s*$", path):
            return ""
        return path

    def _execution_asset_role(self, asset: Dict[str, Any]) -> str:
        """Canonical role for a ``data.assets`` item (which carries no
        ``input_role``), derived from file name + physical format + read pair,
        mapped into the same vocabulary as ``_canonical_asset_role``."""
        name = str(asset.get("files") or asset.get("name") or "")
        fmt = str(asset.get("format") or "").lower()
        read_pair = str(asset.get("read_pair") or "").lower()
        role = self._role_for_input(name)
        if role in {"fastq_r1", "fastq_r2", "fastq_file"}:
            if read_pair == "r1":
                return "fastq_r1"
            if read_pair == "r2":
                return "fastq_r2"
            return role
        if role != "data_file":
            return role
        # 单细胞对象只认 rds 这一种物理格式，不按文件名判。同一批研究里
        # `Matrix-h5`（10x 稀疏矩阵目录，format=dir）和 `03_sc_obj_final_anno.rds`
        # 都是单细胞产物、都在 scRNAseq 目录下，但只有后者是 Seurat 对象。原先两者
        # 都落到 `data_file`，于是 `lung_tme_annotation_cnv` 的 `input_rds` 会挑中
        # 那个 h5 目录并给出 `missing: []`——不是"取不到参数"，是取到了一个**错的**
        # 参数还说一个都不缺。执行端 readRDS 一个目录必然失败，而回包看不出异常。
        if fmt == "rds" or str(asset.get("file_path") or "").lower().endswith(".rds"):
            return "scrna_object"
        if "maf" in fmt:
            return "maf_file"
        if "vcf" in fmt:
            return "vcf_file"
        if "bam" in fmt:
            return "bam_file"
        if "fastq" in fmt or fmt.startswith("fq"):
            if read_pair == "r1":
                return "fastq_r1"
            if read_pair == "r2":
                return "fastq_r2"
            return "fastq_file"
        return "data_file"

    def _execution_params(
        self,
        method: Optional[RegisteredMethod],
        data: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Convert this recommendation's confirmed data assets into
        directly-usable PipelineBuilder params, keyed by the **real WDL param
        name** (``io_slot.builder_param``, e.g. ``maf_file``) — not the slot
        name and not ``wdl_target``. Only KG-confirmed file inputs with a real
        path are mapped; anything unresolved is reported in the missing list
        rather than guessed (no fabricated paths)."""
        params: Dict[str, Any] = {}
        missing: List[Dict[str, Any]] = []
        if method is None:
            # 返回空 params + **空** missing 等于说"这张卡零个参数、且一个都不缺"，
            # 消费方按 `not missing` 判可提交就会当成能提交。而 method 只从图谱目录
            # 来，目录一空每张卡都长这样。0822 probe C2（tumor-normal WES 体细胞突变）
            # 报的"整卡缺少参数绑定 tumor_r1/normal_r1..."就是这么来的：不是绑不上，
            # 是根本不知道有哪些槽位。缺什么说不出来，至少要说"说不出来"。
            missing.append({
                "param": None,
                "slot": None,
                "role": None,
                "reason": (
                    "method_not_in_catalog"
                    if self.registered_methods.all_methods
                    else "catalog_unavailable"
                ),
                "detail": self.registered_methods.unavailable_state()
                or "该 pipeline 未在 Neo4j 目录中注册，无法得知其输入槽位",
            })
            return params, missing
        assets = list((data or {}).get("assets") or [])
        usage: Dict[str, int] = {}
        tool_id = str(getattr(method, "tool_id", "") or "")
        for slot in method.inputs or []:
            slot_name = str(slot.get("name") or "")
            role = self._canonical_asset_role(slot_name, str(slot.get("input_role") or ""))
            builder_param = str(slot.get("builder_param") or "").strip()
            # 规则 4 的判据：这个参数是不是执行端自带（REFERENCE_RESOURCE_PARAMS）。
            # 不再用 canonical role == "reference_file" —— 那是按槽名关键字猜出来的，
            # 会把 `genome_annotation → gene_order` 这种"名字像参考、实际必须由用户
            # 给"的必需输入一并吞掉：既不映射也不报缺，回包看不出任何异常。
            is_reference = (tool_id, builder_param) in REFERENCE_RESOURCE_PARAMS
            if not builder_param:
                if str(slot.get("variant_alias_for") or "").strip():
                    # 别名行不是独立输入，只是旧槽名指向真实槽（bwa 的
                    # clean_fastq_read → clean_fastq_read_r1）。真实槽自己会报，
                    # 别名再报一次就是把同一件事说两遍，只会淹掉别的条目。
                    continue
                # 这里原来是无声 `continue`，注释断言"没有 builder_param 的槽都是
                # sample-lookup / 参考索引，卡片自带默认值"。那个断言在目录只收录 12 个
                # 全绑定工具时成立；0823 清点发现 128 个输入槽有 95 个为空，绝大多数是
                # 货真价实的数据输入——只是 io_slot.csv 里没抄上 WDL 绑定。
                #
                # 后果不是报错而是**静默少给参数**：师兄那边看到的是 execution_params={}
                # 加一份字段完整、看不出异常的回包，只能靠肉眼发现三个输入全空。
                # 参考文件仍然不报（师兄规则 4），其余一律走 missing——缺什么说不出来，
                # 至少要说"说不出来"，这和上面 method is None 那支是同一条原则。
                #
                # 这一支的"参考文件"只能按 canonical role 判，因为规则 4 的白名单键是
                # builder_param 而这里恰恰没有。所以再加一道 `is_reference` 是无效的，
                # 只能维持 role 判据——现状是这类槽 0 条（全仓清点：builder_param 为空
                # 且被判 reference_file 的输入槽为 0），真出现了得先补 builder_param。
                if role == "reference_file":
                    continue
                missing.append({
                    "param": None,
                    "slot": slot_name,
                    "role": role,
                    "reason": "slot_not_bound",
                    "detail": (
                        "该输入槽在 data/csv/catalog/io_slot.csv 里没有 builder_param，"
                        "无法映射到 WDL 参数；待确认清单见 docs/待确认_builder_param.md"
                    ),
                })
                continue
            if is_reference:
                # Reference/index resources (genome index, gtf, PoN, known-sites…)
                # are carried by the executor image — never map nor report them as
                # missing (师兄 rule 4). 判据是 REFERENCE_RESOURCE_PARAMS 这张显式
                # 白名单，不是槽名关键字；理由见该表上方的注释。
                continue
            # A whole-card pipeline can declare several slots of the same role
            # that differ only by sample_role (wes_somatic_pair's tumor_r1 vs
            # normal_r1). Round-robin over role alone would assign them by list
            # order, i.e. by luck; honour the declared dimension instead.
            dimension = str(slot.get("dimension") or "")
            dimension_value = str(slot.get("dimension_value") or "").lower()
            candidates = []
            for asset in assets:
                if self._execution_asset_role(asset) != role:
                    continue
                if dimension == "sample_role" and dimension_value:
                    if str(asset.get("sample_role") or "").lower() != dimension_value:
                        continue
                path = self._real_execution_path(asset)
                if path:
                    candidates.append((asset, path))
            if not candidates:
                missing.append({
                    "param": builder_param,
                    "slot": slot_name,
                    # 报缺时不沿用 canonical role：`gene_order` 的槽名叫
                    # `genome_annotation`，canonical role 是 `reference_file`，而
                    # 消费方看到 role=reference_file 的缺项第一反应就是"执行端自带的，
                    # 可以忽略"——正好是这条被漏了两轮的原因。既然走到了报缺这一支，
                    # 就说明它不在规则 4 白名单里、必须由用户提供，改报 data_file。
                    "role": "data_file" if role == "reference_file" else role,
                    "reason": "no_confirmed_path",
                })
                continue
            # Prefer a study-level aggregate (dotted format e.g. ".maf") over
            # per-run files when several match a single-valued slot.
            candidates.sort(
                key=lambda ap: 0 if str(ap[0].get("format") or "").strip().startswith(".") else 1
            )
            if str(slot.get("cardinality") or "") == "array":
                # 数组参数给全部匹配路径（规格第 2 条："文件数组参数返回路径数组"）。
                # 走单值那条路会只取一个：fastqc 的 scatter 就只跑一个 FASTQ、cnvkit
                # 的队列只算一个样本——都不报错，只是悄悄少做。
                # 两个槽可以共用一个参数（fastqc 的 raw / clean 都对 `fastqs`），
                # 所以是并集去重、保持顺序，不是覆盖。
                bucket = params.setdefault(builder_param, [])
                if not isinstance(bucket, list):
                    bucket = params[builder_param] = [bucket]
                for _asset, path in candidates:
                    if path not in bucket:
                        bucket.append(path)
                continue
            usage_key = f"{role}:{dimension_value}" if dimension_value else role
            index = usage.get(usage_key, 0)
            if index >= len(candidates):
                index = len(candidates) - 1
            params[builder_param] = candidates[index][1]
            usage[usage_key] = index + 1
        return params, missing

    def _partial_recommendation_assets(
        self,
        matcher: Any,
        matched: Dict[str, Any],
        pipeline_id: str,
    ) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
        required_roles = sorted(matcher._allowed_file_roles(pipeline_id))
        by_study: Dict[str, List[Dict[str, Any]]] = {}
        for item in matched.get("backup_file_candidates") or []:
            study = str(item.get("study_accession") or "unknown")
            by_study.setdefault(study, []).append(item)

        ranked: List[Tuple[int, str, List[Dict[str, Any]], Set[str]]] = []
        for study, files in by_study.items():
            present = {matcher._file_role(item) for item in files}
            covered = {
                role for role in required_roles
                if any(_role_satisfies(role, value) for value in present)
            }
            ranked.append((-len(covered), study, files, covered))
        if not ranked:
            return [], [], required_roles
        _score, study, files, covered = sorted(ranked, key=lambda item: (item[0], item[1]))[0]

        selected: List[Dict[str, Any]] = []
        for role in required_roles:
            match = next(
                (
                    item for item in files
                    if _role_satisfies(role, matcher._file_role(item))
                ),
                None,
            )
            if match and match not in selected:
                selected.append(match)
        if required_roles == ["fastq"] or set(required_roles) == {"fastq"}:
            selected = matcher._dedupe_files(files)[: matcher._required_file_count(pipeline_id)]
        assets = [_evidence_asset(item, matcher._file_role) for item in selected]
        missing_roles = [role for role in required_roles if role not in covered]
        return assets, ([] if study == "unknown" else [study]), missing_roles

    @staticmethod
    def _strip_multiqc_from_candidates(values: Any) -> List[Dict[str, Any]]:
        """Drop any multiqc steps (and references to them) before validation.

        multiqc has zero NEXT edges in the graph, so it can never form a valid
        chain; the LLM occasionally emits X->multiqc fan-in that fails the closed
        -set NEXT / parallel-root checks, which is why the same query returns
        inconsistently. Removing it here makes validation deterministic
        regardless of whether the LLM included it. Safe because multiqc is a
        terminal QC-report aggregator whose output no analytic step consumes, so
        dropping it never breaks the surviving backbone.
        """
        if not isinstance(values, list):
            return []
        cleaned: List[Dict[str, Any]] = []
        for item in values:
            if not isinstance(item, dict):
                cleaned.append(item)
                continue
            steps = item.get("steps")
            if not isinstance(steps, list):
                cleaned.append(item)
                continue
            removed_ids = {
                str(step.get("step_id") or "")
                for step in steps
                if isinstance(step, dict)
                and str(step.get("tool_id") or "").lower() == "multiqc"
            }
            if not removed_ids:
                cleaned.append(item)
                continue
            new_steps: List[Any] = []
            for step in steps:
                if not isinstance(step, dict):
                    new_steps.append(step)
                    continue
                if str(step.get("tool_id") or "").lower() == "multiqc":
                    continue
                step = dict(step)
                depends = step.get("depends_on")
                if isinstance(depends, str):
                    depends = [depends]
                if isinstance(depends, list):
                    step["depends_on"] = [
                        dep for dep in depends if str(dep) not in removed_ids
                    ]
                inputs = step.get("inputs")
                if isinstance(inputs, dict):
                    step["inputs"] = {
                        name: binding
                        for name, binding in inputs.items()
                        if not (
                            isinstance(binding, dict)
                            and isinstance(binding.get("from"), dict)
                            and str(binding["from"].get("step_id") or "") in removed_ids
                        )
                    }
                new_steps.append(step)
            item = dict(item)
            item["steps"] = new_steps
            cleaned.append(item)
        return cleaned

    @staticmethod
    def _normalize_ranked_candidates(values: Any) -> List[Dict[str, Any]]:
        if not isinstance(values, list):
            return []
        prepared: List[Tuple[int, int, Dict[str, Any]]] = []
        seen_chains: Set[str] = set()
        for index, item in enumerate(values[:5], 1):
            if not isinstance(item, dict):
                continue
            steps = item.get("steps") or []
            signature = json.dumps(steps, ensure_ascii=False, sort_keys=True)
            if signature in seen_chains:
                continue
            seen_chains.add(signature)
            try:
                rank = int(item.get("rank") or index)
            except (TypeError, ValueError):
                rank = index
            rank = rank if rank > 0 else index
            prepared.append((rank, index, {
                "rank": rank,
                "match_note": str(item.get("match_note") or "").strip(),
                "steps": steps,
            }))
        prepared.sort(key=lambda row: (row[0], row[1]))
        used: Set[int] = set()
        normalized: List[Dict[str, Any]] = []
        for rank, _index, item in prepared:
            while rank in used:
                rank += 1
            used.add(rank)
            item["rank"] = rank
            normalized.append(item)
        return normalized

    def _candidate_required_asset_roles(
        self,
        methods: Sequence[Dict[str, Any]],
        validation: Dict[str, Any],
    ) -> List[str]:
        roles: List[str] = []
        for method in methods:
            for binding in (method.get("inputs") or {}).values():
                role = str(binding.get("asset_role") or "")
                if role and role not in EXECUTION_MANAGED_ASSET_ROLES and role not in roles:
                    roles.append(role)
        for item in validation.get("required_external_inputs") or []:
            role = self._role_for_input(str(item.get("input") or ""))
            if role not in EXECUTION_MANAGED_ASSET_ROLES and role not in roles:
                roles.append(role)
        return roles

    @staticmethod
    def _is_paired_wes_candidate(methods: Sequence[Dict[str, Any]]) -> bool:
        step_ids = [str(item.get("step_id") or "").lower() for item in methods]
        has_both_sides = (
            any(re.search(r"(?:^|[_.-])tumor(?:$|[_.-])", value) for value in step_ids)
            and any(re.search(r"(?:^|[_.-])normal(?:$|[_.-])", value) for value in step_ids)
        )
        four_slots = {"tumor_bam", "tumor_bai", "normal_bam", "normal_bai"}
        has_gatk_merge = any(
            str(item.get("tool_id") or "").lower() == "gatk"
            and four_slots.issubset(set((item.get("inputs") or {}).keys()))
            for item in methods
        )
        return has_both_sides and has_gatk_merge

    @staticmethod
    def _legacy_input_from_combination(
        combination: Dict[str, Any], metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        details: List[Dict[str, Any]] = []
        paths: List[str] = []
        for item in combination.get("files") or []:
            path = str(item.get("file_path") or item.get("path") or item.get("files") or "")
            if not path:
                continue
            read_pair = item.get("read_pair") or item.get("Read Pair")
            input_role = item.get("input_role") or (
                "fastq" if str(read_pair or "").lower() in {"r1", "r2"} else None
            )
            paths.append(path)
            details.append({
                "path": path,
                "files": item.get("files"),
                "input_role": input_role,
                "read_pair": read_pair,
                "format": item.get("format"),
                "source": item.get("source"),
                "study_accession": item.get("study_accession"),
                # Matched combination file records carry the sample number under
                # `sample_id` (the source projection); older shapes use
                # `sample_accession`. Accept either so the asset — and the
                # required WDL sample_id derived from it — is never empty.
                "sample_accession": item.get("sample_id") or item.get("sample_accession"),
                "run_accession": item.get("run_accession"),
                "individual_accession": item.get("individual_accession"),
                "sample_role": item.get("sample_role"),
                "sample_role_label": item.get("sample_role_label"),
                "match_reason": item.get("match_reason"),
            })
        return {
            "pipeline_id": None,
            "files": paths,
            "files_text": "\n".join(paths),
            "debug": {
                "file_details": details,
                "data_combination": combination,
                "llm_metadata": metadata,
            },
        }

    def _build_top3_candidate(
        self,
        text: str,
        intent: Dict[str, Any],
        raw_candidate: Dict[str, Any],
        methods: List[Dict[str, Any]],
        validation: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        rank = int(raw_candidate["rank"])
        required_roles = self._candidate_required_asset_roles(methods, validation)
        paired = self._is_paired_wes_candidate(methods)
        if paired:
            matched_data = self.router.matcher.match(
                intent, [{"pipeline_id": "wes_somatic_pair"}], limit=10
            )
        else:
            matched_data = self.router.matcher.match_custom_roles(
                intent, required_roles, limit=10
            )
        combinations = matched_data.get("data_combinations") or []
        if not combinations:
            constraints = matched_data.get("query_constraints") or {}
            unavailable = (
                constraints.get("disease")
                if constraints.get("disease_status") == "not_available" else None
            )
            cohort_error = (
                f"图谱里没有登记「{unavailable}」的队列，不能拿其它癌种的数据顶上"
                if unavailable else ""
            )
            return None, {
                "rank": rank,
                "stage": "cohort_disease_mismatch" if cohort_error else "data_matching",
                "errors": [cohort_error or "没有完整的数据组合"],
                "required_asset_roles": required_roles,
                "paired_wes_matcher": paired,
            }

        legacy = self._legacy_input_from_combination(combinations[0], {})
        assets = self._build_assets(legacy)
        plan = {"mode": "custom", "methods": deepcopy(methods), "validation": validation}
        internal_chain, missing, _parameters = self._custom_tool_chain(plan, assets)
        if missing:
            return None, {
                "rank": rank,
                "stage": "asset_binding",
                "errors": ["完整数据组合未能绑定全部用户样本输入"],
                "missing_assets": missing,
                "paired_wes_matcher": paired,
            }
        internal_validation = self._validate_internal_agent_contract({
            "assets": assets,
            "tool_chain": internal_chain,
        })
        tool_chain, mapping_errors = self.execution_registry.externalize(
            internal_chain, assets
        )
        knowledge_validation = self.execution_registry.validate(tool_chain, assets)
        contract_errors = (
            list(internal_validation.get("errors") or [])
            + list(mapping_errors)
            + list(knowledge_validation.get("errors") or [])
        )
        if contract_errors:
            return None, {
                "rank": rank,
                "stage": "contract_validation",
                "errors": contract_errors,
                "paired_wes_matcher": paired,
            }
        study_accession = self._study_accession(legacy, assets)
        match_key = json.dumps({
            "query": text,
            "rank": rank,
            "steps": [item.get("step_id") for item in tool_chain],
            "study": study_accession,
        }, ensure_ascii=False, sort_keys=True)
        return {
            "rank": rank,
            "match_note": raw_candidate.get("match_note") or "",
            "workflow_mode": "custom",
            "match_id": "match-" + hashlib.sha256(
                match_key.encode("utf-8")
            ).hexdigest()[:16],
            "validation_ok": True,
            "feasibility_status": "ready",
            "study_accession": study_accession,
            "assets": assets,
            "tool_chain": tool_chain,
            "selection_reason": raw_candidate.get("match_note") or "",
            "extensions": {
                "paired_wes_matcher": paired,
                "required_asset_roles": required_roles,
                "internal_tool_ids": [
                    str(item.get("tool_id") or "") for item in internal_chain
                ],
                "data_combination": {
                    key: combinations[0].get(key)
                    for key in (
                        "kind", "study_accession", "individual_accession",
                        "match_reason",
                    )
                    if combinations[0].get(key) is not None
                },
                "contract_validation": {
                    "ok": True,
                    "errors": [],
                    "internal_catalog": internal_validation,
                    "knowledge_card": knowledge_validation,
                },
            },
        }, None

    def _neo4j_pipeline_steps(self, pipeline_id: str) -> List[Dict[str, Any]]:
        registered = self.registered_methods.pipeline_steps.get(pipeline_id) or []
        if registered:
            return [
                {
                    "step_order": step.get("step_order"),
                    "step_id": step.get("step_id"),
                    "call_name": step.get("tool_id"),
                    "task_name": step.get("tool_id"),
                    "tool_id": step.get("tool_id"),
                    "description": step.get("description"),
                    "inputs": [item["name"] for item in step.get("inputs") or []],
                    "outputs": [item["name"] for item in step.get("outputs") or []],
                    "depends_on": step.get("depends_on") or [],
                    "source": "neo4j",
                }
                for step in registered
            ]
        method = self.registered_methods.pipeline_methods.get(pipeline_id)
        if not method:
            return []
        return [{
            "step_order": 1,
            "step_id": pipeline_id,
            "call_name": pipeline_id,
            "task_name": pipeline_id,
            "tool_id": pipeline_id,
            "description": method.description,
            "inputs": [item["name"] for item in method.inputs],
            "outputs": [item["name"] for item in method.outputs],
            "depends_on": [],
            "source": "neo4j",
        }]

    def _method_menu_lines(self) -> List[str]:
        lines = []
        data_by_source: Dict[str, List[str]] = {}
        order_by_source: Dict[str, List[str]] = {}
        # Sort edge sets to guarantee deterministic menu lines across processes.
        # Python set iteration order changes with hash randomization, which breaks
        # DEMO_REPLAY cassette hashes when a stage-two prompt is recorded in one
        # process and replayed in another.
        for source, output, target, input_name in sorted(self.registered_methods.data_edges):
            data_by_source.setdefault(source, []).append(f"{target}({output}->{input_name})")
        data_edges_as_pairs = {(s, t) for s, _o, t, _i in self.registered_methods.data_edges}
        for source, target in sorted(self.registered_methods.next_edges):
            if (source, target) not in data_edges_as_pairs:
                order_by_source.setdefault(source, []).append(target)
        for source in data_by_source:
            data_by_source[source].sort()
        for source in order_by_source:
            order_by_source[source].sort()
        for method in self.registered_methods.capabilities():
            tool_id = method["tool_id"]
            # multiqc has zero NEXT edges in the graph, so it can never be a
            # legal link in any chain. Advertising it only tempts the LLM to
            # hallucinate X->multiqc fan-in that fails validation and makes the
            # same query return inconsistently. Keep it out of the atomic menu.
            if tool_id == "multiqc":
                continue
            inputs = ", ".join(
                f"{item['name']}[{item.get('artifact') or 'file'};"
                f"{','.join(item.get('formats') or [])};"
                f"{'optional' if item.get('optional') else 'required'}]"
                for item in method["inputs"]
            ) or "none"
            outputs = ", ".join(
                f"{item['name']}[{item.get('artifact') or 'file'};{','.join(item.get('formats') or [])}]"
                for item in method["outputs"]
            ) or "none"
            data_next = data_by_source.get(tool_id, [])
            order_next = order_by_source.get(tool_id, [])
            lines.append(
                f"- {tool_id} | "
                f"inputs=[{inputs}] | outputs=[{outputs}] | "
                f"data_next=[{', '.join(data_next)}] | order_next=[{', '.join(order_next)}] | "
                f"{method['description']}"
            )
        return lines

    @staticmethod
    def _consume_llm_result(
        raw: Dict[str, Any], stage: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        decision = dict(raw)
        usage = decision.pop("__llm_usage", {}) or {}
        model = decision.pop("__llm_model", None)
        return decision, {
            "used": True,
            "status": "ok",
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "calls": 1,
            "stages": [stage],
        }

    def _capability_intent(self, text: str) -> Optional[Dict[str, Any]]:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not normalized:
            return None
        if self._explicit_customization(normalized):
            return None
        if any(hint in normalized for hint in self.RECOMMENDATION_HINTS):
            return None
        compact = re.sub(r"\s+", "", normalized)
        browse = any(
            hint.lower() in normalized or re.sub(r"\s+", "", hint.lower()) in compact
            for hint in self.CAPABILITY_BROWSE_HINTS
        )
        browse = browse or bool(re.search(
            r"(?:有哪些|哪些|列出|查看|查询).{0,24}(?:流程|pipeline|工具|方法)",
            normalized,
            flags=re.IGNORECASE,
        ))
        browse = browse or any(
            re.match(pattern, normalized, flags=re.IGNORECASE)
            for pattern in self.CAPABILITY_GENERIC_PATTERNS
        )
        if not browse:
            return None

        mentions_pipeline = any(
            term in normalized for term in ("流程", "pipeline", "预制菜")
        )
        mentions_atomic = any(
            term in normalized
            for term in ("原子工具", "atomic tool", "atomic工具", "工具", "方法")
        )
        if mentions_atomic and not mentions_pipeline:
            target = "atomic_tools"
        elif mentions_pipeline and not mentions_atomic:
            target = "pipelines"
        else:
            target = "full_catalog"

        input_words = ("输入", "需要", "接收", "处理", "基于", "使用", "从")
        output_words = ("输出", "产出", "生成", "得到", "结果")
        has_input_word = any(term in normalized for term in input_words)
        has_output_word = any(term in normalized for term in output_words)
        io_scope = "output" if has_output_word and not has_input_word else "input"

        data_filters = [
            key
            for key, spec in CAPABILITY_DATA_FILTERS.items()
            if any(alias.lower() in normalized for alias in spec["aliases"])
        ]
        if "matrix" in data_filters and any(
            item in data_filters for item in ("count_matrix", "expression_matrix")
        ):
            data_filters.remove("matrix")

        def _scope_for_filter(key: str) -> str:
            """按句中语境判断该数据条件作用于输入侧还是输出侧；语境不明返回 any。"""
            hits = [
                normalized.find(alias.lower())
                for alias in CAPABILITY_DATA_FILTERS[key]["aliases"]
            ]
            hits = [pos for pos in hits if pos >= 0]
            if not hits:
                return "any"
            pos = min(hits)
            input_dists = [
                abs(pos - normalized.find(word))
                for word in input_words
                if normalized.find(word) >= 0
            ]
            output_dists = [
                abs(pos - normalized.find(word))
                for word in output_words
                if normalized.find(word) >= 0
            ]
            if input_dists and (not output_dists or min(input_dists) <= min(output_dists)):
                return "input"
            if output_dists:
                return "output"
            return "any"

        data_filter_scopes = {key: _scope_for_filter(key) for key in data_filters}
        topic_filters = [
            key
            for key, spec in CAPABILITY_TOPIC_FILTERS.items()
            if any(alias.lower() in normalized for alias in spec["aliases"])
        ]
        return {
            "target": target,
            "io_scope": io_scope,
            "data_filters": data_filters,
            "data_filter_scopes": data_filter_scopes,
            "topic_filters": topic_filters,
            "source": "deterministic_rule",
        }

    def _explicit_customization(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if any(hint.lower() in normalized for hint in self.CUSTOM_HINTS):
            return True
        method_or_step = (
            r"(?:fastqc|fastp|trim(?: galore)?|star|rsem|samtools|featurecounts|multiqc|"
            r"bwa|gatk|bcftools|snpeff|salmon|步骤|环节|质控|剪切|比对|定量|计数|去重|过滤|注释)"
        )
        patterns = (
            rf"(?:不用|不做|不要|只做|只保留|仅保留).{{0,16}}{method_or_step}",
            rf"{method_or_step}.{{0,16}}(?:不用|不做|不要|只做|只保留|仅保留)",
            rf"(?:把|将).{{0,20}}{method_or_step}.{{0,20}}(?:放到|移到|提前|延后)",
        )
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _method_slot_blob(method: RegisteredMethod, io_scope: str) -> str:
        slots = method.outputs if io_scope == "output" else method.inputs
        values: List[str] = []
        for slot in slots:
            values.extend([
                str(slot.get("name") or ""),
                str(slot.get("artifact") or ""),
                str(slot.get("description") or ""),
                " ".join(str(value) for value in slot.get("formats") or []),
            ])
        return " ".join(values).lower()

    @staticmethod
    def _method_search_blob(method: RegisteredMethod) -> str:
        return " ".join([
            method.tool_id,
            method.name,
            method.description,
            WorkflowComposer._method_slot_blob(method, "input"),
            WorkflowComposer._method_slot_blob(method, "output"),
        ]).lower()

    def _matches_capability_filters(
        self, method: RegisteredMethod, intent: Dict[str, Any]
    ) -> bool:
        scopes = intent.get("data_filter_scopes") or {}
        input_blob = self._method_slot_blob(method, "input")
        output_blob: Optional[str] = None
        for key in intent.get("data_filters") or []:
            spec = CAPABILITY_DATA_FILTERS.get(str(key))
            if not spec:
                continue
            scope = scopes.get(str(key)) or str(intent.get("io_scope") or "input")
            if scope == "input":
                blob = input_blob
            else:
                if output_blob is None:
                    output_blob = self._method_slot_blob(method, "output")
                blob = output_blob if scope == "output" else f"{input_blob} {output_blob}"
            if not any(term.lower() in blob for term in spec["slot_terms"]):
                return False
        method_blob = self._method_search_blob(method)
        for key in intent.get("topic_filters") or []:
            spec = CAPABILITY_TOPIC_FILTERS.get(str(key))
            if spec and not any(term.lower() in method_blob for term in spec["terms"]):
                return False
        return True

    def _capability_entry(self, method: RegisteredMethod) -> Dict[str, Any]:
        entry = {
            **method.as_dict(),
            "source": "neo4j",
        }
        if method.tool_kind in {"pipeline", "task_pipeline"}:
            has_recipe = bool(self.registered_methods.pipeline_steps.get(method.tool_id))
            entry.update({
                "internal_steps": self._neo4j_pipeline_steps(method.tool_id),
                "internal_steps_locked": True,
                "decomposition_status": (
                    "neo4j_locked_recipe" if has_recipe else "neo4j_pipeline_level_tool"
                ),
            })
        return entry

    def _capability_plan(
        self,
        text: str,
        capability_intent: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        target = str(capability_intent.get("target") or "pipelines")
        pipeline_methods = [
            method
            for method in sorted(
                self.registered_methods.pipeline_methods.values(),
                key=lambda item: item.tool_id,
            )
            if self._matches_capability_filters(method, capability_intent)
        ]
        atomic_methods = [
            method
            for method in sorted(
                self.registered_methods.methods.values(),
                key=lambda item: item.tool_id,
            )
            if self._matches_capability_filters(method, capability_intent)
        ]
        if target == "pipelines":
            atomic_methods = []
        elif target == "atomic_tools":
            pipeline_methods = []

        labels = [
            CAPABILITY_DATA_FILTERS[key]["label"]
            for key in capability_intent.get("data_filters") or []
            if key in CAPABILITY_DATA_FILTERS
        ] + [
            CAPABILITY_TOPIC_FILTERS[key]["label"]
            for key in capability_intent.get("topic_filters") or []
            if key in CAPABILITY_TOPIC_FILTERS
        ]
        filter_text = "、".join(labels)
        if target == "atomic_tools":
            summary = f"当前 Neo4j 目录中找到 {len(atomic_methods)} 个符合条件的 atomic tool。"
        elif target == "pipelines":
            summary = f"当前 Neo4j 目录中找到 {len(pipeline_methods)} 个符合条件的标准 pipeline。"
        else:
            summary = (
                f"当前 Neo4j 登记 {len(self.registered_methods.pipeline_methods)} 个标准 pipeline/"
                f"task-pipeline 和 {len(self.registered_methods.methods)} 个 atomic tool。"
            )
        if filter_text:
            summary = f"按数据条件“{filter_text}”筛选，" + summary
        if not pipeline_methods and not atomic_methods:
            summary += " 当前目录未登记匹配能力；这不等于该分析在生物学上不可实现。"

        all_selected = pipeline_methods + atomic_methods
        input_formats = sorted({
            fmt
            for method in all_selected
            for slot in method.inputs
            for fmt in slot.get("formats") or []
        })
        output_formats = sorted({
            fmt
            for method in all_selected
            for slot in method.outputs
            for fmt in slot.get("formats") or []
        })
        answer = {
            "query_kind": target,
            "summary": summary,
            "filters": {
                "io_scope": capability_intent.get("io_scope") or "input",
                "data": capability_intent.get("data_filters") or [],
                "data_scopes": capability_intent.get("data_filter_scopes") or {},
                "topics": capability_intent.get("topic_filters") or [],
            },
            "pipeline_count": len(pipeline_methods),
            "atomic_tool_count": len(atomic_methods),
            "pipelines": [self._capability_entry(method) for method in pipeline_methods],
            "atomic_tools": [self._capability_entry(method) for method in atomic_methods],
            "available_input_formats": input_formats,
            "available_output_formats": output_formats,
            "catalog_complete": False,
            "catalog_note": "Neo4j 工具目录仍在拆解中，未登记能力不会被推断或编造。",
            "source": "neo4j",
        }
        result: Dict[str, Any] = {
            "status": "ok",
            "nl": text,
            "intent": {
                "query_text": text,
                "analysis_goal": "查询当前工作流能力目录",
                "requested_outputs": [],
                "source": capability_intent.get("source") or "capability",
            },
            "matched_pipelines": [],
            "matched_data": {
                "cohort_candidates": [],
                "file_candidates": [],
                "data_combinations": [],
            },
            "capabilities_count": len(self.registered_methods.pipeline_methods),
            "capability_answer": answer,
        }
        plan = {
            "mode": "capability",
            "label": "能力目录",
            "reason": summary,
            "capability_answer": answer,
            "validation": {"ok": True, "errors": []},
            "planner_metadata": metadata,
        }
        result["answer"] = summary
        self._apply_capability_contract(result, plan)
        return result

    @staticmethod
    def _deterministic_rnaseq_candidate_steps() -> List[Dict[str, Any]]:
        return [
            {
                "step_id": "fastp",
                "tool_id": "fastp",
                "inputs": {
                    "raw_fastq_read_r1": {"asset_role": "fastq_r1"},
                    "raw_fastq_read_r2": {"asset_role": "fastq_r2"},
                },
            },
            {
                "step_id": "star",
                "tool_id": "star",
                "inputs": {
                    "clean_fastq_read": {
                        "from": {"step_id": "fastp", "output": "clean_fastq_read"}
                    },
                    "genome_annotation": {"asset_role": "reference_file"},
                },
            },
            {
                "step_id": "rsem",
                "tool_id": "rsem",
                "inputs": {
                    "transcriptome_bam": {
                        "from": {"step_id": "star", "output": "transcriptome_bam"}
                    },
                    "genome_annotation": {"asset_role": "reference_file"},
                },
            },
            {
                "step_id": "samtools",
                "tool_id": "samtools",
                "inputs": {
                    "aligned_bam": {
                        "from": {"step_id": "star", "output": "aligned_bam"}
                    },
                },
                "depends_on": ["star"],
            },
            {
                "step_id": "featurecounts",
                "tool_id": "featurecounts",
                "inputs": {
                    "sorted_dedup_bam": {
                        "from": {"step_id": "samtools", "output": "sorted_dedup_bam"}
                    },
                    "genome_annotation": {"asset_role": "reference_file"},
                },
                "depends_on": ["samtools"],
            },
        ]

    @staticmethod
    def _eligible_rnaseq_fallback(
        text: str,
        intent: Dict[str, Any],
        recommendations: Sequence[Dict[str, Any]],
    ) -> bool:
        if not any(item.get("pipeline_id") == "rnaseq_singletask" for item in recommendations):
            return False
        normalized = re.sub(r"\s+", "", str(text or "").lower())
        if not any(term in normalized for term in ("rna-seq", "rnaseq", "fastq", "fq.gz", "表达定量")):
            return False
        if any(term in normalized for term in ("maf", "vcf", "wes", "体细胞突变", "肿瘤-正常")):
            return False
        return str(intent.get("omics_type") or "").lower() in {"", "rna-seq", "bulk rna-seq", "rnaseq"} or "rna" in normalized

    def _validate_custom_steps(
        self,
        raw_steps: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        errors: List[str] = []
        # 图谱没连上时目录是空的，于是**每一个** tool_id 都会被判成"未知"——调用方
        # 送来一条完全合法的链，却被告知工具名非法，去查自己那边。0822 排查测试时
        # 就是被这句话带偏的：满屏"未知 tool_id: star"，看着像目录坏了，实际是
        # bolt 连不上。工具目录只从图谱来（见 RegisteredMethodCatalog），所以这里
        # 必须先把"我不认识"和"我什么都不认识"分开说。
        catalog_state = self.registered_methods.unavailable_state()
        if catalog_state:
            return [], {
                "ok": False,
                "errors": [
                    f"工具目录为空，无法校验任何 tool_id：{catalog_state}。"
                    "这不是 steps 的问题，请先恢复图谱连接。"
                ],
                "warnings": [],
                "required_external_inputs": [],
                "catalog_unavailable": True,
                "catalog_error": self.registered_methods.error or "unknown",
            }
        normalized_steps, normalized_ids = self._normalize_custom_step_ids(raw_steps)
        warnings: List[str] = [
            f"已规范化 step_id: {old} -> {new}"
            for old, new in normalized_ids
        ]
        seen_step_ids: Set[str] = set()
        outputs_by_step: Dict[str, Set[str]] = {}
        output_specs_by_step: Dict[str, Dict[str, Dict[str, Any]]] = {}
        tool_by_step: Dict[str, str] = {}
        required_external: List[Dict[str, str]] = []
        steps: List[Dict[str, Any]] = []
        root_steps: List[Dict[str, Any]] = []
        for index, raw_step in enumerate(normalized_steps, 1):
            if not isinstance(raw_step, dict):
                errors.append(f"第 {index} 步不是对象")
                continue
            tool_id = str(raw_step.get("tool_id") or "")
            step_id = str(raw_step.get("step_id") or f"step_{index}")
            if step_id in seen_step_ids:
                errors.append(f"step_id 重复: {step_id}")
                continue
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_.-]*$", step_id):
                errors.append(f"step_id 非法: {step_id}")
                continue
            seen_step_ids.add(step_id)
            method = self.registered_methods.methods.get(tool_id)
            if not method:
                errors.append(f"第 {index} 步包含未知 tool_id: {tool_id or '<empty>'}")
                continue
            input_specs = {item["name"]: item for item in method.inputs}
            output_names = {item["name"] for item in method.outputs}
            bindings = raw_step.get("inputs") or {}
            if not isinstance(bindings, dict):
                errors.append(f"{step_id}.inputs 必须是对象")
                bindings = {}
            raw_dependencies = raw_step.get("depends_on") or []
            if isinstance(raw_dependencies, str):
                raw_dependencies = [raw_dependencies]
            elif not isinstance(raw_dependencies, list):
                errors.append(f"{step_id}.depends_on 必须是数组或字符串")
                raw_dependencies = []
            clean_bindings: Dict[str, Dict[str, Any]] = {}
            for input_name, binding in bindings.items():
                if input_name not in input_specs:
                    errors.append(f"{step_id} 包含未注册输入: {input_name}")
                    continue
                if isinstance(binding, str):
                    binding = {"asset_role": binding}
                    warnings.append(
                        f"已规范化 {step_id}.{input_name} 的字符串资产绑定"
                    )
                if not isinstance(binding, dict):
                    errors.append(f"{step_id}.{input_name} 的绑定必须是对象")
                    continue
                if binding.get("asset_role"):
                    clean_bindings[input_name] = {
                        "asset_role": self._canonical_asset_role(
                            input_name, str(binding["asset_role"])
                        )
                    }
                    continue
                source = binding.get("from")
                if isinstance(source, dict):
                    source_step = str(source.get("step_id") or "")
                    source_output = str(source.get("output") or "")
                    if source_step not in outputs_by_step:
                        errors.append(f"{step_id}.{input_name} 引用了不存在或非前序 step_id: {source_step}")
                        continue
                    if source_output not in outputs_by_step[source_step]:
                        errors.append(f"{step_id}.{input_name} 引用了未注册输出: {source_step}.{source_output}")
                        continue
                    source_tool = tool_by_step[source_step]
                    if (source_tool, source_output, tool_id, input_name) not in self.registered_methods.data_edges:
                        errors.append(
                            f"NEXT data 边不匹配: {source_tool}.{source_output} -> {tool_id}.{input_name} "
                            f"({source_step} -> {step_id})"
                        )
                        continue
                    expected_dimension = str(input_specs[input_name].get("dimension") or "")
                    expected_value = str(input_specs[input_name].get("dimension_value") or "")
                    if expected_dimension == "sample_role" and expected_value in {"tumor", "normal"}:
                        actual_value = self._step_sample_role(source_step)
                        if actual_value != expected_value:
                            errors.append(
                                f"样本维度不匹配: {source_step} 不能绑定 {step_id}.{input_name}; "
                                f"期望 sample_role={expected_value}"
                            )
                            continue
                    clean_bindings[input_name] = {"from": {"step_id": source_step, "output": source_output}}
                    continue
                if self._role_for_input(input_name) in EXECUTION_MANAGED_ASSET_ROLES:
                    # Reference genomes, indexes and interval lists are hosted by
                    # the execution side and never come from user data, so an
                    # empty binding here carries no information. Filling it is
                    # deterministic and keeps a common model slip from sinking an
                    # otherwise valid chain.
                    clean_bindings[input_name] = {"asset_role": "reference_file"}
                    warnings.append(
                        f"已补全 {step_id}.{input_name} 的执行端资源绑定"
                    )
                    continue
                errors.append(f"{step_id}.{input_name} 缺少 asset_role 或 from")
            if tool_id != "multiqc" and input_specs and not clean_bindings:
                errors.append(f"{step_id} 必须至少绑定一个已注册输入")
            if tool_id == "multiqc" and not clean_bindings and not raw_dependencies:
                errors.append(f"{step_id} 必须绑定 qc_files 或依赖至少一个 QC 前序步骤")
            selected_variant, variant_error = self._matching_input_variant(
                method, set(clean_bindings), step_id
            )
            if variant_error:
                errors.append(f"{step_id} 输入变体无唯一解: {variant_error}")
            for input_name, spec in input_specs.items():
                if input_name in clean_bindings or spec["optional"]:
                    continue
                if method.input_variants and any(
                    input_name in names for names in method.input_variants.values()
                ):
                    continue
                target = {"step_id": step_id, "input": input_name, "type": spec["type"]}
                if (
                    spec["is_file"]
                    and self._role_for_input(input_name)
                    not in EXECUTION_MANAGED_ASSET_ROLES
                ):
                    required_external.append(target)
            depends_on: List[str] = []
            for dependency in raw_dependencies:
                dependency_id = str(dependency or "")
                if dependency_id not in tool_by_step:
                    errors.append(f"{step_id}.depends_on 引用了不存在或非前序 step_id: {dependency_id}")
                    continue
                source_tool = tool_by_step[dependency_id]
                if (source_tool, tool_id) not in self.registered_methods.next_edges:
                    errors.append(
                        f"NEXT 不允许: {source_tool} -> {tool_id} "
                        f"({dependency_id} -> {step_id})"
                    )
                    continue
                if dependency_id not in depends_on:
                    depends_on.append(dependency_id)
            is_root = not depends_on and not any(
                "from" in binding for binding in clean_bindings.values()
            )
            if is_root:
                root_steps.append({
                    "step_id": step_id,
                    "tool_id": tool_id,
                    "sample_role": self._step_sample_role(step_id),
                    "input_names": sorted(clean_bindings),
                })
            outputs_by_step[step_id] = output_names
            output_specs_by_step[step_id] = {
                item["name"]: item for item in method.outputs
            }
            tool_by_step[step_id] = tool_id
            enriched = method.as_dict()
            enriched.update({
                "order": index,
                "step_id": step_id,
                "inputs": clean_bindings,
                "depends_on": depends_on,
                "reason": str(raw_step.get("reason") or ""),
                "input_variant": selected_variant,
            })
            steps.append(enriched)
        if len(root_steps) > 1:
            root_roles = {item["sample_role"] for item in root_steps}
            root_tools = {item["tool_id"] for item in root_steps}
            root_input_shapes = {tuple(item["input_names"]) for item in root_steps}
            if not (
                len(root_steps) == 2
                and root_roles == {"tumor", "normal"}
                and len(root_tools) == 1
                and len(root_input_shapes) == 1
            ):
                for item in root_steps[1:]:
                    errors.append(
                        f"步骤（{item['step_id']}）未与前序输出衔接："
                        "并行双根只允许同一工具、同一输入形状且 sample_role "
                        "恰为 tumor/normal 的两条配对样本链"
                    )
        if not steps:
            errors.append("自定义模式没有有效方法步骤")
        if required_external:
            warnings.append("仍有未绑定的文件输入，需由资产匹配或用户补充")
        return steps, {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "required_external_inputs": required_external,
        }

    @staticmethod
    def _step_sample_role(step_id: str) -> Optional[str]:
        lowered = str(step_id or "").lower()
        for role in ("tumor", "normal"):
            if re.search(rf"(?:^|[_.-]){role}(?:$|[_.-])", lowered):
                return role
        return None

    def _matching_input_variant(
        self,
        method: RegisteredMethod,
        bound_names: Set[str],
        step_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        if not method.input_variants:
            return None, None
        variant_slots = {
            slot for names in method.input_variants.values() for slot in names
        }
        normalized = {
            method.input_aliases.get(name, name)
            for name in bound_names
            if method.input_aliases.get(name, name) in variant_slots
        }
        matches = [
            name for name, names in method.input_variants.items()
            if set(names) == normalized
        ]
        sample_role = self._step_sample_role(step_id)
        if method.tool_id == "fastp" and sample_role and matches != ["paired_end"]:
            return None, f"{sample_role} 样本链必须完整绑定 paired_end R1/R2"
        if method.exactly_one_variant and len(matches) != 1:
            return None, (
                f"bound={sorted(normalized)}, complete_variants={matches or []}, "
                f"expected={method.input_variants}"
            )
        return (matches[0] if len(matches) == 1 else None), None

    @staticmethod
    def _normalize_custom_step_ids(
        raw_steps: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
        prepared = [deepcopy(step) if isinstance(step, dict) else step for step in raw_steps]
        original_ids = [
            str(step.get("step_id") or f"step_{index}")
            for index, step in enumerate(prepared, 1)
            if isinstance(step, dict)
        ]
        counts = {value: original_ids.count(value) for value in set(original_ids)}
        used = {
            value
            for value in original_ids
            if re.match(r"^[A-Za-z_][A-Za-z0-9_.-]*$", value)
        }
        aliases: Dict[str, str] = {}
        normalized: List[Tuple[str, str]] = []
        for index, step in enumerate(prepared, 1):
            if not isinstance(step, dict):
                continue
            original = str(step.get("step_id") or f"step_{index}")
            if (
                counts.get(original) == 1
                and not re.match(r"^[A-Za-z_][A-Za-z0-9_.-]*$", original)
            ):
                candidate = f"step_{index}"
                suffix = 2
                while candidate in used:
                    candidate = f"step_{index}_{suffix}"
                    suffix += 1
                aliases[original] = candidate
                step["step_id"] = candidate
                used.add(candidate)
                normalized.append((original, candidate))

        for step in prepared:
            if not isinstance(step, dict):
                continue
            dependencies = step.get("depends_on")
            if isinstance(dependencies, list):
                step["depends_on"] = [
                    aliases.get(str(dependency), dependency)
                    for dependency in dependencies
                ]
            elif dependencies is not None:
                step["depends_on"] = aliases.get(str(dependencies), dependencies)
            for binding in (step.get("inputs") or {}).values():
                if not isinstance(binding, dict) or not isinstance(binding.get("from"), dict):
                    continue
                source = binding["from"]
                source_id = str(source.get("step_id") or "")
                if source_id in aliases:
                    source["step_id"] = aliases[source_id]
        return prepared, normalized

    def _apply_capability_contract(
        self, result: Dict[str, Any], plan: Dict[str, Any]
    ) -> None:
        intent = result.get("intent") or {}
        query_text = str(intent.get("query_text") or result.get("nl") or "")
        answer = plan.get("capability_answer") or {}
        message = "这是能力目录查询，不生成执行流程，也不进行数据资产可行性判断。"
        result["schema_version"] = "tool-chain/v2"
        result["selection_status"] = "information"
        result["candidate_count"] = 0
        result["candidates"] = []
        result["recommendation_count"] = 0
        result["recommendations"] = []
        result["unsupported_reason"] = None
        result["planner_metadata"] = plan.get("planner_metadata") or {}
        result["capability_answer"] = answer
        result["intent"] = {
            **intent,
            "query_text": query_text,
            "analysis_goal": intent.get("analysis_goal") or "查询当前工作流能力目录",
            "requested_outputs": intent.get("requested_outputs") or [],
        }
        if isinstance(result.get("result"), dict):
            result["result"].update({
                "schema_version": "tool-chain/v2",
                "selection_status": "information",
                "candidate_count": 0,
                "candidates": [],
                "recommendation_count": 0,
                "recommendations": [],
                "unsupported_reason": None,
                "intent": result["intent"],
            })

    def _build_assets(self, legacy: Dict[str, Any]) -> List[Dict[str, Any]]:
        details = list((legacy.get("debug") or {}).get("file_details") or [])
        if not details:
            details = [{"path": path, "files": Path(path).name} for path in legacy.get("files") or []]
        assets: List[Dict[str, Any]] = []
        used_ids: Set[str] = set()
        for index, detail in enumerate(details, 1):
            path = str(detail.get("path") or detail.get("file_path") or detail.get("files") or "")
            if not path:
                continue
            role = self._contract_asset_role(detail)
            read_pair = str(detail.get("read_pair") or "").lower()
            study = str(detail.get("study_accession") or "asset")
            stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{study}-{role}-{index}").strip("-") or f"asset-{index}"
            asset_id = stem
            suffix = 2
            while asset_id in used_ids:
                asset_id = f"{stem}-{suffix}"
                suffix += 1
            used_ids.add(asset_id)
            assets.append({
                "asset_id": asset_id,
                "role": role,
                "path": path,
                "format": detail.get("format"),
                "path_verified": Path(path).exists(),
                "source": detail.get("source"),
                "sample_id": detail.get("sample_accession"),
                "run_accession": detail.get("run_accession"),
                "individual_accession": detail.get("individual_accession"),
                "sample_role": detail.get("sample_role"),
                "sample_role_label": detail.get("sample_role_label"),
                "mate": (
                    read_pair if read_pair in {"r1", "r2"}
                    else "r1" if role == "fastq_r1"
                    else "r2" if role == "fastq_r2"
                    else None
                ),
            })
        return assets

    def _contract_asset_role(self, detail: Dict[str, Any]) -> str:
        role = str(detail.get("input_role") or detail.get("role") or "").lower()
        name = str(detail.get("files") or detail.get("path") or "").lower()
        read_pair = str(detail.get("read_pair") or "").lower()
        if role == "expression_count":
            return "count_matrix"
        if role == "expression_abundance":
            return "expression_matrix"
        if role == "expression":
            if any(token in name for token in ("count", "featurecounts", "htseq")):
                return "count_matrix"
            if any(token in name for token in ("tpm", "fpkm", "rsem", "abundance")):
                return "expression_matrix"
            # 文件名无 count/丰度信号的通用表达文件，两个子类型槽位都可接受
            return "expression_file"
        if role == "scrna_object":
            # `_role_of_file` 已按 format=rds / .rds 后缀判过，这里原样透传。
            # 别在这里改按文件名判：Matrix-h5 目录和 .rds 文件的名字都像单细胞产物。
            return "scrna_object"
        if role == "clinical":
            return "clinical_file"
        if role == "metainfo":
            return "sample_metadata"
        if role == "maf":
            return "maf_file"
        if role in {"fastq", "fastq_r1", "fastq_r2"}:
            if re.search(r"(?:^|[._-])(?:r?1|f1|read1)(?:[._-]|$)", name):
                return "fastq_r1"
            if re.search(r"(?:^|[._-])(?:r?2|read2)(?:[._-]|$)", name):
                return "fastq_r2"
            if read_pair == "r1":
                return "fastq_r1"
            if read_pair == "r2":
                return "fastq_r2"
            if role in {"fastq_r1", "fastq_r2"}:
                return role
            return "fastq_file"
        return f"{role}_file" if role else "data_file"

    def _custom_tool_chain(
        self, plan: Dict[str, Any], assets: Sequence[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        chain: List[Dict[str, Any]] = []
        missing = list((plan.get("validation") or {}).get("required_external_inputs") or [])
        parameters: List[Dict[str, Any]] = []
        asset_usage: Dict[str, int] = {}
        for method in plan.get("methods") or []:
            bindings: Dict[str, Dict[str, Any]] = {}
            registered = self.registered_methods.methods.get(str(method.get("tool_id") or ""))
            specs = {item["name"]: item for item in registered.inputs} if registered else {}
            for input_name, binding in (method.get("inputs") or {}).items():
                if binding.get("from"):
                    bindings[input_name] = {"from": dict(binding["from"])}
                    continue
                role = str(binding.get("asset_role") or "data_file")
                asset = self._select_asset(
                    role,
                    assets,
                    asset_usage,
                    step_id=str(method.get("step_id") or ""),
                    slot_spec=specs.get(input_name) or {},
                )
                if asset:
                    bindings[input_name] = {"asset_id": asset["asset_id"]}
                elif role not in EXECUTION_MANAGED_ASSET_ROLES:
                    missing.append({"step_id": method.get("step_id"), "input": input_name, "role": role})
            chain.append({
                "step_id": method.get("step_id"),
                "tool_id": method.get("tool_id"),
                "inputs": bindings,
                "depends_on": method.get("depends_on") or [],
            })
        return chain, self._dedupe_records(missing), self._dedupe_records(parameters)

    def _role_for_input(self, input_name: str) -> str:
        name = input_name.lower()
        # 单细胞 Seurat 对象槽（`scrna_object_rds` / `input_rds`）。必须先于下面所有
        # 规则，否则它一条都不命中、落到 `data_file`——而 `data_file` 会接受任何未分类
        # 资产，包括 10x 的 `Matrix-h5` 目录。见 `_execution_asset_role` 的对应注释。
        #
        # 这里判后缀不判子串：本函数也被 `_execution_asset_role` 拿**文件名**调用，
        # 而 `"rds"` 作为子串会命中 `…records.tsv` 这类普通表格文件。
        if (name.endswith("_rds") or name.endswith(".rds")
                or "scrna_object" in name or "seurat" in name):
            return "scrna_object"
        if "count" in name:
            return "count_matrix"
        if any(token in name for token in ("expression", "fpkm", "tpm", "logcpm")):
            return "expression_matrix"
        if "clinical" in name:
            return "clinical_file"
        if any(token in name for token in ("meta", "mapping")):
            return "sample_metadata"
        if "maf" in name:
            return "maf_file"
        if any(token in name for token in ("read1", "fastq_1", "_r1")):
            return "fastq_r1"
        if any(token in name for token in ("read2", "fastq_2", "_r2")):
            return "fastq_r2"
        if name.endswith(("_vcf_index", "_bam_index", "_bai", "_tbi")):
            # 数据文件的伴随索引不是参考资源。`filtered_vcf_index` 名字里带 "index"，
            # 会先命中下面那条 reference 规则，被判成"卡片自带默认值，既不映射也不报缺"
            # （师兄规则 4）——于是 bcftools 少给一个必需参数还一声不吭。它没有默认值，
            # 缺了直接执行失败，必须按数据走。
            return "vcf_file" if "vcf" in name else "bam_file"
        if any(token in name for token in (
            "ref", "reference", "index", "genome", "gtf", "gff", "annotation",
            "interval", "known_site", "pon", "resource",
        )):
            return "reference_file"
        if "bam" in name:
            return "bam_file"
        if "vcf" in name:
            return "vcf_file"
        return "data_file"

    def _canonical_asset_role(self, input_name: str, requested_role: str) -> str:
        inferred = self._role_for_input(input_name)
        if inferred != "data_file":
            return inferred
        role = requested_role.strip().lower().replace("-", "_").replace(" ", "_")
        canonical = {
            "count_matrix", "expression_matrix", "clinical_file", "sample_metadata",
            "maf_file", "fastq_r1", "fastq_r2", "fastq_file", "bam_file",
            "vcf_file", "reference_file", "data_file", "scrna_object",
        }
        if role in canonical:
            return role
        if "count" in role or "计数" in role:
            return "count_matrix"
        if any(token in role for token in ("expression", "fpkm", "tpm", "logcpm", "表达")):
            return "expression_matrix"
        if "clinical" in role or "临床" in role:
            return "clinical_file"
        if any(token in role for token in ("metadata", "meta_", "样本信息", "样本元数据")):
            return "sample_metadata"
        if "maf" in role:
            return "maf_file"
        if "fastq" in role:
            if any(token in role for token in ("r1", "read1", "read_1")):
                return "fastq_r1"
            if any(token in role for token in ("r2", "read2", "read_2")):
                return "fastq_r2"
            return "fastq_file"
        if "bam" in role:
            return "bam_file"
        if "vcf" in role:
            return "vcf_file"
        if any(token in role for token in ("reference", "index", "genome", "参考", "索引")):
            return "reference_file"
        return "data_file"

    def _select_asset(
        self,
        role: str,
        assets: Sequence[Dict[str, Any]],
        usage: Dict[str, int],
        *,
        step_id: str = "",
        slot_spec: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        compatible = [asset for asset in assets if asset.get("role") == role]
        if not compatible and role == "fastq_file":
            compatible = [
                asset for asset in assets
                if asset.get("role") in {"fastq_r1", "fastq_r2", "fastq_file"}
            ]
        if not compatible and role in {"count_matrix", "expression_matrix"}:
            # 只允许通用表达文件（无 count/丰度信号）兜底；count 与 TPM/FPKM
            # 之间语义不同，禁止互相静默降级。
            compatible = [asset for asset in assets if asset.get("role") == "expression_file"]
        if not compatible and role == "data_file":
            compatible = list(assets)
        slot_spec = slot_spec or {}
        sample_role = self._step_sample_role(step_id)
        if sample_role:
            compatible = [
                asset for asset in compatible
                if str(asset.get("sample_role") or "") == sample_role
            ]
        if slot_spec.get("dimension") == "mate":
            mate = str(slot_spec.get("dimension_value") or "")
            compatible = [asset for asset in compatible if asset.get("mate") == mate]
        if not compatible:
            return None
        usage_key = "|".join([
            role,
            sample_role or "",
            str(slot_spec.get("dimension") or ""),
            str(slot_spec.get("dimension_value") or ""),
        ])
        index = usage.get(usage_key, 0)
        if index >= len(compatible):
            return None
        asset = compatible[index]
        usage[usage_key] = index + 1
        return asset

    def _study_accession(self, legacy: Dict[str, Any], assets: Sequence[Dict[str, Any]]) -> Optional[str]:
        combo = (legacy.get("debug") or {}).get("data_combination") or {}
        if combo.get("study_accession"):
            return combo["study_accession"]
        for detail in (legacy.get("debug") or {}).get("file_details") or []:
            if detail.get("study_accession"):
                return detail["study_accession"]
        return None

    def _dedupe_records(self, records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Set[str] = set()
        result: List[Dict[str, Any]] = []
        for record in records:
            key = json.dumps(record, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                result.append(record)
        return result

    def _validate_internal_agent_contract(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        errors: List[str] = []
        assets_by_id = {
            asset.get("asset_id"): asset for asset in contract.get("assets") or []
        }
        asset_ids = set(assets_by_id)
        known_steps: Dict[str, str] = {}
        outputs_by_step: Dict[str, Set[str]] = {}
        for step in contract.get("tool_chain") or []:
            step_id = step.get("step_id")
            tool_id = step.get("tool_id")
            if not step_id or step_id in known_steps:
                errors.append(f"step_id 缺失或重复: {step_id}")
                continue
            method = self.registered_methods.all_methods.get(str(tool_id))
            if not method:
                errors.append(f"未注册 tool_id: {tool_id}")
                continue
            input_names = {item["name"] for item in method.inputs}
            input_specs = {item["name"]: item for item in method.inputs}
            for input_name, binding in (step.get("inputs") or {}).items():
                if input_name not in input_names:
                    errors.append(f"{step_id} 使用未注册输入 {input_name}")
                if binding.get("asset_id") and binding["asset_id"] not in asset_ids:
                    errors.append(f"{step_id}.{input_name} 引用不存在 asset_id")
                if binding.get("asset_id") in assets_by_id:
                    asset = assets_by_id[binding["asset_id"]]
                    expected_role = self._step_sample_role(str(step_id))
                    if expected_role and asset.get("sample_role") != expected_role:
                        errors.append(
                            f"{step_id}.{input_name} asset sample_role 不匹配"
                        )
                    spec = input_specs.get(input_name) or {}
                    if spec.get("dimension") == "mate" and asset.get("mate") != spec.get("dimension_value"):
                        errors.append(f"{step_id}.{input_name} asset mate 不匹配")
                source = binding.get("from")
                if source:
                    source_step = source.get("step_id")
                    source_output = source.get("output")
                    if source_step not in known_steps:
                        errors.append(f"{step_id}.{input_name} 引用不存在或非上游 step_id")
                    elif source_output not in outputs_by_step.get(source_step, set()):
                        errors.append(f"{step_id}.{input_name} 引用未注册上游输出")
                    spec = input_specs.get(input_name) or {}
                    if spec.get("dimension") == "sample_role" and spec.get("dimension_value") in {"tumor", "normal"}:
                        if self._step_sample_role(str(source_step)) != spec.get("dimension_value"):
                            errors.append(f"{step_id}.{input_name} 上游 sample_role 不匹配")
            _variant, variant_error = self._matching_input_variant(
                method, set((step.get("inputs") or {}).keys()), str(step_id)
            )
            if variant_error:
                errors.append(f"{step_id} 输入变体无唯一解: {variant_error}")
            known_steps[step_id] = str(tool_id)
            outputs_by_step[step_id] = {item["name"] for item in method.outputs}
        return {"ok": not errors, "errors": errors}

_COMPOSER: Optional[WorkflowComposer] = None


def get_composer() -> WorkflowComposer:
    global _COMPOSER
    if _COMPOSER is None:
        _COMPOSER = WorkflowComposer()
    return _COMPOSER


def compose_workflow_request(
    nl_text: Any,
    top_k: int = 3,
) -> Dict[str, Any]:
    return get_composer().plan(
        nl_text,
        top_k=top_k,
    )


def list_workflow_methods() -> Dict[str, Any]:
    composer = get_composer()
    decomposition = {}
    for method in composer.registered_methods.pipeline_methods.values():
        recipe = composer._neo4j_pipeline_steps(method.tool_id)
        has_recipe = bool(composer.registered_methods.pipeline_steps.get(method.tool_id))
        decomposition[method.tool_id] = {
            "status": "neo4j_locked_recipe" if has_recipe else "neo4j_pipeline_level_tool",
            "registered_units": [step["tool_id"] for step in recipe],
            "unexpanded_internal_steps": [],
            "source": "neo4j",
        }
    return {
        "method_catalog_status": {
            **METHOD_CATALOG_STATUS,
            "registered_method_count": len(composer.registered_methods.methods),
            "total_tool_count": len(composer.registered_methods.all_methods),
            "connected": composer.registered_methods.connected,
            "error": composer.registered_methods.error,
        },
        "pipeline_decomposition_status": decomposition,
        "atomic_tools": composer.registered_methods.capabilities(),
        "neo4j_tools": composer.registered_methods.capabilities(include_pipelines=True),
    }


def list_neo4j_pipeline_capabilities() -> List[Dict[str, Any]]:
    composer = get_composer()
    return [
        {
            **method.as_dict(),
            "source": "neo4j",
            "internal_steps": composer._neo4j_pipeline_steps(method.tool_id),
            "internal_steps_locked": True,
        }
        for method in sorted(
            composer.registered_methods.pipeline_methods.values(),
            key=lambda item: item.tool_id,
        )
    ]
