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
    build_agent_input,
)
from neo4j_observability import Neo4jClient
from runtime_config import initialize_runtime


initialize_runtime()


PIPELINE_QUALITY_GATES: Dict[str, Dict[str, Any]] = {
    "cellranger_workflow": {"status": "blocked_pending_version", "severity": "critical", "issues": ["Cell Ranger 7.x/8.x 参数和 BAM 输出名需先按镜像版本确认"]},
    "wes_somatic_pair": {"status": "known_blocker", "severity": "critical", "issues": ["GATK 4.1+ Mutect2 不接受 --tumor-sample"]},
    "paired_fastq_to_unmapped_bam": {"status": "example_input_risk", "severity": "high", "issues": ["原示例 fastq_2 曾错误指向 R1，使用前必须重新核对配对"]},
    "rnaseq_singletask": {"status": "single_end_blocked", "severity": "high", "issues": ["单端 Trim Galore 输出与 R2 守卫存在已知问题", "continueOnReturnCode 会掩盖失败"]},
    "survival_analysis": {"status": "edge_case_risk", "severity": "high", "issues": ["单组/NA 分支可能缺输出或崩溃", "终点列可能回退到 OS 但仍标 PFS"]},
    "her2_pfs_survival": {"status": "edge_case_risk", "severity": "high", "issues": ["单组分支缺少必需输出", "否定事件词可能被误判为进展事件"]},
    "diff_expr_go": {"status": "scientific_review", "severity": "medium", "issues": ["默认差异筛选使用原始 p 值而非校正后 p 值"]},
    "diff_expr_kegg": {"status": "scientific_review", "severity": "medium", "issues": ["实际富集数据库为 Reactome", "默认差异筛选使用原始 p 值"]},
    "tmb_survival_analysis": {"status": "implementation_incomplete", "severity": "medium", "issues": ["核心 R 脚本仅存在于镜像", "当前过滤口径可能漏计 indel"]},
    "immune_infiltration_iobr": {"status": "scientific_review", "severity": "medium", "issues": ["CIBERSORT reliable 阈值 0.3 高于常用 0.05"]},
}

PIPELINE_ROUTING_CONSTRAINTS = {
    "rnaseq_singletask": (
        "paired-end branch covers FastQC -> Trim Galore -> STAR rRNA depletion -> STAR genome alignment -> "
        "BAM processing -> RSEM -> FeatureCounts -> MultiQC in this order; requires R1/R2, rRNA STAR index, "
        "genome STAR index, RSEM index and matching GTF. The known Trim Galore/R2 defects affect single-end only."
    ),
    "paired_fastq_to_unmapped_bam": (
        "only converts paired FASTQ to unmapped BAM/uBAM; requires R1/R2 plus readgroup, library, platform unit, "
        "run date, platform and sequencing center metadata; it does not perform QC, alignment or variant calling."
    ),
    "wes_somatic_pair": (
        "requires paired tumor-normal WES FASTQ and produces aligned BAM plus somatic VCF; use only when variant "
        "calling is requested, not for a plain FASTQ-to-uBAM conversion."
    ),
    "cellranger_workflow": (
        "requires 10x Chromium single-cell FASTQ and Cell Ranger reference assets; do not use for bulk RNA-seq."
    ),
}

METHOD_CATALOG_STATUS = {
    "status": "work_in_progress",
    "scope": "Neo4j curated tool catalog and reviewed NEXT relationships",
    "source": "neo4j",
    "is_complete_internal_tool_decomposition": False,
}

EXECUTION_MANAGED_ASSET_ROLES = {"reference_file"}

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
            "optional": not bool(slot.get("required")),
            "artifact": artifacts[0] if artifacts else None,
            "formats": [str(value) for value in slot.get("formats") or [] if value],
            "description": str(slot.get("description") or ""),
            "dimension": str(slot.get("dimension") or ""),
            "dimension_value": str(slot.get("dimension_value") or ""),
            "variant": str(slot.get("variant") or ""),
            "variant_alias_for": str(slot.get("variant_alias_for") or ""),
        }

    def capabilities(self, include_pipelines: bool = False) -> List[Dict[str, Any]]:
        source = self.all_methods if include_pipelines else self.methods
        return [source[key].as_dict() for key in sorted(source)]


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
    ):
        self.registered_methods = method_catalog or RegisteredMethodCatalog()
        self.router = router or PipelineRouter(
            catalog=Neo4jPipelineCatalog(self.registered_methods)
        )

    def plan(
        self,
        nl_text: Any,
        top_k: int = 5,
        force_custom: bool = False,
        expand_standard_steps: bool = True,
    ) -> Dict[str, Any]:
        text = "" if nl_text is None else str(nl_text).strip()
        capability_intent = None if force_custom else self._capability_intent(text)
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
        decision, planner_metadata = (
            self._llm_decision(text, force_custom=True)
            if force_custom else self._llm_decision(text)
        )
        if not decision:
            known_standard_ids = (
                [] if force_custom else self._known_standard_pipeline_ids(text)
            )
            decision = {
                "mode": "custom" if force_custom else self._rule_mode(text),
                "reason": "LLM 规划器未启用，按显式修改词做保守判定。",
                "pipeline_ids": known_standard_ids,
                "reference_pipeline_ids": [],
                "steps": [],
            }
        mode = (
            decision.get("mode")
            if decision.get("mode") in {"standard", "custom", "capability"}
            else self._rule_mode(text)
        )
        if mode == "capability":
            return self._capability_plan(
                text,
                self._capability_intent(text) or {"target": "pipelines", "source": "llm"},
                planner_metadata,
            )
        if mode == "custom":
            return self._custom_plan(text, decision, planner_metadata, top_k)
        return self._standard_plan(
            text,
            decision,
            planner_metadata,
            top_k,
            expand_standard_steps=expand_standard_steps,
        )

    def _llm_decision(
        self, text: str, force_custom: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        if not text or _force_rule():
            return None, {"used": False, "status": "force_rule" if _force_rule() else "empty_query"}
        stage_one_prompt = (
            '''你是生信工作流编排器的流程选择器。你只负责判断用户需求应该走"标准流程"还是
"自定义组链",以及选哪些标准流程。你不执行任何生信任务。

## 输出格式

只输出一个 JSON 对象,不要 markdown 代码块,不要任何解释文字。字段顺序如下:

{
  "analysis": {
    "data_in_hand": "用户手上有什么数据(测序原始数据/表达矩阵/MAF/临床表),\n                     以及是否提到配对样本(肿瘤vs正常、处理vs对照)",
    "goal": "用户最终想要什么产物",
    "steps_implied": "从数据到产物在生信上需要经过哪些环节",
    "menu_scan": "菜单里哪些 pipeline 与这些环节相关,各覆盖了哪一段"
  },
  "mode": "standard" | "custom",
  "reason": "判定理由,一到三句",
  "requirements": ["拆解出的需求点"],
  "pipeline_ids": [...],
  "reference_pipeline_ids": [...],
  "pipeline_assessments": [
    {
      "pipeline_id": "...",
      "input_match": "match" | "partial" | "mismatch",
      "functional_coverage": "full" | "partial" | "none",
      "output_match": "match" | "partial" | "mismatch",
      "note": "简述"
    }
  ],
  "uncovered_requirements": ["菜单里没有任何 pipeline 能覆盖的需求点"]
}

必须先填 analysis 再填其余字段。analysis 是你的推理过程,不要跳过、不要事后补写。

## 判定顺序(严格按此顺序)

1. 用户是否明确要求修改某个流程的内部步骤(换掉/删掉/插入/调整某一步)?
   → mode = "custom"。这条优先级最高,即使菜单里有现成流程也走 custom。

2. 否则,菜单里是否存在一个或多个 pipeline,其组合能覆盖 requirements?
   → mode = "standard"。
   注意:**组合多个 pipeline 是常态,不是例外**。一个需求点对应一个 pipeline、
   多个需求点对应多个 pipeline,这是标准做法。不要因为"没有单个 pipeline 能全包"
   就判 custom——先看组合能不能覆盖。
   只有当 requirements 中存在任何 pipeline 组合都覆盖不了的部分时,才走第 3 条。

3. 否则 → mode = "custom",把最接近的 pipeline 填进 reference_pipeline_ids
   (供下一阶段参考),pipeline_ids 留空。

## 关于 pipeline_assessments(重要)

对每一个你放进 pipeline_ids 的流程,都必须给出诚实的三项评估。
**不要为了让答案看起来完整而虚报 match/full。**

- input_match:用户手上的数据能否直接喂给这个流程的必需输入?
- functional_coverage:这个流程是否完成了用户要求的核心分析任务?
- output_match:这个流程的产物**是否包含**用户要的核心产物?

functional_coverage 判定标准:
- 只要该流程产出了用户要求的核心产物/完成了核心任务,即使内部还多做了上游步骤,也标 **full**;
- 只完成一部分或需要借助其他流程补全才标 **partial**;
- 完全无关才标 **none**。

output_match 判定标准:
- 如果流程的产出中明确包含用户目标产物(即使还附带其他产物),标 **match**;
- 如果产物与用户目标产物属于同类但层级/格式不对(如用户要注释后的 VCF,流程只给 unfiltered VCF),标 **partial**;
- 如果产物完全不相关,标 **mismatch**。

functional_coverage / output_match 任何一项为 partial / mismatch / none,
或者存在 uncovered_requirements,下游会自动降级为 custom。
input_match = "mismatch" **不单独触发降级**(数据类型问题会在标准流程里明确标注给用户)。
如实填写就是正确做法,不要为了保住 standard 而美化评估。

## 表达数据类型(选流程时必须区分)

- raw count 矩阵:featureCounts / HTSeq 类工具的产物,文件名常含 count/counts
- 丰度矩阵:TPM / FPKM,RSEM 类工具的产物

**两者不可互换。** 需要 raw count 的流程不能喂 TPM 矩阵,反之亦然。
选流程前先确认用户手上的是哪一种;用户没说清楚时,在 requirements 里标注这个歧义,
不要替他假设。

## 配对样本识别

如果用户提到肿瘤/正常、癌旁、对照组、配对样本、somatic、体细胞变异等,
在 analysis.data_in_hand 里明确写出"配对样本",并在 requirements 里列一条
"需要按样本分别处理后汇合"。下一阶段依赖这个信号。

## 常见组合示例(帮助你识别 standard,不要照搬 ID,以菜单为准)

- "同时做 GO 和 KEGG/通路富集" → 两个富集 pipeline 组合:diff_expr_go + diff_expr_kegg,mode = standard。
  **不要纠结 diff_expr_kegg 内部用的是 Reactome 还是 KEGG 数据库**,
  只要流程提供通路富集结果,output_match 和 functional_coverage 都标 full。
- "画突变景观图,再看 TMB 和生存的关系" → 突变景观 + TMB 生存分析组合,standard
- "双端 FASTQ 做 RNA-seq 上游,要表达矩阵" → RNA-seq 上游单个 pipeline,standard
- "FASTQ 转 uBAM" → uBAM 转换单个 pipeline,standard

## 用户未明确数据类型时的处理

如果用户只说"做 XX 分析"但没提具体数据文件/格式,而流程需要某种表达矩阵/临床表/MAF:
- 不要直接判 input_match = "mismatch";
- 判 **partial** 并在 note 里写"用户未明确数据,流程需要 X";
- 这不会导致降级,仍然可以走 standard。

## 输入类型不匹配的处理(重要)

如果用户手上的数据类型不符合流程要求(例如流程要 raw count 矩阵,
用户有的是 TPM/FPKM),**仍然要把这个流程放进 pipeline_ids**,
并在 pipeline_assessments 里如实标 input_match = "mismatch",
在 note 里写清楚"该流程需要 X,用户提供的是 Y"。

不要因为输入不匹配就判 custom——自定义组链**也解决不了数据类型问题**,
那样只会让用户什么信息都拿不到。把问题说清楚比返回空结果有用。

## 硬性约束

- pipeline_ids 只能来自下方菜单,不得编造 ID,不得改写 ID 的拼写;
- 判定 standard 时必须给出至少一个 pipeline_id;给不出就应该判 custom;
- 不要在本阶段拆解原子工具,那是下一阶段的事;
- 不要收集或讨论线程数、内存等运行参数,那不属于编排。

标准 pipeline 菜单：
''' + "\n".join(self._pipeline_menu_lines())
        )
        if force_custom:
            stage_one = {
                "mode": "custom",
                "reason": "强制自助餐测试：跳过标准 pipeline 选择。",
                "pipeline_ids": [],
                "reference_pipeline_ids": [],
            }
            stage_one_metadata = {
                "used": True,
                "status": "ok",
                "model": None,
                "calls": 0,
                "stages": [],
                "force_custom": True,
            }
        else:
            stage_one_raw = _lazy_call_llm(stage_one_prompt, f"用户需求：{text}")
            if not isinstance(stage_one_raw, dict):
                return None, {"used": False, "status": "failed_or_unavailable"}
            stage_one, stage_one_metadata = self._consume_llm_result(
                stage_one_raw, "standard_selection"
            )
        if self._explicit_customization(text) and stage_one.get("mode") != "custom":
            stage_one["reference_pipeline_ids"] = (
                stage_one.get("pipeline_ids")
                or stage_one.get("reference_pipeline_ids")
                or []
            )
            stage_one["pipeline_ids"] = []
            stage_one["mode"] = "custom"
            stage_one["reason"] = (
                f"{stage_one.get('reason') or ''} 用户明确要求修改标准流程内部步骤，"
                "程序规则将模式校正为 custom。"
            ).strip()
        elif not force_custom:
            known_standard_ids = self._known_standard_pipeline_ids(text)
            if known_standard_ids:
                stage_one["mode"] = "standard"
                stage_one["pipeline_ids"] = known_standard_ids
                stage_one["reference_pipeline_ids"] = []
                if not stage_one_metadata.get("used"):
                    # 仅规则兜底路径可以清空覆盖评估；LLM 实际跑通时必须保留其
                    # pipeline_assessments/uncovered_requirements，让随后的覆盖缺口
                    # 检查继续生效，避免规则捷径抹掉 LLM 发现的缺口。
                    stage_one["uncovered_requirements"] = []
                    stage_one["pipeline_assessments"] = []
                stage_one["reason"] = (
                    f"{stage_one.get('reason') or ''} 已由保守组合规则确认："
                    "请求直接对应已登记标准 pipeline，未要求修改其内部步骤。"
                ).strip()
        if stage_one.get("mode") == "standard" and self._standard_has_coverage_gap(stage_one):
            stage_one["mode"] = "custom"
            stage_one["reference_pipeline_ids"] = stage_one.get("pipeline_ids") or []
            stage_one["pipeline_ids"] = []
            stage_one["reason"] = (
                f"{stage_one.get('reason') or ''} 标准流程逐项评估存在未覆盖需求或输入/输出不匹配。"
            ).strip()
        if stage_one.get("mode") != "custom":
            stage_one.setdefault("steps", [])
            return stage_one, stage_one_metadata

        stage_two_prompt = (
            '''你是生信工作流编排器的组链器。上一阶段已判定需要自定义组链。
你要从下方菜单的原子工具中,组出一条满足需求的工具链。你不执行任何生信任务。

## 输出格式

只输出一个 JSON 对象,不要 markdown 代码块,不要任何解释文字:

{
  "analysis": {
    "sample_layout": "本次是单样本还是配对样本?配对的话有哪几个样本角色?",
    "data_path": "从输入数据到目标产物,数据形态依次如何变化\n                  (FASTQ → BAM → sorted BAM → VCF → ...)",
    "tool_mapping": "每一次形态变化由菜单里的哪个工具完成",
    "checks": "自检结果,见下方自检清单"
  },
  "steps": [ ... ],
  "decomposition_gaps": [ ... ]
}

必须先填 analysis 再填 steps。

## 无法组链时的处理(先读这条)

如果你判断当前菜单的原子工具**无法表达**用户的需求
(典型情况:配对样本需要在某个工具处汇合,但该工具只注册了一个对应输入槽),
那么:

- steps 返回空数组;
- **decomposition_gaps 必须非空**,写明具体缺什么。格式:
  "配对样本汇合无法表达:<工具名> 在当前目录中只注册了 <N> 个 <数据形态> 输入槽,
   无法同时接收 <样本角色列表>。需要为该工具补充分样本输入槽。"

**硬约束:steps 为空数组时,decomposition_gaps 绝对不能为空。**
两者同时为空等于"我做不了但我不告诉你为什么",这是最差的输出,不可接受。

## 以参考流程为基准(收到 reference_pipeline_ids 时必读)

用户消息末尾附带了参考流程的**原子步骤清单**（step_id、tool_id、inputs、outputs、depends_on）。
当用户的需求是"把某流程里的 A 换成 B""删掉某一步""插入某一步""其他不变"时:

1. 以附带清单为**唯一基线**,不要凭记忆重写;
2. 只改用户明确要求改的那一处工具(tool_id),保持该步骤原有的 step_id 语义;
3. **所有分析步骤必须保留**,不得省略;下游的定量、计数、质控汇总等步骤全部保留;
4. **尽量保持原顺序和上下游连接**:
   - 被替换步骤的上游 from/depends_on 要接到新工具上;
   - 被替换步骤的下游步骤必须继续接到新工具的对应输出上;
   - 其余未改步骤的 from、depends_on、inputs、outputs 全部保留;
   - 如果新工具与原上下游之间没有 allowed_next 边,可以合法调整相邻质控/预处理步骤的顺序,但不得省略步骤,最终产物必须一致。
4. **其余步骤必须原样保留**,包括下游的定量、计数、质控汇总等步骤。
   用户说"其他不变"就是字面意思,不要顺手精简。
5. 在 analysis.data_path 里确认:改完之后,原流程的最终产物是否仍然产出?
   如果少了,说明你漏了步骤,回去补。

常见错误:
- 只组到中间形态(如只到 BAM)就收尾,丢掉了下游的表达定量和质控汇总;
- 替换 fastp/trim_galore 后删掉了 fastqc,或没让 star 改接 fastp 的 clean_fastq_read;
- 改了工具却漏改下游 from,导致下游 step 还指向已被替换的旧步骤。

正确示例(把 trim_galore 换成 fastp,保留全部主链步骤):
- fastp (fastp, raw_fastq_read) →
- fastqc_raw (fastqc, 来自 fastp.clean_fastq_read 或 raw_fastq_read, depends_on=[fastp]) →
- star (star, clean_fastq_read 来自 fastp.clean_fastq_read) →
- rsem + samtools (并行,来自 star 的不同输出) →
- featurecounts
最终产物仍是表达丰度矩阵、表达计数矩阵和 MultiQC 报告。
(如果 allowed_next 边允许,也可把 fastqc 放在 fastp 之前,但当前目录下 fastqc→fastp 边可能不存在,此时上述顺序是合法替代。)

## step 结构

{
  "step_id": "唯一标识,字母开头,可含数字/下划线/点/连字符",
  "tool_id": "必须是菜单中的原子工具 id",
  "inputs": {
    "<工具注册的输入名>": {"asset_role": "..."}
      或
    "<工具注册的输入名>": {"from": {"step_id": "...", "output": "<源工具注册的输出名>"}}
  },
  "depends_on": ["step_id", ...],
  "reason": "这一步做什么、属于哪个样本"
}

注意:`from` 挂在**单个 input 之下**,不是 step 级的数组。
每个 input 只能有一个绑定——要么 asset_role,要么 from,不能两者都有。
一个 step 能接几路上游,取决于它注册了几个输入槽。

## 样本维度(本次重点,务必读完)

**step 是"工具 × 样本"的实例,不是"工具"。**
同一个 tool_id 可以出现在多个 step 里,只要 step_id 不同——这是合法且必要的。

### 判断需要几条链

- 单样本流程(RNA-seq 上游、单样本 QC 等)→ 一条链,step_id 不加后缀。
- 配对流程(肿瘤 vs 正常、处理 vs 对照、somatic/体细胞变异)→
  **每个样本一条独立的链**,step_id 加 `_tumor` / `_normal` 后缀区分。

### 配对流程的硬性要求

1. **单样本步骤必须复制。** fastqc / fastp / trim_galore / bwa / star / samtools
   都是单样本步骤,配对分析时必须为每个样本各生成一个 step。
   禁止让两个样本共用同一个 step。

2. **绝对不要在 samtools 或更早的步骤把两个样本合并。**
   两个样本必须各自独立完成 比对 → 排序/索引/去重,各自产出自己的 BAM/BAI,
   之后才能汇合。提前合并会产生生物学上错误的结果。

3. **同链传播。** 单样本步骤的 from 只能指向**相同后缀**的上游 step。
   `samtools_tumor` 的 from 必须是 `bwa_tumor`,绝不能是 `bwa_normal`。

4. **汇合步骤只出现一次。** gatk / bcftools / snpeff 各只生成一个 step。
   不要为每个样本分别生成一个汇合步骤,除非该工具本身就设计为每个样本独立运行。

### 配对链的正确形状(示意,不要照抄 step_id 以外的内容)

fastp_tumor  → bwa_tumor  → samtools_tumor  ┐
                                              ├→ gatk → bcftools → snpeff
fastp_normal → bwa_normal → samtools_normal ┘

**注意**:上图成立的前提是 gatk 注册了两个能分别接收 tumor/normal BAM 的输入槽。
如果 gatk 只注册了一个 BAM 输入槽,则上图在当前目录下**不成立**,必须按
"无法组链时的处理"一节返回阻断,steps 为空、decomposition_gaps 非空。

## 数据形态不可混淆

| 不要混淆 | 说明 |
|---|---|
| uBAM ≠ 比对后 BAM | uBAM 是未比对的,不能当作 bwa/star 的输出使用 |
| transcriptome_bam ≠ aligned_bam | STAR 的转录组坐标 BAM 只能给 rsem;基因组坐标 BAM 才走 samtools |
| STAR 的主输出名是 `aligned_bam` | 不要写成其他名字 |
| raw count ≠ TPM/FPKM | featurecounts 产 raw count,rsem 产丰度矩阵,下游不可互换 |
| MultiQC 只吃质控日志 | 用 `depends_on` 连接,不解析表达矩阵/变异表/富集结果 |

## 连接规则

1. 每个 step 的 input 名必须**逐字**匹配该工具注册的输入名,不得改写、不得意译;
2. from 的 output 名必须**逐字**匹配源工具注册的输出名;
3. from 只能引用**已经出现在前面**的 step;
4. 每一条 from 和 depends_on,其 (源工具, 目标工具) 必须存在于菜单给出的
   allowed_next_tool_ids 中。菜单里没有的连接一律不能用;
5. **除第一步外,每个 step 的 inputs 中至少要有一个 input 使用 from 绑定,
   或者该 step 有 depends_on。** 全部 input 都用 asset_role 绑定的非首步是非法的;
6. 不得编造菜单以外的 tool_id、输入名、输出名、连接边。

## decomposition_gaps

如果用户要求修改的是某个尚未拆解成原子步骤的 pipeline 的内部步骤,
把这件事如实写进 decomposition_gaps,**不要凭猜测编造该 pipeline 的内部拆分**。
下游会据此返回 blocked 状态,这是正确行为。

## 提交前自检(把结论写进 analysis.checks)

逐条回答,任何一条为"否"就回去改:

1. 本次是配对样本吗?如果是,每个单样本工具都成对出现了吗?
2. 每个单样本 step 的 from 后缀是否与自身一致?有没有跨样本连接?
3. 汇合步骤只出现一次吗?(gatk/bcftools/snpeff 不要为每个样本各一个)
4. 如果这是配对样本:我数过汇合工具的输入槽了吗?够吗?
5. 如果不够:我是如实写进 decomposition_gaps 了,还是偷偷退回了单样本链?
    (后者不可接受)
6. 有没有在 samtools 或更早的位置合并样本?
7. 所有 input / output 名是否与菜单逐字一致?
8. 所有连接是否都在 allowed_next_tool_ids 里?
9. 除第一步外,每个 step 是否都有 from 或 depends_on?
10. 有没有编造任何菜单里没有的东西?

Neo4j atomic 方法目录：
''' + "\n".join(self._method_menu_lines())
        )
        reference_pipeline_ids = (
            stage_one.get("reference_pipeline_ids")
            or stage_one.get("pipeline_ids")
            or []
        )
        reference_recipes = {
            pipeline_id: self._neo4j_pipeline_steps(pipeline_id)
            for pipeline_id in reference_pipeline_ids
            if pipeline_id in self.registered_methods.pipeline_methods
        }
        stage_two_user = (
            f"用户需求：{text}\n第一阶段参考流程："
            f"{json.dumps(reference_pipeline_ids, ensure_ascii=False)}\n"
            f"第一阶段理由：{stage_one.get('reason') or ''}\n"
            f"参考流程原子步骤（只读，用于'其他不变'时保持完整）：\n"
            f"{json.dumps(reference_recipes, ensure_ascii=False, indent=2)}"
        )
        stage_two_attempts = 1
        stage_two_raw = _lazy_call_llm(stage_two_prompt, stage_two_user)
        if not isinstance(stage_two_raw, dict):
            stage_two_attempts += 1
            retry_prompt = (
                stage_two_prompt
                + "\n\n上一次返回未形成可解析 JSON。请重新从完整用户目标规划，"
                "只返回一个符合上述 schema 的 JSON object。"
            )
            stage_two_raw = _lazy_call_llm(retry_prompt, stage_two_user)
        if not isinstance(stage_two_raw, dict):
            stage_one["steps"] = []
            return stage_one, {
                **stage_one_metadata,
                "used": False,
                "status": "custom_generation_failed",
                "calls": int(stage_one_metadata.get("calls") or 0) + stage_two_attempts,
            }
        stage_two, stage_two_metadata = self._consume_llm_result(
            stage_two_raw, "custom_method_composition"
        )
        stage_two_metadata["calls"] = stage_two_attempts
        if stage_two_attempts > 1:
            stage_two_metadata["stages"].append("custom_method_composition_retry")

        raw_steps = stage_two.get("steps") or []
        raw_gaps = stage_two.get("decomposition_gaps") or []
        # Code-level guard: an empty steps list with empty gaps violates the
        # stage-two hard constraint and makes the blocker reason disappear.
        # For paired-sample requests, retry once; if the model still returns
        # nothing, synthesize gaps from catalog facts rather than falling back
        # to generic validation errors.
        if (
            not raw_steps
            and not raw_gaps
            and stage_two_attempts < 2
            and self._request_implies_pairing(text)
        ):
            retry_prompt = (
                stage_two_prompt
                + "\n\n上一步返回了空 steps 且空 decomposition_gaps，这违反了"
                "'无法组链时必须返回 gaps'的硬约束。如果当前目录无法表达需求，"
                "请返回 steps=[] 并填写具体 decomposition_gaps；如果可以表达，请返回有效 steps。"
            )
            stage_two_raw = _lazy_call_llm(retry_prompt, stage_two_user)
            stage_two_attempts += 1
            if isinstance(stage_two_raw, dict):
                stage_two, stage_two_metadata = self._consume_llm_result(
                    stage_two_raw, "custom_method_composition"
                )
                stage_two_metadata["calls"] = stage_two_attempts
                stage_two_metadata["stages"].append("custom_method_composition_retry")
                raw_steps = stage_two.get("steps") or []
                raw_gaps = stage_two.get("decomposition_gaps") or []

        if not raw_steps and not raw_gaps:
            raw_gaps = self._generate_fallback_gaps(
                text, stage_one.get("reference_pipeline_ids")
                or stage_one.get("pipeline_ids")
                or []
            )

        decision = {
            "mode": "custom",
            "reason": stage_two.get("reason") or stage_one.get("reason"),
            "analysis": stage_one.get("analysis"),
            "pipeline_ids": [],
            "reference_pipeline_ids": (
                stage_two.get("reference_pipeline_ids")
                or stage_one.get("reference_pipeline_ids")
                or stage_one.get("pipeline_ids")
                or []
            ),
            "decomposition_gaps": raw_gaps,
            "steps": raw_steps,
        }
        return decision, self._merge_planner_metadata(stage_one_metadata, stage_two_metadata)

    @staticmethod
    def _request_implies_pairing(text: str) -> bool:
        """Detect paired-sample intent from user request text."""
        lowered = text.lower()
        has_tumor = "肿瘤" in text or "tumor" in lowered
        has_normal = "正常" in text or "normal" in lowered
        has_pairing_hint = any(
            k in text or k in lowered
            for k in ("配对", "成对", "paired", "pair", "体细胞", "somatic", "tumor-normal")
        )
        return (has_tumor and has_normal) or has_pairing_hint

    def _generate_fallback_gaps(
        self, text: str, reference_pipeline_ids: Sequence[str]
    ) -> List[Dict[str, Any]]:
        """Synthesize decomposition gaps from catalog facts when LLM returns empty gaps.

        This avoids the silent "custom mode has no valid steps" fallback and makes
        the blocker reason stable and reproducible.
        """
        gaps: List[Dict[str, Any]] = []
        if not self._request_implies_pairing(text):
            gaps.append({
                "message": "当前方法目录无法表达该请求所需的完整工具链,请补充相关原子工具或输入槽定义。"
            })
            return gaps

        # Detect merge-point candidates from reference recipes where available.
        candidate_tool_ids: Set[str] = set()
        for pid in reference_pipeline_ids:
            for step in self._neo4j_pipeline_steps(pid):
                deps = step.get("depends_on") or []
                if isinstance(deps, str):
                    deps = [deps]
                if len(deps) >= 2:
                    suffixes: Set[str] = set()
                    for dep in deps:
                        if dep.endswith("_tumor") or dep.endswith("_T"):
                            suffixes.add("tumor")
                        elif dep.endswith("_normal") or dep.endswith("_N"):
                            suffixes.add("normal")
                    if len(suffixes) >= 2:
                        candidate_tool_ids.add(step.get("tool_id"))

        # Fallback candidate discovery: atomic tools that are plausible merge
        # points for paired analysis (variant calling / somatic calling).
        if not candidate_tool_ids:
            merge_keywords = (
                "变异", "somatic", "variant", "calling", "call", "mutect",
                "haplotype", "体细胞", "gatk", "bcftools", "snpeff",
            )
            for tool_id, method in self.registered_methods.methods.items():
                text_signature = " ".join([
                    tool_id.lower(),
                    method.name.lower(),
                    (method.description or "").lower(),
                ])
                if any(k.lower() in text_signature for k in merge_keywords):
                    candidate_tool_ids.add(tool_id)

        found_merge_gap = False
        for tool_id in sorted(candidate_tool_ids):
            method = self.registered_methods.methods.get(tool_id)
            if not method:
                continue
            data_slots = [
                slot for slot in method.inputs
                if any(term in slot.get("name", "").lower() for term in ("bam", "fastq", "vcf", "cram"))
            ]
            # A merge point must have at least one sample-level slot, but only
            # one of them: it cannot host two independent sample branches.
            if len(data_slots) == 1:
                found_merge_gap = True
                slot = data_slots[0]
                slot_name = slot["name"]
                gaps.append({
                    "message": (
                        f"配对样本汇合无法表达:{tool_id} 在当前目录中只注册了 1 个 "
                        f"{slot_name} 输入槽,无法同时接收 tumor_{slot_name}, "
                        f"normal_{slot_name}。需要为该工具补充分样本输入槽。"
                    )
                })

        if not found_merge_gap:
            gaps.append({
                "message": "当前方法目录无法表达配对样本分析所需的输入槽结构,无法完成原子化拆解。"
            })
        return gaps

    def _pipeline_menu_lines(self) -> List[str]:
        lines = []
        for pipeline_id in sorted(self.registered_methods.pipeline_methods):
            method = self.registered_methods.pipeline_methods[pipeline_id]
            steps = [step["tool_id"] for step in self._neo4j_pipeline_steps(pipeline_id)]
            inputs = [
                f"{item['name']}[{item.get('artifact') or 'file'}]"
                for item in method.inputs
            ]
            outputs = [
                f"{item['name']}[{item.get('artifact') or 'file'}]"
                for item in method.outputs
            ]
            description = re.sub(r"\s+", " ", method.description).strip()
            constraint = PIPELINE_ROUTING_CONSTRAINTS.get(pipeline_id, "")
            decomposition_status = (
                "neo4j_locked_recipe"
                if self.registered_methods.pipeline_steps.get(pipeline_id)
                else "neo4j_pipeline_level_tool"
            )
            lines.append(
                f"- {pipeline_id} | {method.name} | {description[:260]} | "
                f"inputs=[{', '.join(inputs)}] | outputs=[{', '.join(outputs)}] | "
                f"locked_steps={steps} | constraints={constraint or 'see declared inputs and outputs'} | "
                f"decomposition_status={decomposition_status} | source=neo4j"
            )
        return lines

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

    @staticmethod
    def _standard_has_coverage_gap(decision: Dict[str, Any]) -> bool:
        if decision.get("uncovered_requirements"):
            return True
        selected = set(decision.get("pipeline_ids") or [])
        for assessment in decision.get("pipeline_assessments") or []:
            if not isinstance(assessment, dict) or assessment.get("pipeline_id") not in selected:
                continue
            if assessment.get("functional_coverage") in {"partial", "none"}:
                return True
            if assessment.get("output_match") in {"partial", "mismatch"}:
                return True
            if assessment.get("uncovered_requirements"):
                return True
        return False

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
                f"- {tool_id} | catalog_id={method['catalog_id']} | "
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

    @staticmethod
    def _merge_planner_metadata(*items: Dict[str, Any]) -> Dict[str, Any]:
        def total(field: str) -> Optional[int]:
            values = [item.get(field) for item in items if item.get(field) is not None]
            return sum(int(value) for value in values) if values else None

        return {
            "used": all(item.get("used") for item in items),
            "status": "ok" if all(item.get("status") == "ok" for item in items) else "partial",
            "model": next((item.get("model") for item in reversed(items) if item.get("model")), None),
            "prompt_tokens": total("prompt_tokens"),
            "completion_tokens": total("completion_tokens"),
            "total_tokens": total("total_tokens"),
            "calls": sum(int(item.get("calls") or 0) for item in items),
            "stages": [stage for item in items for stage in (item.get("stages") or [])],
            "force_custom": any(bool(item.get("force_custom")) for item in items),
        }

    def _capability_intent(self, text: str) -> Optional[Dict[str, Any]]:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not normalized:
            return None
        if self._explicit_customization(normalized):
            return None
        if any(hint in normalized for hint in self.RECOMMENDATION_HINTS):
            return None
        browse = any(hint.lower() in normalized for hint in self.CAPABILITY_BROWSE_HINTS)
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

    def _known_standard_pipeline_ids(self, text: str) -> List[str]:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not normalized or self._explicit_customization(normalized):
            return []
        available = self.registered_methods.pipeline_methods

        has_landscape = any(
            term in normalized
            for term in ("突变景观", "oncoplot", "瀑布图", "高频突变")
        )
        has_tmb = any(
            term in normalized for term in ("tmb", "肿瘤突变负荷", "突变负荷")
        )
        if has_landscape and has_tmb:
            ids = ["wes_somatic_maf_landscape", "tmb_survival_analysis"]
            if all(pipeline_id in available for pipeline_id in ids):
                return ids

        has_go = bool(re.search(r"(?:\bgo\b|go\s*富集|go功能)", normalized))
        has_pathway = any(
            term in normalized for term in ("kegg", "reactome", "通路富集")
        )
        has_joint_request = any(
            term in normalized for term in ("同时", "都做", "一起", "以及", "和")
        )
        if has_go and has_pathway and has_joint_request:
            ids = ["diff_expr_go", "diff_expr_kegg"]
            if all(pipeline_id in available for pipeline_id in ids):
                return ids

        has_rna_fastq = "fastq" in normalized and any(
            term in normalized for term in ("rna-seq", "rnaseq", "bulk rna")
        )
        has_rna_output = any(
            term in normalized
            for term in (
                "完整上游", "上游分析", "表达矩阵", "表达计数", "表达定量",
                "count矩阵", "count 矩阵", "featurecounts", "rsem",
            )
        )
        if has_rna_fastq and has_rna_output and "rnaseq_singletask" in available:
            return ["rnaseq_singletask"]

        has_ubam = any(
            term in normalized
            for term in ("ubam", "未比对 bam", "unmapped bam", "fastq 转 bam")
        )
        if "fastq" in normalized and has_ubam and "paired_fastq_to_unmapped_bam" in available:
            return ["paired_fastq_to_unmapped_bam"]
        return []

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
        return self._attach_plan(result, plan)

    def _standard_plan(
        self,
        text: str,
        decision: Dict[str, Any],
        metadata: Dict[str, Any],
        top_k: int,
        expand_standard_steps: bool = True,
    ) -> Dict[str, Any]:
        requested_ids = self._valid_pipeline_ids(decision.get("pipeline_ids"), top_k)
        if requested_ids:
            result = self.router.route(text, top_k=top_k, allow_llm=False, selected_pipeline_ids=requested_ids)
        else:
            candidates = self.router.route(text, top_k=14, allow_llm=False)
            requested_ids = [
                item.get("pipeline_id")
                for item in candidates.get("matched_pipelines") or []
                if (
                    float(item.get("confidence") or 0) >= 0.7
                    and item.get("pipeline_id") in self.registered_methods.pipeline_methods
                )
            ][:top_k]
            if not requested_ids and not metadata.get("used"):
                # 仅规则兜底路径允许无条件取 router 第一名；LLM 决策为 standard
                # 却没给出 pipeline_id 时，不得把低置信候选包装成校验通过的确认结果。
                requested_ids = [
                    item.get("pipeline_id")
                    for item in candidates.get("matched_pipelines") or []
                    if item.get("pipeline_id") in self.registered_methods.pipeline_methods
                ][:1]
            result = self.router.route(text, top_k=top_k, allow_llm=False, selected_pipeline_ids=requested_ids or None)
        selected_by_id = {
            item.get("pipeline_id"): item
            for item in result.get("matched_pipelines") or []
            if item.get("pipeline_id")
        }
        pipelines = []
        for pipeline_id in requested_ids:
            method = self.registered_methods.pipeline_methods.get(pipeline_id)
            if not method:
                continue
            matched = selected_by_id.get(pipeline_id) or {}
            pipelines.append({
                "order": len(pipelines) + 1,
                "pipeline_id": pipeline_id,
                "name": method.name,
                "description": method.description,
                "confidence": matched.get("confidence"),
                "inputs": method.inputs,
                "outputs": method.outputs,
                "internal_steps": self._neo4j_pipeline_steps(pipeline_id),
                "internal_steps_locked": True,
                "source": "neo4j",
                "quality_gate": self._quality_gate_for_request(pipeline_id, text),
            })
        result["matched_pipelines"] = [
            {
                "pipeline_id": item["pipeline_id"],
                "name": item["name"],
                "description": item["description"],
                "confidence": item.get("confidence"),
                "reason": decision.get("reason") or "",
                "inputs": item["inputs"],
                "outputs": item["outputs"],
                "internal_steps": item["internal_steps"],
                "source": "neo4j",
            }
            for item in pipelines
        ]
        result["capabilities_count"] = len(self.registered_methods.pipeline_methods)
        plan = {
            "mode": "standard",
            "label": "预制菜",
            "reason": decision.get("reason") or "需求可由标准 pipeline 原样完成。",
            "analysis": decision.get("analysis"),
            "pipeline_ids": [item["pipeline_id"] for item in pipelines],
            "pipelines": pipelines,
            "coverage_assessment": {
                "requirements": decision.get("requirements") or {},
                "pipeline_assessments": decision.get("pipeline_assessments") or [],
                "uncovered_requirements": decision.get("uncovered_requirements") or [],
            },
            "validation": {"ok": bool(pipelines), "errors": [] if pipelines else ["未匹配到标准 pipeline"]},
            "expand_standard_steps": bool(expand_standard_steps),
            "planner_metadata": metadata,
        }
        return self._attach_plan(result, plan)

    def _custom_plan(
        self,
        text: str,
        decision: Dict[str, Any],
        metadata: Dict[str, Any],
        top_k: int,
    ) -> Dict[str, Any]:
        reference_ids = self._valid_pipeline_ids(
            decision.get("reference_pipeline_ids") or decision.get("pipeline_ids"), top_k
        )
        result = self.router.route(text, top_k=top_k, allow_llm=False, selected_pipeline_ids=reference_ids or None)
        steps, validation = self._validate_custom_steps(decision.get("steps") or [])
        raw_gaps = decision.get("decomposition_gaps") or []
        decomposition_gaps: List[Dict[str, Any]] = []
        for item in raw_gaps:
            if isinstance(item, dict):
                decomposition_gaps.append(item)
            elif isinstance(item, str):
                decomposition_gaps.append({"message": item})
        if decomposition_gaps:
            validation["ok"] = False
            validation["errors"].insert(0, "所需内部方法尚未完成原子化拆解，当前方法目录无法忠实表达该修改")
            validation["decomposition_gaps"] = decomposition_gaps
        if not metadata.get("used"):
            validation["ok"] = False
            validation["errors"].insert(0, "自助餐模式需要 LLM 从方法闭集中生成步骤；当前未启用或不可用")
        if self._request_implies_pairing(text) and validation.get("ok"):
            paired_data = self.router.matcher.match(
                result.get("intent") or {},
                [{"pipeline_id": "wes_somatic_pair"}],
                limit=10,
            )
            result["matched_data"] = paired_data
            result["agent_input"] = build_agent_input(
                [{
                    "pipeline_id": "wes_somatic_pair",
                    "name": "paired tumor-normal WES data profile",
                    "confidence": 1.0,
                    "reason": "validated paired custom chain",
                }],
                paired_data,
                result.get("intent") or {},
                metadata,
                allow_llm_summary=False,
            )
            if isinstance(result.get("result"), dict):
                result["result"]["matched_data"] = paired_data
                result["result"]["agent_input"] = result["agent_input"]
        references = []
        for item in result.get("matched_pipelines") or []:
            references.append({
                "pipeline_id": item.get("pipeline_id"),
                "name": item.get("name"),
                "quality_gate": self._quality_gate_for_request(item.get("pipeline_id"), text),
            })
        plan = {
            "mode": "custom",
            "label": "自助餐",
            "reason": decision.get("reason") or "需求需要修改标准 pipeline 的内部方法。",
            "analysis": decision.get("analysis"),
            "reference_pipelines": references,
            "methods": steps,
            "validation": validation,
            "decomposition_gaps": decomposition_gaps,
            "execution_status": (
                "blocked_by_incomplete_method_decomposition"
                if decomposition_gaps else "draft_requires_pipeline_materialization"
            ),
            "method_catalog_status": {
                **METHOD_CATALOG_STATUS,
                "registered_method_count": len(self.registered_methods.methods),
            },
            "planner_metadata": metadata,
        }
        agent_input = result.get("agent_input") or {}
        previous_pipeline = agent_input.get("pipeline_id")
        agent_input["pipeline_id"] = None
        agent_input["workflow_kind"] = "custom_draft"
        agent_input.setdefault("debug", {})["reference_pipeline_id"] = previous_pipeline
        result["agent_input"] = agent_input
        if isinstance(result.get("result"), dict):
            result["result"]["agent_input"] = agent_input
        return self._attach_plan(result, plan)

    def _validate_custom_steps(
        self,
        raw_steps: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        errors: List[str] = []
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
                errors.append(f"{step_id}.{input_name} 缺少 asset_role 或 from")
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
            raw_dependencies = raw_step.get("depends_on") or []
            if isinstance(raw_dependencies, str):
                raw_dependencies = [raw_dependencies]
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

    def _attach_plan(self, result: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        result["workflow_mode"] = plan["mode"]
        result["workflow_plan"] = plan
        if isinstance(result.get("result"), dict):
            result["result"]["workflow_mode"] = plan["mode"]
            result["result"]["workflow_plan"] = plan
        if plan["mode"] == "capability":
            result["answer"] = str(
                (plan.get("capability_answer") or {}).get("summary")
                or plan.get("reason")
                or "已返回当前 Neo4j 能力目录。"
            )
        elif plan["mode"] == "standard":
            names = " -> ".join(item.get("name") or item["pipeline_id"] for item in plan.get("pipelines") or [])
            result["answer"] = f"预制菜模式：{names or '未匹配到标准流程'}。标准 pipeline 内部步骤保持不变。"
        else:
            names = " -> ".join(item.get("name") or item["tool_id"] for item in plan.get("methods") or [])
            result["answer"] = f"自助餐模式：{names or '尚未生成有效方法链'}。该结果是待物化和验证的流程草案。"
        self._apply_agent_contract(result, plan)
        return result

    def _quality_gate_for_request(
        self,
        pipeline_id: Optional[str],
        text: str,
        assets: Sequence[Dict[str, Any]] = (),
    ) -> Dict[str, Any]:
        base = PIPELINE_QUALITY_GATES.get(pipeline_id or "", {
            "status": "reviewed_core_ok", "severity": "low", "issues": []
        })
        gate = {
            **base,
            "issues": list(base.get("issues") or []),
            "blocks_execution": base.get("severity") in {"critical", "high"},
            "non_applicable_issues": [],
        }
        normalized = str(text or "").lower()
        roles = {str(asset.get("role") or "") for asset in assets}
        paired = (
            any(term in normalized for term in ("paired-end", "paired end", "pair-end", "双端", "r1/r2", "r1 和 r2"))
            or {"fastq_r1", "fastq_r2"}.issubset(roles)
        )
        single = any(term in normalized for term in ("single-end", "single end", "单端"))

        if pipeline_id == "rnaseq_singletask":
            single_end_issue = "单端 Trim Galore 输出与 R2 守卫存在已知问题"
            runtime_issue = "continueOnReturnCode 会掩盖失败"
            if paired and not single:
                gate.update({
                    "status": "paired_end_supported_with_warning",
                    "severity": "medium",
                    "issues": [runtime_issue],
                    "blocks_execution": False,
                    "non_applicable_issues": [single_end_issue],
                    "scope_reason": "本次为双端 RNA-seq，已知单端分支缺陷不适用。",
                })
            elif single:
                gate.update({
                    "status": "single_end_blocked",
                    "severity": "high",
                    "issues": [single_end_issue, runtime_issue],
                    "blocks_execution": True,
                    "scope_reason": "本次明确要求单端 RNA-seq，命中已知致命分支缺陷。",
                })
            else:
                gate.update({
                    "status": "read_layout_confirmation_required",
                    "severity": "medium",
                    "issues": ["需确认输入是双端；单端分支存在已知问题", runtime_issue],
                    "blocks_execution": False,
                    "scope_reason": "需求未明确 read layout；若资产匹配到 R1/R2，可按双端路径执行。",
                })
        elif pipeline_id == "paired_fastq_to_unmapped_bam":
            gate.update({
                "status": "input_pair_validation_required",
                "severity": "medium",
                "issues": ["执行前核对 R1/R2 来自同一样本，并补齐 Read Group 元数据"],
                "blocks_execution": False,
                "non_applicable_issues": ["原示例 fastq_2 曾错误指向 R1；不代表 pipeline 转换逻辑错误"],
                "scope_reason": "风险位于示例输入和配对校验，不阻断正确输入上的标准 uBAM 流程。",
            })
        return gate

    def _apply_agent_contract(self, result: Dict[str, Any], plan: Dict[str, Any]) -> None:
        if plan["mode"] == "capability":
            self._apply_capability_contract(result, plan)
            return
        legacy = dict(result.get("agent_input") or {})
        assets = self._build_assets(legacy)
        intent = result.get("intent") or {}
        query_text = str(intent.get("query_text") or result.get("nl") or "")
        if plan["mode"] == "standard":
            for pipeline in plan.get("pipelines") or []:
                pipeline["quality_gate"] = self._quality_gate_for_request(
                    pipeline.get("pipeline_id"), query_text, assets
                )
            tool_chain, missing, _parameters = self._standard_tool_chain(plan, assets)
        else:
            tool_chain, missing, _parameters = self._custom_tool_chain(plan, assets)
        # 标准流程选对，但 LLM 逐项评估里把某个被选中 pipeline 的输入判为
        # input_match == "mismatch"（例如聚类要 raw count、用户手里是 TPM），
        # 此时资产匹配可能已从其他 study 顶上一份类型不符的文件，让 missing 为空、
        # 状态误报 ready。这里把类型不匹配显式提升为缺数据：流程对、数据缺。
        # 只在 standard 模式生效，不恢复已删除的 mismatch→custom 降级分支。
        type_mismatches: List[Dict[str, Any]] = []
        if plan["mode"] == "standard":
            type_mismatches = self._data_type_mismatches(plan, tool_chain)
        plan_validation = plan.get("validation") or {}
        if not tool_chain or not plan_validation.get("ok"):
            orchestration_status = "no_match"
        elif missing:
            orchestration_status = "missing_data"
        elif type_mismatches:
            orchestration_status = "missing_data"
        elif plan["mode"] == "custom":
            orchestration_status = "draft"
        else:
            orchestration_status = "ready"
        selection_status = "missing_assets" if orchestration_status == "missing_data" else orchestration_status
        study_accession = self._study_accession(legacy, assets)
        match_key = json.dumps({
            "query": query_text,
            "mode": plan["mode"],
            "pipelines": plan.get("pipeline_ids") or [x.get("pipeline_id") for x in plan.get("reference_pipelines") or []],
            "steps": [x.get("step_id") for x in tool_chain],
            "study": study_accession,
        }, ensure_ascii=False, sort_keys=True)
        match_id = "match-" + hashlib.sha256(match_key.encode("utf-8")).hexdigest()[:16]
        combined_missing = type_mismatches + missing
        if combined_missing:
            if type_mismatches:
                feasibility_message = "流程选择已确定，但输入数据类型不匹配：" + "；".join(
                    item["reason"] for item in type_mismatches
                )
            else:
                feasibility_message = "仍缺少流程所需的用户样本数据。"
        else:
            feasibility_message = "流程所需的用户样本数据已匹配。"
        contract = {
            "execution_kind": "tool_chain",
            "workflow_mode": plan["mode"],
            "match_id": match_id,
            "study_accession": study_accession,
            "assets": assets,
            "tool_chain": tool_chain,
            "feasibility": {
                "status": "missing_assets" if combined_missing else "ready",
                "missing_assets": combined_missing,
                "data_ready": not combined_missing,
                "message": feasibility_message,
            },
            "selection_reason": str(plan.get("reason") or ""),
            "orchestration_status": orchestration_status,
            "orchestration_ready": orchestration_status == "ready",
            "orchestration_message": self._orchestration_status_message(orchestration_status),
            "extensions": {
                "quality_gates": {
                    item.get("pipeline_id"): item.get("quality_gate")
                    for item in (plan.get("pipelines") or plan.get("reference_pipelines") or [])
                    if item.get("pipeline_id")
                },
                "plan_validation": plan_validation,
            },
            # Compatibility fields for existing consumers during the v1 transition.
            "pipeline_id": legacy.get("pipeline_id"),
            "files": legacy.get("files") or [],
            "files_text": legacy.get("files_text") or "",
        }
        contract_validation = self._validate_agent_contract(contract)
        contract["extensions"]["contract_validation"] = contract_validation
        if not contract_validation["ok"]:
            selection_status = "no_match"
            orchestration_status = "no_match"
            contract["orchestration_status"] = orchestration_status
            contract["orchestration_ready"] = False
            contract["orchestration_message"] = self._orchestration_status_message(orchestration_status)
        result["schema_version"] = "tool-chain/v1"
        result["selection_status"] = selection_status
        result["orchestration_status"] = orchestration_status
        result["orchestration_ready"] = orchestration_status == "ready"
        result["orchestration_message"] = contract["orchestration_message"]
        result["agent_input"] = contract
        result["intent"] = {
            **intent,
            "query_text": query_text,
            "analysis_goal": intent.get("analysis_goal"),
            "requested_outputs": intent.get("requested_outputs") or [],
        }
        if isinstance(result.get("result"), dict):
            result["result"]["schema_version"] = "tool-chain/v1"
            result["result"]["selection_status"] = selection_status
            result["result"]["orchestration_status"] = orchestration_status
            result["result"]["orchestration_ready"] = orchestration_status == "ready"
            result["result"]["orchestration_message"] = result["orchestration_message"]
            result["result"]["agent_input"] = contract
            result["result"]["intent"] = result["intent"]

    def _data_type_mismatches(
        self, plan: Dict[str, Any], tool_chain: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """标准流程逐项评估中被选中 pipeline 的 input_match == "mismatch" 时，
        把它转成 missing_assets 条目。流程选对、数据类型不符——这不是 ready，
        也不该降级 custom，而是"流程对、数据缺"。"""
        assessment_map: Dict[str, Dict[str, Any]] = {}
        coverage = plan.get("coverage_assessment") or {}
        for assessment in coverage.get("pipeline_assessments") or []:
            if isinstance(assessment, dict) and assessment.get("pipeline_id"):
                assessment_map[assessment["pipeline_id"]] = assessment
        selected_ids = {step.get("tool_id") for step in tool_chain}
        records: List[Dict[str, Any]] = []
        for pipeline_id, assessment in assessment_map.items():
            if pipeline_id not in selected_ids:
                continue
            if assessment.get("input_match") != "mismatch":
                continue
            note = str(assessment.get("note") or "").strip() or (
                "该流程所需的输入数据类型与用户提供的数据不匹配。"
            )
            records.append({
                "step_id": pipeline_id,
                "input": "data_type_match",
                "role": "user_input",
                "reason": note,
            })
        return records

    def _apply_capability_contract(
        self, result: Dict[str, Any], plan: Dict[str, Any]
    ) -> None:
        intent = result.get("intent") or {}
        query_text = str(intent.get("query_text") or result.get("nl") or "")
        answer = plan.get("capability_answer") or {}
        match_key = json.dumps({
            "query": query_text,
            "mode": "capability",
            "pipelines": [
                item.get("tool_id") for item in answer.get("pipelines") or []
            ],
            "atomic_tools": [
                item.get("tool_id") for item in answer.get("atomic_tools") or []
            ],
        }, ensure_ascii=False, sort_keys=True)
        message = "这是能力目录查询，不生成执行流程，也不进行数据资产可行性判断。"
        contract = {
            "execution_kind": "information",
            "workflow_mode": "capability",
            "match_id": "capability-" + hashlib.sha256(
                match_key.encode("utf-8")
            ).hexdigest()[:16],
            "study_accession": None,
            "assets": [],
            "tool_chain": [],
            "feasibility": {
                "status": "not_applicable",
                "missing_assets": [],
                "data_ready": None,
                "message": message,
            },
            "selection_reason": str(plan.get("reason") or ""),
            "orchestration_status": "information",
            "orchestration_ready": False,
            "orchestration_message": message,
            "extensions": {
                "capability_answer": answer,
                "plan_validation": plan.get("validation") or {"ok": True, "errors": []},
                "contract_validation": {"ok": True, "errors": []},
            },
            "pipeline_id": None,
            "files": [],
            "files_text": "",
        }
        result["schema_version"] = "tool-chain/v1"
        result["selection_status"] = "information"
        result["orchestration_status"] = "information"
        result["orchestration_ready"] = False
        result["orchestration_message"] = message
        result["agent_input"] = contract
        result["intent"] = {
            **intent,
            "query_text": query_text,
            "analysis_goal": intent.get("analysis_goal") or "查询当前工作流能力目录",
            "requested_outputs": intent.get("requested_outputs") or [],
        }
        if isinstance(result.get("result"), dict):
            result["result"].update({
                "schema_version": "tool-chain/v1",
                "selection_status": "information",
                "orchestration_status": "information",
                "orchestration_ready": False,
                "orchestration_message": message,
                "agent_input": contract,
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
                "sample_accession": detail.get("sample_accession"),
                "run_accession": detail.get("run_accession"),
                "individual_accession": detail.get("individual_accession"),
                "sample_role": detail.get("sample_role"),
                "mate": (
                    read_pair if read_pair in {"r1", "r2"}
                    else "r1" if role == "fastq_r1"
                    else "r2" if role == "fastq_r2"
                    else None
                ),
            })
        return assets

    def _selection_status_message(self, status: str) -> str:
        return {
            "ready": "用户样本数据和工具引用齐全，流程编排已确定。",
            "missing_assets": "工具链已生成，但仍缺少必需的用户样本数据。",
            "requires_review": "兼容状态：旧调用端要求复核流程实现风险。",
            "draft": "自定义工具链引用有效，但仍需执行端物化并验证。",
            "no_match": "未形成通过契约校验的工具链。",
        }.get(status, status)

    @staticmethod
    def _orchestration_status_message(status: str) -> str:
        return {
            "ready": "标准流程与工具链结构已确定。",
            "missing_data": "标准流程已确定，但仍缺少必需的用户样本数据。",
            "draft": "自定义方法链草案已形成，仍需执行端物化。",
            "requires_review": "兼容状态：旧调用端要求复核流程实现风险。",
            "no_match": "尚未形成通过闭集与结构校验的流程。",
        }.get(status, status)

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

    def _standard_tool_chain(
        self, plan: Dict[str, Any], assets: Sequence[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        chain: List[Dict[str, Any]] = []
        missing: List[Dict[str, Any]] = []
        asset_usage: Dict[str, int] = {}
        prior_outputs: Dict[str, Tuple[str, str]] = {}
        for pipeline in plan.get("pipelines") or []:
            pipeline_id = pipeline.get("pipeline_id") or "pipeline"
            method = self.registered_methods.pipeline_methods.get(pipeline_id)
            if not method:
                missing.append({
                    "step_id": pipeline_id,
                    "input": "neo4j_tool_contract",
                    "role": "pipeline_not_registered",
                })
                continue
            registered_recipe = self.registered_methods.pipeline_steps.get(pipeline_id) or []
            if plan.get("expand_standard_steps", False) and registered_recipe:
                recipe_steps, recipe_validation = self._expanded_pipeline_methods(pipeline_id)
                if not recipe_validation["ok"]:
                    missing.append({
                        "step_id": pipeline_id,
                        "input": "locked_recipe_validation",
                        "role": "invalid_registered_recipe",
                        "errors": recipe_validation["errors"],
                    })
                    continue
                for recipe_step in recipe_steps:
                    bindings: Dict[str, Dict[str, Any]] = {}
                    for input_name, binding in (recipe_step.get("inputs") or {}).items():
                        if binding.get("from"):
                            bindings[input_name] = {"from": dict(binding["from"])}
                            continue
                        role = str(binding.get("asset_role") or "data_file")
                        spec = next(
                            (item for item in self.registered_methods.methods[recipe_step["tool_id"]].inputs if item["name"] == input_name),
                            {},
                        )
                        asset = self._select_asset(
                            role, assets, asset_usage,
                            step_id=str(recipe_step.get("step_id") or ""),
                            slot_spec=spec,
                        )
                        if asset:
                            bindings[input_name] = {"asset_id": asset["asset_id"]}
                        elif role not in EXECUTION_MANAGED_ASSET_ROLES:
                            missing.append({
                                "step_id": recipe_step.get("step_id"),
                                "input": input_name,
                                "role": role,
                            })
                    chain.append({
                        "step_id": recipe_step.get("step_id"),
                        "tool_id": recipe_step.get("tool_id"),
                        "inputs": bindings,
                        "depends_on": recipe_step.get("depends_on") or [],
                        "parent_pipeline_id": pipeline_id,
                        "decomposition_status": "expanded_locked_recipe",
                    })
                continue
            bindings: Dict[str, Dict[str, Any]] = {}
            for spec in method.inputs:
                artifact = str(spec.get("artifact") or "")
                if artifact in prior_outputs:
                    source_step, source_output = prior_outputs[artifact]
                    bindings[spec["name"]] = {
                        "from": {"step_id": source_step, "output": source_output}
                    }
                    continue
                role = self._role_for_input(spec["name"])
                asset = self._select_asset(
                    role, assets, asset_usage, step_id=pipeline_id, slot_spec=spec
                )
                if asset:
                    bindings[spec["name"]] = {"asset_id": asset["asset_id"]}
                elif (
                    not spec["optional"]
                    and role not in EXECUTION_MANAGED_ASSET_ROLES
                ):
                    missing.append({
                        "step_id": pipeline_id,
                        "input": spec["name"],
                        "role": role,
                    })
            pipeline_step = {"step_id": pipeline_id, "tool_id": pipeline_id, "inputs": bindings}
            if plan.get("expand_standard_steps", False):
                pipeline_step.update({
                    "decomposition_status": "pipeline_level_unexpanded",
                    "expandable": False,
                })
            chain.append(pipeline_step)
            for output in method.outputs:
                artifact = str(output.get("artifact") or "")
                if artifact:
                    prior_outputs[artifact] = (pipeline_id, output["name"])
        return chain, self._dedupe_records(missing), []

    def _expanded_pipeline_methods(
        self, pipeline_id: str
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Translate a locked HAS_STEP recipe into the same bindings custom mode validates."""
        recipe = self.registered_methods.pipeline_steps.get(pipeline_id) or []
        steps: List[Dict[str, Any]] = []
        prior: List[Tuple[str, str, str]] = []
        for item in recipe:
            tool_id = str(item.get("tool_id") or "")
            method = self.registered_methods.methods.get(tool_id)
            if not method:
                continue
            inputs: Dict[str, Dict[str, Any]] = {}
            for spec in method.inputs:
                input_name = str(spec["name"])
                source = next((
                    (step_id, output_name)
                    for step_id, source_tool, output_name in reversed(prior)
                    if (source_tool, output_name, tool_id, input_name)
                    in self.registered_methods.data_edges
                ), None)
                if source:
                    inputs[input_name] = {
                        "from": {"step_id": source[0], "output": source[1]}
                    }
                elif not spec.get("optional") or str(spec.get("artifact")) == "raw_fastq_read":
                    inputs[input_name] = {
                        "asset_role": self._canonical_asset_role(
                            input_name, str(spec.get("artifact") or "data_file")
                        )
                    }
            step_id = str(item.get("step_id") or tool_id)
            steps.append({
                "step_id": step_id,
                "tool_id": tool_id,
                "inputs": inputs,
                "depends_on": list(item.get("depends_on") or []),
            })
            for output in method.outputs:
                prior.append((step_id, tool_id, str(output["name"])))
        return self._validate_custom_steps(steps)

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
            "vcf_file", "reference_file", "data_file",
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

    def _validate_agent_contract(self, contract: Dict[str, Any]) -> Dict[str, Any]:
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

    def _valid_pipeline_ids(self, values: Any, top_k: int) -> List[str]:
        if isinstance(values, str):
            values = [values]
        valid: List[str] = []
        for value in values or []:
            pipeline_id = str(value)
            if (
                pipeline_id in self.router.catalog.pipelines
                and pipeline_id in self.registered_methods.pipeline_methods
                and pipeline_id not in valid
            ):
                valid.append(pipeline_id)
        return valid[:top_k]

    def _rule_mode(self, text: str) -> str:
        if self._explicit_customization(text):
            return "custom"
        if self._capability_intent(text):
            return "capability"
        return "standard"


_COMPOSER: Optional[WorkflowComposer] = None


def get_composer() -> WorkflowComposer:
    global _COMPOSER
    if _COMPOSER is None:
        _COMPOSER = WorkflowComposer()
    return _COMPOSER


def compose_workflow_request(
    nl_text: Any,
    top_k: int = 5,
    force_custom: bool = False,
    expand_standard_steps: bool = True,
) -> Dict[str, Any]:
    return get_composer().plan(
        nl_text,
        top_k=top_k,
        force_custom=force_custom,
        expand_standard_steps=expand_standard_steps,
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
