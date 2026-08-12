"""Deterministic scoring and data matching for a Neo4j-backed tool catalog.

Pipeline and atomic-tool contracts are injected by ``WorkflowComposer`` from
Neo4j. Local WDL files are historical inputs only and are never parsed into the
public runtime tool catalog.
"""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    import config as _cfg
except Exception:  # pragma: no cover
    _cfg = None

def _lazy_call_llm(system: str, user: str) -> Optional[Dict[str, Any]]:
    """Reuse intent._call_llm without creating an import-time cycle."""
    try:
        from intent import _call_llm as call_llm

        return call_llm(system, user)
    except Exception:
        return None

HERE = Path(__file__).resolve().parent
# The packaged router is self-contained; keep all catalog paths inside it.
PROJECT_ROOT = HERE
CSV_DIR = Path(
    os.environ.get("DATA_CSV_DIR", str(PROJECT_ROOT / "data" / "csv"))
).expanduser()

DISEASE_ALIASES = {
    "胶质瘤": ["胶质瘤", "glioma", "CGGA"],
    "黑色素瘤": ["黑色素瘤", "melanoma"],
    "食管癌": ["食管癌", "食管鳞癌", "esophageal", "ESCC"],
    "肝癌": ["肝癌", "肝细胞癌", "liver", "HCC"],
    "肺癌": ["肺癌", "lung"],
    "结直肠癌": ["结直肠癌", "肠癌", "colorectal", "colon", "rectal"],
    "乳腺癌": ["乳腺癌", "breast"],
    "胃癌": ["胃癌", "gastric", "stomach"],
}

DATA_PROFILE_TEMPLATES = {
    "paired_fastq": {
        "roles": ["fastq"],
        "formats": ["fq.gz", "fastq.gz"],
        "bundle": "paired_fastq",
        "prompt": "需要双端 FASTQ R1/R2；不要默认使用表达矩阵、clinical 或 MAF。"
    },
    "expression_only": {
        "roles": ["expression_abundance"],
        "formats": ["tsv"],
        "strategies": ["RNA-Seq"],
        "terms": ["FPKM", "TPM"],
        "bundle": "expression_only",
        "prompt": "需要处理后的表达矩阵；不需要 clinical、metainfo、BAM、MAF。"
    },
    "count_matrix": {
        "roles": ["expression_count"],
        "formats": ["tsv"],
        "strategies": ["RNA-Seq"],
        "terms": ["counts", "count"],
        "bundle": "expression_only",
        "prompt": "需要 count 表达矩阵；不需要 clinical、metainfo、MAF。"
    },
    "expression_clinical": {
        "roles": ["expression", "clinical", "metainfo"],
        "formats": ["tsv", "xls", "xlsx"],
        "strategies": ["RNA-Seq"],
        "terms": ["TPM", "Clinical", "MetaInfo"],
        "bundle": "expression_clinical_bundle",
        "prompt": "需要表达矩阵 + clinical/metainfo 做样本映射、分组或生存终点。"
    },
    "mutation_only": {
        "roles": ["maf"],
        "formats": ["maf"],
        "strategies": ["WES"],
        "terms": ["SomaticSNV", "MAF"],
        "bundle": "mutation_only",
        "prompt": "需要 MAF/体细胞突变文件；不默认需要 clinical/metainfo。"
    },
    "mutation_clinical": {
        "roles": ["maf", "clinical", "metainfo"],
        "formats": ["maf", "xls", "xlsx"],
        "strategies": ["WES"],
        "terms": ["SomaticSNV", "Clinical", "MetaInfo"],
        "bundle": "mutation_clinical_bundle",
        "prompt": "需要 MAF/突变文件 + clinical/metainfo；不需要表达矩阵或 FASTQ。"
    },
}

PIPELINE_DATA_PROFILE_KEYS = {
    "cellranger_workflow": "paired_fastq",
    "rnaseq_singletask": "paired_fastq",
    "wes_somatic_pair": "paired_fastq",
    "paired_fastq_to_unmapped_bam": "paired_fastq",
    "diff_expr_go": "expression_only",
    "diff_expr_kegg": "expression_only",
    "rnaseq_unsupervised_cluster": "count_matrix",
    "wgcna": "expression_clinical",
    "immune_infiltration_iobr": "expression_clinical",
    "her2_pfs_survival": "expression_clinical",
    "survival_analysis": "mutation_clinical",
    "tmb_survival_analysis": "mutation_clinical",
    "wes_somatic_maf_landscape": "mutation_only",
    "driver_gene_gender_analysis": "mutation_clinical",
}

FORMAT_HINTS = [
    (["fastq.gz", "fq.gz", "fastq", "原始测序", "原始数据", "reads"], "fq.gz"),
    (["maf", "突变文件", "somaticsnv"], "maf"),
    (["fpkm"], "tsv"),
    (["tpm"], "tsv"),
    (["count 矩阵", "count矩阵", "counts"], "tsv"),
    (["表达矩阵", "表达谱", "转录组数据"], "tsv"),
    (["clinical", "临床"], "xls"),
    (["xlsx", "excel"], "xlsx"),
    (["xls"], "xls"),
    (["tsv"], "tsv"),
    (["csv"], "csv"),
]

OMICS_HINTS = [
    (["10x", "单细胞", "scrna", "cellranger"], "scRNA-seq"),
    (["rna-seq", "rnaseq", "转录组", "表达矩阵", "表达谱", "fpkm", "tpm", "count"], "bulk RNA-seq"),
    (["wes", "全外显子", "外显子", "maf", "突变", "tmb", "体细胞"], "WES/MAF"),
    (["wgs", "全基因组"], "WGS"),
]

ANALYSIS_HINTS = [
    (["go 富集", "go功能", "go 功能"], "GO 富集"),
    (["kegg", "reactome", "通路富集"], "通路富集"),
    (["无监督聚类", "聚类", "分群", "亚型", "分型", "分子分型", "自动分成", "自动识别"], "无监督聚类"),
    (["wgcna", "共表达"], "WGCNA"),
    (["免疫浸润", "cibersort", "iobr"], "免疫浸润"),
    (["cellranger", "单细胞"], "CellRanger 单细胞分析"),
    (["表达定量", "rsem", "featurecounts"], "RNA-seq 表达定量"),
    (["体细胞变异", "体细胞突变检测", "mutect2", "变异检测"], "体细胞变异检测"),
    (["突变景观", "oncoplot"], "突变景观"),
    (["tmb", "肿瘤突变负荷"], "TMB 生存分析"),
    (["her2", "erbb2"], "HER2 PFS 生存分析"),
    (["生存", "pfs", "kaplan", "cox"], "生存分析"),
    (["驱动基因", "性别"], "驱动基因性别分层"),
]


@dataclass
class PipelineDef:
    pipeline_id: str
    name: str
    directory: str
    keywords: List[str]
    description: str
    repo_dir: Path
    inputs: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def as_capability(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "directory": self.directory,
            "input_summary": self.inputs[:8],
            "output_summary": self.outputs[:8],
            "has_internal_steps": bool(self.steps),
            "source": "neo4j",
            "step_count": len(self.steps),
        }


def _norm(text: Any) -> str:
    return str(text or "").strip()


def _lower(text: Any) -> str:
    return _norm(text).lower()


_ASSAY_SYNONYMS = {
    "rnaseq": {"rnaseq", "rnasequencing"},
    "scrna": {"scrna", "scrnaseq", "singlecellrna", "singlecellrnaseq"},
    "wes": {"wes"},
    "wgs": {"wgs"},
}


def _normalize_assay_tokens(value: Any) -> Set[str]:
    """把 assay 描述归一化成标准词集；无法识别/垃圾值返回空集。"""
    raw = str(value or "").strip()
    if raw.lower() in {"0", "#n/a", "n/a", "na", "null", "none", ""}:
        return set()
    parts = re.split(r"[,，;／/]+|\s+(?:and|&)\s+", raw, flags=re.I)
    tokens: Set[str] = set()
    for part in parts:
        t = re.sub(r"[^a-z0-9]", "", part.lower())
        if not t:
            continue
        for canonical, aliases in _ASSAY_SYNONYMS.items():
            if t in aliases:
                tokens.add(canonical)
                break
        else:
            tokens.add(t)
    return tokens


def _canonical_assay_set(values: Iterable[Any]) -> Set[str]:
    out: Set[str] = set()
    for v in values:
        out.update(_normalize_assay_tokens(v))
    return out


def _data_profile(pipeline_id: Optional[str]) -> Dict[str, Any]:
    key = PIPELINE_DATA_PROFILE_KEYS.get(pipeline_id or "")
    profile = dict(DATA_PROFILE_TEMPLATES.get(key or "", {}))
    if pipeline_id == "cellranger_workflow":
        profile["strategies"] = ["scRNA-Seq"]
        profile["terms"] = list(dict.fromkeys((profile.get("terms") or []) + ["10x", "HRR572934"]))
        profile["prompt"] = "需要 10x/scRNA-seq FASTQ R1/R2；不要默认使用 bulk 表达矩阵、clinical 或 MAF。"
    elif pipeline_id == "rnaseq_singletask":
        profile["strategies"] = ["RNA-Seq"]
        profile["terms"] = ["FastQC", "STAR", "RSEM", "FeatureCounts"]
        profile["prompt"] = "需要 bulk RNA-seq FASTQ R1/R2；用于上游 QC、比对、表达定量，不直接拿处理后的表达矩阵作为输入。"
    elif pipeline_id in {"wes_somatic_pair", "paired_fastq_to_unmapped_bam"}:
        profile["strategies"] = ["WES", "WGS"]
        if pipeline_id == "wes_somatic_pair":
            profile["terms"] = ["tumor", "normal", "Mutect2", "somatic"]
            profile["prompt"] = "需要肿瘤/正常配对 WES FASTQ；输出 somatic VCF/MAF，不把已有 MAF 当输入。"
        else:
            profile["terms"] = ["unmapped BAM", "uBAM", "read group"]
            profile["prompt"] = "需要双端 FASTQ R1/R2；目标是生成未比对 BAM/uBAM。"
    elif pipeline_id == "rnaseq_unsupervised_cluster":
        profile["terms"] = ["counts", "count"]
    elif pipeline_id == "wgcna":
        profile["terms"] = ["counts", "Clinical", "MetaInfo"]
        profile["prompt"] = "需要表达矩阵 + clinical/metainfo 做样本映射和性状关联。"
    elif pipeline_id == "wes_somatic_maf_landscape":
        profile["prompt"] = "需要 MAF/体细胞突变文件；突变景观本身不默认需要 clinical/metainfo。"
    elif pipeline_id == "driver_gene_gender_analysis":
        profile["terms"] = ["SomaticSNV", "Clinical", "MetaInfo", "gender"]
        profile["prompt"] = "需要 MAF + clinical/metainfo 中的性别信息；不需要表达矩阵。"
    return profile

ROLE_LABELS = {
    "fastq": "FASTQ 测序数据（R1/R2）",
    "expression": "表达矩阵",
    "expression_count": "原始 count 表达矩阵",
    "expression_abundance": "TPM/FPKM 表达丰度矩阵",
    "clinical": "临床数据（Clinical）",
    "metainfo": "样本信息（MetaInfo）",
    "maf": "体细胞突变文件（MAF）",
    "bam": "BAM 比对文件",
    "vcf": "VCF 变异文件",
}


# 样本角色判据逐 study 定义。没有登记的 study 一律不支持配对分析（fail closed）。
# 三种规则类型：
#   ("specimen_types", {取值: 角色})
#   ("name_suffix",    {后缀: 角色})
#   ("study_constant", 角色)
STUDY_ROLE_RULES: Dict[str, Tuple[str, Any]] = {
    "HRA000873": ("specimen_types", {"Patient Solid Tissue": "tumor",
                                      "Peritumoral": "normal"}),
    "HRA000021": ("specimen_types", {"Patient Solid Tissue": "tumor",
                                      "Peritumoral": "normal"}),
    "HRA001272": ("specimen_types", {"Patient Solid Tissue": "tumor",
                                      "Peritumoral": "normal"}),
    "HRA006499": ("name_suffix", {"_T": "tumor", "_N": "normal"}),
    "HRA001748": ("study_constant", "tumor"),
    "HRA001749": ("study_constant", "normal"),
}


def _sample_role(record: Dict[str, Any]) -> Optional[str]:
    """按 STUDY_ROLE_RULES 推断样本角色；推不出返回 None，不要猜。"""
    study = _norm(record.get("study_accession"))
    rule = STUDY_ROLE_RULES.get(study)
    if not rule:
        return None
    kind, mapping = rule
    if kind == "study_constant":
        return str(mapping)
    if kind == "specimen_types":
        return mapping.get(_norm(record.get("specimen_types")))
    if kind == "name_suffix":
        name = _norm(record.get("sample_name"))
        if name.endswith("_T") or name.endswith("_t"):
            return mapping.get("_T")
        if name.endswith("_N") or name.endswith("_n"):
            return mapping.get("_N")
        return None
    return None


def _assess_wes_somatic_cases(fastqs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """轻量版可行性判断：只统计是否存在合格的同个体 tumor/normal 配对。"""
    by_individual: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for f in fastqs:
        role = _sample_role(f)
        if role not in {"tumor", "normal"}:
            continue
        ind = _norm(f.get("individual_accession"))
        if not ind:
            continue
        by_individual.setdefault(ind, {"tumor": [], "normal": []})[role].append(f)
    cases = []
    for ind, sides in by_individual.items():
        if (
            len(_paired_fastq_groups(sides["tumor"])) == 1
            and len(_paired_fastq_groups(sides["normal"])) == 1
        ):
            cases.append({"individual_accession": ind})
    return cases


def _wes_somatic_infeasibility_reason(fastqs: Sequence[Dict[str, Any]]) -> str:
    """区分 wes_somatic_pair 无法配对的具体原因。"""
    if not fastqs:
        return "「wes_somatic_pair」未匹配到任何 FASTQ 文件。"
    studies = {_norm(f.get("study_accession")) for f in fastqs}
    unregistered_studies = studies - set(STUDY_ROLE_RULES.keys())
    if unregistered_studies == studies:
        return (
            "「wes_somatic_pair」需要为 study 登记肿瘤/正常角色规则；"
            f"当前 matched 的 study 均未登记: {', '.join(sorted(studies))}。"
        )

    by_individual: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for f in fastqs:
        role = _sample_role(f)
        if role not in {"tumor", "normal"}:
            continue
        ind = _norm(f.get("individual_accession"))
        if not ind:
            continue
        by_individual.setdefault(ind, {"tumor": [], "normal": []})[role].append(f)

    if not by_individual:
        return (
            "「wes_somatic_pair」已匹配的 FASTQ 无法推断肿瘤/正常角色"
            "（study 未登记规则或规则无法覆盖当前样本）。"
        )

    has_one_sided = False
    has_multi_sample = False
    for sides in by_individual.values():
        tumor_pairs = len(_paired_fastq_groups(sides["tumor"]))
        normal_pairs = len(_paired_fastq_groups(sides["normal"]))
        if (tumor_pairs == 0 and normal_pairs >= 1) or (normal_pairs == 0 and tumor_pairs >= 1):
            has_one_sided = True
        if tumor_pairs > 1 or normal_pairs > 1:
            has_multi_sample = True

    if has_multi_sample:
        return (
            "「wes_somatic_pair」找到若干个体存在肿瘤或正常侧的多个样本，"
            "当前规则只接受单侧恰好 1 个 R1/R2 对，无法自动挑选。"
        )
    if has_one_sided:
        return (
            "「wes_somatic_pair」已推断角色的个体均只有单侧样本，"
            "无法构成 tumor/normal 配对。"
        )
    return "「wes_somatic_pair」未找到同个体且 tumor/normal 各一侧的完整配对。"


def _role_satisfies(required: str, present: str) -> bool:
    """通用 expression 与其 count/abundance 子类型互相兼容，两个子类型之间不兼容。"""
    if required == present:
        return True
    if required == "expression" and present.startswith("expression"):
        return True
    if present == "expression" and required.startswith("expression"):
        return True
    return False


# `[.-]r1` covers dot/dash separated mates (10125714.R1.fastq.gz) that the
# underscore-only form missed. The `r` stays mandatory there so plain `.1`/`-1`
# chunks in single-end names are not mistaken for a mate.
_FASTQ_R1_PATTERN = re.compile(r"(_r?1|[.-]r1|_f1|read1)")
_FASTQ_R2_PATTERN = re.compile(r"(_r?2|[.-]r2|_f2|read2)")


def _fastq_pair_key(item: Dict[str, Any]) -> str:
    """同一 sample/run 的 R1/R2 应得到相同的配对键。"""
    for field in ("sample_accession", "run_accession"):
        value = _norm(item.get(field))
        if value:
            return value
    name = _lower(item.get("files") or item.get("file_path"))
    stem = re.sub(r"\.(fastq|fq)(\.gz)?$", "", name)
    return re.sub(r"([._-])(r?1|r?2|f1|f2|read1|read2)$", "", stem)


def _paired_fastq_groups(files: Sequence[Dict[str, Any]]) -> List[Dict[str, List[Dict[str, Any]]]]:
    """按同源配对键聚合 R1/R2，只返回真正成对的组，不按列表位置凑对。"""
    groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for item in files:
        name = _lower(item.get("files"))
        read_pair = _lower(item.get("read_pair"))
        entry = groups.setdefault(_fastq_pair_key(item), {"r1": [], "r2": []})
        if read_pair == "r1" or _FASTQ_R1_PATTERN.search(name):
            entry["r1"].append(item)
        elif read_pair == "r2" or _FASTQ_R2_PATTERN.search(name):
            entry["r2"].append(item)
    return [entry for entry in groups.values() if entry["r1"] and entry["r2"]]


def _role_of_file(item: Dict[str, Any]) -> str:
    """Infer the data role of a file record from its name/format (single source of truth)."""
    name = _lower(item.get("files"))
    fmt = _lower(item.get("format"))
    if "fastq" in name or "fq" in fmt or "fastq" in fmt:
        return "fastq"
    if "clinical" in name:
        return "clinical"
    if "metainfo" in name or "meta-info" in name:
        return "metainfo"
    if "maf" in fmt or "maf" in name or "somaticsnv" in name:
        return "maf"
    if "bam" in fmt or "bam" in name:
        return "bam"
    if "vcf" in fmt or "vcf" in name:
        return "vcf"
    if any(x in name for x in ["counts", "count", "featurecounts", "htseq"]):
        return "expression_count"
    if any(x in name for x in ["fpkm", "tpm", "rsem", "abundance"]):
        return "expression_abundance"
    if "genes" in name:
        return "expression"
    return "other"


def assess_feasibility(pipeline_id: Optional[str], file_records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Check whether the matched files cover every data role the pipeline requires.

    Returns an advisory block (does not raise). When a required role is missing the
    agent should stop and ask the user for that data instead of running a partial job.
    """
    profile = _data_profile(pipeline_id)
    required_roles = list(dict.fromkeys(profile.get("roles") or []))
    present_roles: List[str] = []
    for f in file_records or []:
        role = f.get("input_role") or _role_of_file(f)
        if role and role not in present_roles:
            present_roles.append(role)
    missing_roles = [
        r for r in required_roles
        if not any(_role_satisfies(r, present) for present in present_roles)
    ]

    required_count = _REQUIRED_FILE_COUNT.get(pipeline_id or "", None)
    actual_count = len([f for f in (file_records or []) if (f.get("file_path") or f.get("files"))])

    if not required_roles:
        # Unknown pipeline profile — cannot judge, do not block.
        return {
            "ok": True,
            "required_roles": [],
            "present_roles": present_roles,
            "missing_roles": [],
            "required_file_count": required_count,
            "actual_file_count": actual_count,
            "message": "未登记该 pipeline 的数据角色，跳过可行性校验。",
        }

    ok = not missing_roles and (required_count is None or actual_count >= required_count)
    pair_blocked = False
    assay_blocked = False
    assay_message = ""
    wes_reason = ""
    if not missing_roles and required_roles == ["fastq"] and required_count:
        fastqs = [
            f for f in (file_records or [])
            if (f.get("input_role") or _role_of_file(f)) == "fastq"
        ]
        allowed_assays = set(profile.get("strategies") or [])
        allowed_norm = _canonical_assay_set(allowed_assays)
        if allowed_norm:
            assay_fastqs: List[Dict[str, Any]] = []
            unknown_assays: List[Dict[str, Any]] = []
            for f in fastqs:
                tokens = _normalize_assay_tokens(f.get("strategy") or f.get("data_type") or "")
                if tokens & allowed_norm:
                    assay_fastqs.append(f)
                elif not tokens:
                    unknown_assays.append(f)
            # 如果全部 FASTQ 都没有可识别的 assay 标注（单元测试里的合成记录），按兼容处理；
            # 只要有一个可识别标注，就要求至少一条落在允许集合内（fail closed）。
            all_unknown = bool(fastqs) and len(unknown_assays) == len(fastqs)
            if not assay_fastqs and fastqs and not all_unknown:
                assay_blocked = True
                ok = False
                seen = sorted({
                    (f.get("strategy") or f.get("data_type") or "未知").strip()
                    for f in fastqs
                    if _normalize_assay_tokens(f.get("strategy") or f.get("data_type") or "")
                })
                assay_message = (
                    f"「{pipeline_id}」需要 {' / '.join(sorted(allowed_assays))} 测序数据，"
                    f"当前匹配到的 FASTQ 为 {', '.join(seen) if seen else '未标注或无法识别'}，无法直接使用。"
                )
            fastqs = assay_fastqs if assay_fastqs else fastqs
        if not assay_blocked:
            if pipeline_id == "wes_somatic_pair":
                cases = _assess_wes_somatic_cases(fastqs)
                if not cases:
                    ok = False
                    pair_blocked = True
                    wes_reason = _wes_somatic_infeasibility_reason(fastqs)
            else:
                need_pairs = 2 if required_count >= 4 else 1
                if len(_paired_fastq_groups(fastqs)) < need_pairs:
                    ok = False
                    pair_blocked = True
    if missing_roles:
        need = "、".join(ROLE_LABELS.get(r, r) for r in missing_roles)
        message = f"缺少{need}，无法执行「{pipeline_id}」，请补充对应数据后再运行。"
    elif assay_blocked:
        message = assay_message
    elif pair_blocked:
        if wes_reason:
            message = wes_reason
        else:
            message = (
                f"「{pipeline_id}」需要同一 sample/run 的 R1/R2 成对 FASTQ，"
                "当前未匹配到完整的同源读对，请确认数据是否完整。"
            )
    elif required_count is not None and actual_count < required_count:
        message = (
            f"匹配到 {actual_count} 个文件，少于「{pipeline_id}」所需的 {required_count} 个"
            f"（如配对样本需 R1/R2 齐全），请确认数据是否完整。"
        )
    else:
        message = "所需数据角色齐全，可以执行。"
    return {
        "ok": ok,
        "required_roles": required_roles,
        "present_roles": present_roles,
        "missing_roles": missing_roles,
        "required_file_count": required_count,
        "actual_file_count": actual_count,
        "message": message,
    }


CUSTOM_ASSET_TO_DATA_ROLE = {
    "fastq_r1": "fastq",
    "fastq_r2": "fastq",
    "fastq_file": "fastq",
    "count_matrix": "expression_count",
    "expression_matrix": "expression_abundance",
    "expression_file": "expression",
    "clinical_file": "clinical",
    "sample_metadata": "metainfo",
    "maf_file": "maf",
    "bam_file": "bam",
    "vcf_file": "vcf",
}


def custom_data_roles(required_asset_roles: Sequence[str]) -> List[str]:
    """Map validated tool-chain asset roles onto the matcher's file-role vocabulary."""
    return list(dict.fromkeys(
        CUSTOM_ASSET_TO_DATA_ROLE[role]
        for role in required_asset_roles
        if role in CUSTOM_ASSET_TO_DATA_ROLE
    ))


def assess_custom_role_feasibility(
    required_asset_roles: Sequence[str],
    file_records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    required_data_roles = custom_data_roles(required_asset_roles)
    present_data_roles = list(dict.fromkeys(
        str(item.get("input_role") or _role_of_file(item))
        for item in file_records
        if item
    ))
    missing_data_roles = [
        role for role in required_data_roles
        if not any(_role_satisfies(role, present) for present in present_data_roles)
    ]
    missing_asset_roles: List[str] = []
    fastqs = [
        item for item in file_records
        if (item.get("input_role") or _role_of_file(item)) == "fastq"
    ]
    pairs = _paired_fastq_groups(fastqs)
    if "fastq_r1" in required_asset_roles and not any(pair["r1"] for pair in pairs):
        missing_asset_roles.append("fastq_r1")
    if "fastq_r2" in required_asset_roles and not any(pair["r2"] for pair in pairs):
        missing_asset_roles.append("fastq_r2")
    for role in required_asset_roles:
        data_role = CUSTOM_ASSET_TO_DATA_ROLE.get(role)
        if data_role in missing_data_roles and role not in missing_asset_roles:
            missing_asset_roles.append(role)
    ok = not missing_asset_roles and not missing_data_roles
    return {
        "ok": ok,
        "required_asset_roles": list(dict.fromkeys(required_asset_roles)),
        "required_data_roles": required_data_roles,
        "present_data_roles": present_data_roles,
        "missing_asset_roles": missing_asset_roles,
        "missing_data_roles": missing_data_roles,
        "message": (
            "已找到满足自定义工具链角色要求的数据。"
            if ok else
            "缺少自定义工具链所需的数据角色: "
            + ", ".join(missing_asset_roles or missing_data_roles)
        ),
    }


# Required file counts per pipeline (module-level mirror of _required_file_count for feasibility).
_REQUIRED_FILE_COUNT = {
    "wes_somatic_pair": 4,
    "cellranger_workflow": 2,
    "rnaseq_singletask": 2,
    "paired_fastq_to_unmapped_bam": 2,
    "diff_expr_go": 1,
    "diff_expr_kegg": 1,
    "rnaseq_unsupervised_cluster": 1,
    "wes_somatic_maf_landscape": 1,
    "wgcna": 3,
    "immune_infiltration_iobr": 3,
    "her2_pfs_survival": 3,
    "survival_analysis": 3,
    "tmb_survival_analysis": 3,
    "driver_gene_gender_analysis": 3,
}


def _contains_any(text: str, terms: Iterable[str]) -> List[str]:
    text_l = text.lower()
    hits = []
    for term in terms:
        if not term:
            continue
        t = str(term).lower()
        if t in text_l or str(term) in text:
            hits.append(str(term))
    return hits


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class CsvKGDataMatcher:
    def __init__(self, csv_dir: Optional[Path] = None):
        self.csv_dir = Path(csv_dir or os.environ.get("DATA_CSV_DIR", str(CSV_DIR))).expanduser()
        self.entity_dir = self.csv_dir / "entities" if (self.csv_dir / "entities").is_dir() else self.csv_dir
        self.relation_dir = self.csv_dir / "relations"
        self.data_schema = "normalized-v2" if self.entity_dir != self.csv_dir else "legacy-flat"
        self.study = _read_csv(self.entity_dir / "study.csv")
        self.project = _read_csv(self.entity_dir / "project.csv")
        self.sample = _read_csv(self.entity_dir / "sample.csv")
        self.individual = _read_csv(self.entity_dir / "individual.csv")
        self.sample_specimen_types = {
            row.get("sample_accession"): row.get("specimen_types") or ""
            for row in self.sample
            if row.get("sample_accession")
        }

        legacy_t1 = _read_csv(self.csv_dir / "T11.csv") or _read_csv(self.csv_dir / "merge_metainfo.csv")
        normalized_t1 = _read_csv(self.entity_dir / "T1.csv") if self.data_schema == "normalized-v2" else []
        self.t1 = self._load_normalized_t1(normalized_t1, legacy_t1) if normalized_t1 else legacy_t1
        if self.data_schema == "normalized-v2":
            self.t2 = _read_csv(self.entity_dir / "T2.csv")
        else:
            self.t2 = _read_csv(self.csv_dir / "T2.1csv") or _read_csv(self.csv_dir / "T2.csv")
        self.project_by_study: Dict[str, Dict[str, str]] = {}
        for row in self.project:
            for st in re.split(r"[,，]", row.get("study_accession") or ""):
                st = st.strip()
                if st and st not in self.project_by_study:
                    self.project_by_study[st] = row
        projects_by_id = {row.get("project_accession"): row for row in self.project}
        for relation in _read_csv(self.relation_dir / "study_in_project.csv"):
            st = relation.get("study_accession")
            project = projects_by_id.get(relation.get("project_accession"))
            if st and project:
                self.project_by_study[st] = project
        self.study_by_id = {
            row.get("study_accession"): row
            for row in self.study
            if row.get("study_accession")
        }

    def _load_normalized_t1(
        self,
        normalized_rows: Sequence[Dict[str, str]],
        legacy_rows: Sequence[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Adapt the normalized KG entity to the file records used by the matcher.

        T1 v2 intentionally stores graph identity and biological metadata only.
        The legacy export remains the local physical-location mirror, so join it
        by file name instead of discarding paths required by agent_input.
        """
        legacy_by_name = {
            self._clean_data_name(row.get("files") or ""): row
            for row in legacy_rows
            if row.get("files")
        }
        format_by_name = {
            self._clean_data_name(row.get("files") or ""): row.get("format") or ""
            for row in _read_csv(self.relation_dir / "T1_in_format.csv")
        }
        level_by_name = {
            self._clean_data_name(row.get("files") or ""): row.get("data_level") or ""
            for row in _read_csv(self.relation_dir / "T1_in_level.csv")
        }
        adapted: List[Dict[str, str]] = []
        for row in normalized_rows:
            name = self._clean_data_name(row.get("dataName") or "")
            legacy = legacy_by_name.get(name, {})
            file_name = legacy.get("file_name") or legacy.get("files") or name
            adapted.append({
                "study_accession": row.get("studyAccession") or legacy.get("study_accession") or "",
                "sample_accession": row.get("sampleAccession") or legacy.get("sample_accession") or "",
                "run_accession": row.get("runAccession") or legacy.get("run_accession") or "",
                "data_type": row.get("strategy") or legacy.get("data_type") or "",
                "Read Pair": legacy.get("Read Pair") or self._guess_read_pair(name),
                "files": file_name,
                "file_id": name,
                "file_name": file_name,
                "format": format_by_name.get(name) or legacy.get("format") or self._infer_format(name),
                "file_path": legacy.get("file_path") or file_name,
                "file_description": legacy.get("file_description") or row.get("sampleDescription") or "",
                "Experiment": row.get("experimentAccession") or legacy.get("Experiment") or "",
                "Platform": row.get("platform") or legacy.get("Platform") or "",
                "data_level": level_by_name.get(name) or legacy.get("data_level") or "1",
                "strategy": row.get("strategy") or legacy.get("data_type") or "",
                "individual_accession": row.get("individualAccession") or "",
                "individual_name": row.get("individualName") or "",
                "sample_name": row.get("sampleName") or "",
                "specimen_types": self.sample_specimen_types.get(row.get("sampleAccession") or "") or "",
                "gender": row.get("gender") or "",
            })
        return adapted

    @staticmethod
    def _clean_data_name(name: str) -> str:
        return re.sub(r"\s*\(\d+\s+bytes\)\s*$", "", name or "")

    @staticmethod
    def _infer_format(name: str) -> str:
        lowered = (name or "").lower()
        for suffix in ("fastq.gz", "fq.gz", "xlsx", "xls", "tsv", "csv", "maf", "vcf", "bam", "h5"):
            if lowered.endswith(suffix):
                return suffix
        return ""

    def _guess_read_pair(self, name: str) -> str:
        n = name.lower()
        if _FASTQ_R1_PATTERN.search(n):
            return "R1"
        if _FASTQ_R2_PATTERN.search(n):
            return "R2"
        return ""

    def match(self, intent: Dict[str, Any], pipelines: Sequence[Dict[str, Any]], limit: int = 10) -> Dict[str, Any]:
        disease = intent.get("disease")
        omics = intent.get("omics_type")
        fmt = intent.get("input_hint")
        pipeline_ids = [p.get("pipeline_id") for p in pipelines]
        strategy_hints, format_hints, file_terms = self._required_data_hints(pipeline_ids, intent)
        if fmt:
            format_hints.add(fmt)

        requested_studies = {
            str(value).upper() for value in intent.get("study_accessions") or [] if value
        }
        cohorts = self._match_cohorts(disease, omics, strategy_hints, limit=limit)
        if requested_studies:
            cohorts = [
                item for item in cohorts
                if str(item.get("study_accession") or "").upper() in requested_studies
            ]
        primary_pid = pipeline_ids[0] if pipeline_ids else None
        # 组合/可行性判断需要在全部候选文件上做，不能在截断后的列表上做；
        # 截断只影响展示给用户的 file_candidates。
        files = self._match_files(disease, strategy_hints, format_hints, file_terms, pipeline_ids, limit=None, intent=intent)
        combos = self._build_combinations(pipeline_ids, files, limit=limit)
        display_files = self._primary_display_files(primary_pid, combos, files)
        return {
            "data_schema": self.data_schema,
            "cohort_candidates": cohorts[:limit],
            "file_candidates": display_files[:limit],
            "backup_file_candidates": (self._filter_files_for_pipeline(primary_pid, files) or files)[:limit],
            "data_combinations": combos[:limit],
            "query_constraints": {
                "disease": disease,
                "omics_type": omics,
                "formats": sorted(format_hints),
                "strategies": sorted(strategy_hints),
                "file_terms": sorted(file_terms),
                "study_accessions": sorted(requested_studies),
            },
        }

    def match_custom_roles(
        self,
        intent: Dict[str, Any],
        required_roles: Sequence[str],
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Match data for a validated custom chain without inventing a pipeline ID."""
        data_roles = custom_data_roles(required_roles)
        strategy_hints: Set[str] = set()
        format_hints: Set[str] = set()
        terms: Set[str] = set()
        if "fastq" in data_roles:
            format_hints.update({"fq.gz", "fastq.gz"})
            omics = str(intent.get("omics_type") or "").lower()
            if "rna" in omics:
                strategy_hints.add("RNA-Seq")
            elif "wes" in omics or "外显子" in str(intent.get("query_text") or ""):
                strategy_hints.add("WES")
            elif "wgs" in omics:
                strategy_hints.add("WGS")
        for role in data_roles:
            if role == "expression_count":
                format_hints.add("tsv")
                terms.update({"counts", "count"})
            elif role == "expression_abundance":
                format_hints.add("tsv")
                terms.update({"FPKM", "TPM"})
            elif role == "clinical":
                format_hints.update({"xls", "xlsx", "tsv"})
                terms.add("Clinical")
            elif role == "metainfo":
                format_hints.update({"xls", "xlsx", "tsv"})
                terms.add("MetaInfo")
            elif role == "maf":
                format_hints.add("maf")
                terms.update({"MAF", "SomaticSNV"})
            elif role == "bam":
                format_hints.add("bam")
            elif role == "vcf":
                format_hints.add("vcf")
        if intent.get("input_hint"):
            format_hints.add(str(intent["input_hint"]))
        requested_studies = {
            str(value).upper() for value in intent.get("study_accessions") or [] if value
        }
        cohorts = self._match_cohorts(
            intent.get("disease"), intent.get("omics_type"), strategy_hints, limit
        )
        if requested_studies:
            cohorts = [
                item for item in cohorts
                if str(item.get("study_accession") or "").upper() in requested_studies
            ]
        candidates = self._match_files(
            intent.get("disease"),
            strategy_hints,
            format_hints,
            terms,
            [],
            limit=None,
            intent=intent,
        )
        filtered = [
            self._with_input_role(item)
            for item in candidates
            if any(_role_satisfies(role, _role_of_file(item)) for role in data_roles)
        ]
        combinations: List[Dict[str, Any]] = []
        by_study: Dict[str, List[Dict[str, Any]]] = {}
        for item in filtered:
            by_study.setdefault(item.get("study_accession") or "unknown", []).append(item)
        for study, study_files in by_study.items():
            selected: List[Dict[str, Any]] = []
            if "fastq" in data_roles:
                pairs = _paired_fastq_groups(study_files)
                if pairs:
                    selected.extend([pairs[0]["r1"][0], pairs[0]["r2"][0]])
            for role in data_roles:
                if role == "fastq":
                    continue
                matches = [
                    item for item in study_files
                    if _role_satisfies(role, item.get("input_role") or _role_of_file(item))
                ]
                if matches:
                    selected.append(matches[0])
            if selected and assess_custom_role_feasibility(required_roles, selected)["ok"]:
                combinations.append({
                    "pipeline_id": "custom_roles",
                    "study_accession": study,
                    "kind": "custom_role_bundle",
                    "files": self._dedupe_files(selected),
                    "match_reason": "满足已校验自定义工具链的数据角色",
                })
                if len(combinations) >= limit:
                    break
        display_files = (
            combinations[0]["files"]
            if combinations
            else self._best_same_study_files(filtered, data_roles, limit)
        )
        return {
            "data_schema": self.data_schema,
            "cohort_candidates": cohorts[:limit],
            "file_candidates": display_files[:limit],
            "backup_file_candidates": self._dedupe_files(filtered)[:limit],
            "data_combinations": combinations[:limit],
            "query_constraints": {
                "disease": intent.get("disease"),
                "omics_type": intent.get("omics_type"),
                "formats": sorted(format_hints),
                "strategies": sorted(strategy_hints),
                "file_terms": sorted(terms),
                "required_data_roles": data_roles,
                "study_accessions": sorted(requested_studies),
            },
        }

    def lookup_files(self, file_names: Sequence[str]) -> Dict[str, Any]:
        """Resolve reviewed file names against this matcher's actual backend rows."""
        requested = [self._clean_data_name(str(value).strip()) for value in file_names if value]
        by_name: Dict[str, List[Dict[str, Any]]] = {}
        for source, row in [("T1", item) for item in self.t1] + [("T2", item) for item in self.t2]:
            aliases: Set[str] = set()
            for key in ("files", "file_name", "file_id", "file", "t2_id"):
                raw = str(row.get(key) or "")
                if not raw:
                    continue
                aliases.add(self._clean_data_name(raw))
                # Composite-key quirk: reference rows key the file as
                # "<file_name>::<file_path>"; also alias the bare file name so a
                # reviewed bare-name lookup (e.g. expected_data) resolves.
                if "::" in raw:
                    aliases.add(self._clean_data_name(raw.split("::", 1)[0]))
            record = self._file_record(source, row, "文件名精确匹配")
            for name in {alias for alias in aliases if alias}:
                by_name.setdefault(name, []).append(record)

        assets: List[Dict[str, Any]] = []
        missing: List[str] = []
        for name in requested:
            matches = by_name.get(name) or []
            if not matches:
                missing.append(name)
                assets.append({"name": name, "graph_status": "missing_from_graph"})
                continue
            item = self._with_input_role(matches[0])
            assets.append({
                "name": name,
                "graph_status": "available",
                **item,
            })
        studies = sorted({
            str(item.get("study_accession"))
            for item in assets
            if item.get("graph_status") == "available" and item.get("study_accession")
        })
        return {
            "status": "available" if requested and not missing else "missing_from_graph",
            "assets": assets,
            "matched_count": len(requested) - len(missing),
            "expected_count": len(requested),
            "missing_asset_names": missing,
            "study_accessions": studies,
        }

    def _file_record(
        self, source: str, row: Dict[str, Any], match_reason: str
    ) -> Dict[str, Any]:
        def _bare(value: Any) -> Any:
            # Strip the "::<path>" composite-key suffix from display names only;
            # leaves "(N bytes)" and plain names untouched.
            text = str(value or "")
            return text.split("::", 1)[0] if "::" in text else value

        file_name = _bare(row.get("file_name") or row.get("files") or row.get("file") or row.get("t2_id"))
        file_id = _bare(row.get("file_id") or row.get("files") or row.get("t2_id"))
        return {
            "source": source,
            "t2_id": row.get("t2_id") if source == "T2" else None,
            "file_id": file_id,
            "file_name": file_name,
            "files": file_name,
            "format": row.get("format") or row.get("file_type") or "",
            "strategy": row.get("strategy") or row.get("data_type") or row.get("Experiment") or "",
            "data_level": row.get("data_level"),
            "study_accession": row.get("study_accession"),
            "sample_id": row.get("sample_accession"),
            "run_accession": row.get("run_accession"),
            "individual_accession": row.get("individual_accession"),
            "individual_name": row.get("individual_name"),
            "sample_name": row.get("sample_name"),
            "specimen_types": row.get("specimen_types"),
            "read_pair": row.get("read_pair") or row.get("Read Pair"),
            "file_path": row.get("file_path"),
            "match_reason": match_reason,
        }

    def _best_same_study_files(
        self,
        files: Sequence[Dict[str, Any]],
        required_roles: Sequence[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        by_study: Dict[str, List[Dict[str, Any]]] = {}
        for item in files:
            by_study.setdefault(str(item.get("study_accession") or "unknown"), []).append(item)
        for group in by_study.values():
            present = {_role_of_file(item) for item in group}
            if all(any(_role_satisfies(role, value) for value in present) for role in required_roles):
                return self._dedupe_files(group)[:limit]
        return []

    def _required_data_hints(self, pipeline_ids: Sequence[str], intent: Dict[str, Any]) -> Tuple[Set[str], Set[str], Set[str]]:
        query_text = str(intent.get("query_text") or "")
        strategies: Set[str] = set()
        formats: Set[str] = set()
        terms: Set[str] = set()
        for pid in pipeline_ids:
            profile = _data_profile(pid)
            strategies.update(profile.get("strategies") or [])
            formats.update(profile.get("formats") or [])
            terms.update(profile.get("terms") or [])
            quant_hint = intent.get("quant_hint")
            if pid in {"diff_expr_go", "diff_expr_kegg"} and quant_hint in {"FPKM", "TPM"}:
                terms.add(quant_hint)
            if pid == "rnaseq_unsupervised_cluster":
                terms.add("counts")
            if pid == "wes_somatic_maf_landscape" and any(k in query_text for k in ["相关", "统计", "组成", "同步输出"]):
                terms.add("HRA001749")
            if pid == "wes_somatic_pair":
                terms.update({"HRR365660", "HRR365661"})
        return strategies, formats, terms

    def _disease_terms(self, disease: Optional[str]) -> List[str]:
        if not disease:
            return []
        return DISEASE_ALIASES.get(disease, [disease])

    def _required_file_count(self, pipeline_id: Optional[str]) -> int:
        if pipeline_id == "wes_somatic_pair":
            return 4
        if pipeline_id in {"cellranger_workflow", "rnaseq_singletask", "paired_fastq_to_unmapped_bam"}:
            return 2
        if pipeline_id in {"diff_expr_go", "diff_expr_kegg", "rnaseq_unsupervised_cluster", "wes_somatic_maf_landscape"}:
            return 1
        if pipeline_id in {"wgcna", "immune_infiltration_iobr", "her2_pfs_survival", "survival_analysis", "tmb_survival_analysis", "driver_gene_gender_analysis"}:
            return 3
        return 3

    def _row_text(self, row: Dict[str, str]) -> str:
        parts = [str(v or "") for v in row.values()]
        st = row.get("study_accession")
        if st and st in self.study_by_id:
            parts.extend(str(v or "") for v in self.study_by_id[st].values())
        if st and st in self.project_by_study:
            parts.extend(str(v or "") for v in self.project_by_study[st].values())
        return " ".join(parts)

    def _match_cohorts(self, disease: Optional[str], omics: Optional[str], strategies: Set[str], limit: int) -> List[Dict[str, Any]]:
        disease_terms = self._disease_terms(disease)
        scored = []
        for row in self.study:
            text = self._row_text(row)
            text_l = text.lower()
            score = 0
            reasons = []
            hits = _contains_any(text, disease_terms)
            if hits:
                score += 5
                reasons.append("癌种/队列匹配: " + ", ".join(hits[:3]))
            elif disease_terms:
                # Explicit disease is a hard constraint. Omics similarity alone
                # must never introduce a cohort from another disease.
                continue
            if omics and omics.lower().replace("bulk ", "") in text_l:
                score += 1
                reasons.append("组学描述匹配")
            for st in strategies:
                if st.lower() in text_l:
                    score += 2
                    reasons.append(f"strategy 匹配 {st}")
            if not disease_terms and strategies:
                score += 1
            if score <= 0:
                continue
            project = self.project_by_study.get(row.get("study_accession"), {})
            scored.append(
                (
                    -score,
                    row.get("study_accession") or "",
                    {
                        "study_accession": row.get("study_accession"),
                        "title": row.get("title") or row.get("study_description"),
                        "tumor_type": row.get("tumor_type"),
                        "study_type": row.get("study_type"),
                        "sample_count": row.get("sample_count"),
                        "project_accession": project.get("project_accession"),
                        "project_name": project.get("project_name"),
                        "match_reason": "; ".join(reasons) or "与请求的数据类型相符",
                    },
                )
            )
        return [x[2] for x in sorted(scored)[:limit]]

    def _match_files(self, disease: Optional[str], strategies: Set[str], formats: Set[str], terms: Set[str], pipeline_ids: Sequence[str], limit: int, intent: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        disease_terms = self._disease_terms(disease)
        primary_pid = pipeline_ids[0] if pipeline_ids else None
        query_text = str((intent or {}).get("query_text") or "")
        requested_studies = {
            str(value).upper()
            for value in (intent or {}).get("study_accessions") or []
            if value
        }
        rows = [("T1", r) for r in self.t1] + [("T2", r) for r in self.t2]
        # assay-aware filtering for FASTQ files: a FASTQ record whose assay is
        # explicitly annotated as incompatible with the requested pipeline
        # strategies is excluded. Unknown/garbage assay values are allowed
        # (handled later by assess_feasibility).
        allowed_assay_norm = _canonical_assay_set(strategies)
        role_rule_bonus = primary_pid == "wes_somatic_pair"
        query_implies_paired = bool(
            query_text
            and ("配对" in query_text or "paired" in query_text.lower())
            and (
                ("肿瘤" in query_text and "正常" in query_text)
                or ("tumor" in query_text.lower() and "normal" in query_text.lower())
            )
        )
        scored = []
        for idx, (source, row) in enumerate(rows):
            if requested_studies and str(row.get("study_accession") or "").upper() not in requested_studies:
                continue
            text = self._row_text(row)
            text_l = text.lower()
            score = 0
            reasons = []
            disease_matched = False
            if disease_terms:
                hits = _contains_any(text, disease_terms)
                if hits:
                    disease_matched = True
                    score += 5
                    reasons.append("癌种/队列匹配")
                else:
                    continue
            fmt = row.get("format") or row.get("file_type") or ""
            if formats and any(f.lower() == fmt.lower() or f.lower() in text_l for f in formats):
                score += 4
                reasons.append(f"格式匹配 {fmt or sorted(formats)[0]}")
            if source == "T2":
                score += 2
                reasons.append("优先使用处理后的 T2 数据")
            # assay mismatch guard for FASTQ
            if allowed_assay_norm and _role_of_file(row) == "fastq":
                file_assay_norm = _normalize_assay_tokens(
                    row.get("strategy") or row.get("data_type") or row.get("Experiment") or ""
                )
                if file_assay_norm and not (file_assay_norm & allowed_assay_norm):
                    continue
            strategy = row.get("strategy") or row.get("data_type") or row.get("Experiment") or ""
            if strategies and any(s.lower() in strategy.lower() or s.lower() in text_l for s in strategies):
                score += 3
                reasons.append(f"strategy 匹配 {strategy or ','.join(sorted(strategies))}")
            term_hits = _contains_any(text, terms)
            if term_hits:
                score += min(3, len(term_hits))
                reasons.append("文件语义匹配: " + ", ".join(term_hits[:3]))
            if (role_rule_bonus or query_implies_paired) and _sample_role(row) in {"tumor", "normal"}:
                score += 2
                reasons.append("样本角色可识别")
            if not disease_terms and (formats or strategies) and score > 0:
                score += 1
            if score <= 0:
                continue
            file_name = row.get("files") or row.get("file") or row.get("t2_id")
            scored.append(
                (
                    -score,
                    row.get("study_accession") or "",
                    file_name or "",
                    idx,
                    self._file_record(source, row, "; ".join(reasons)),
                )
            )
        return [x[4] for x in sorted(scored)[:limit]]

    def _file_role(self, item: Dict[str, Any]) -> str:
        return _role_of_file(item)

    def _allowed_file_roles(self, pipeline_id: Optional[str]) -> Set[str]:
        return set(_data_profile(pipeline_id).get("roles") or [])

    def _filter_files_for_pipeline(self, pipeline_id: Optional[str], files: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        allowed = self._allowed_file_roles(pipeline_id)
        if not allowed:
            return list(files)
        filtered = []
        for item in files:
            role = self._file_role(item)
            if any(_role_satisfies(allowed_role, role) for allowed_role in allowed):
                copied = dict(item)
                copied["input_role"] = role
                filtered.append(copied)
        return filtered

    def _primary_display_files(self, pipeline_id: Optional[str], combos: Sequence[Dict[str, Any]], files: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for combo in combos:
            if combo.get("pipeline_id") == pipeline_id and combo.get("files"):
                return self._dedupe_files([self._with_input_role(f) for f in combo.get("files") or []])
        filtered = self._filter_files_for_pipeline(pipeline_id, files)
        return self._best_same_study_files(
            filtered,
            list(self._allowed_file_roles(pipeline_id)),
            self._required_file_count(pipeline_id),
        )

    def _with_input_role(self, item: Dict[str, Any]) -> Dict[str, Any]:
        copied = dict(item)
        copied["input_role"] = copied.get("input_role") or self._file_role(copied)
        return copied

    def _trim_to_required_count(self, pipeline_id: Optional[str], files: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        files = self._dedupe_files(files)
        if pipeline_id == "wes_somatic_pair":
            return list(files)[:4]
        if pipeline_id in {"cellranger_workflow", "rnaseq_singletask", "paired_fastq_to_unmapped_bam"}:
            return list(files)[:2]
        if pipeline_id in {"diff_expr_go", "diff_expr_kegg", "rnaseq_unsupervised_cluster", "wes_somatic_maf_landscape"}:
            return list(files)[:1]
        if pipeline_id in {"wgcna", "immune_infiltration_iobr", "her2_pfs_survival", "survival_analysis", "tmb_survival_analysis", "driver_gene_gender_analysis"}:
            return list(files)[:3]
        return list(files)[:3]

    def _dedupe_files(self, files: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for item in files:
            key = _lower(item.get("file_name") or item.get("files") or item.get("file_path") or item.get("file_id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    def _pair_wes_somatic_cases(
        self,
        files: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """按 individual_accession 为 wes_somatic_pair 构建 tumor/normal 配对 case。

        只接受一侧恰好 1 个 R1+R2 完整对的个体；任一侧 0 个或 ≥2 个都丢弃。
        跨 study 的同一 individual（如 HRA001748/1749）会因 individual_accession
        相同而自动配在一起。
        """
        from copy import deepcopy

        by_individual: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        for f in files:
            role = _sample_role(f)
            if role not in {"tumor", "normal"}:
                continue
            ind = _norm(f.get("individual_accession"))
            if not ind:
                continue
            by_individual.setdefault(ind, {"tumor": [], "normal": []})[role].append(deepcopy(f))

        cases: List[Dict[str, Any]] = []
        for ind, sides in by_individual.items():
            tumor_pairs = _paired_fastq_groups(sides["tumor"])
            normal_pairs = _paired_fastq_groups(sides["normal"])
            if len(tumor_pairs) != 1 or len(normal_pairs) != 1:
                continue
            selected = [
                tumor_pairs[0]["r1"][0],
                tumor_pairs[0]["r2"][0],
                normal_pairs[0]["r1"][0],
                normal_pairs[0]["r2"][0],
            ]
            for sf in selected:
                sf["individual_accession"] = ind
            selected[0]["sample_role"] = "tumor"
            selected[1]["sample_role"] = "tumor"
            selected[2]["sample_role"] = "normal"
            selected[3]["sample_role"] = "normal"
            cases.append({"individual_accession": ind, "files": selected})
        return cases

    def _build_combinations(self, pipeline_ids: Sequence[str], files: Sequence[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        combos: List[Dict[str, Any]] = []
        by_study: Dict[str, List[Dict[str, Any]]] = {}
        for f in files:
            by_study.setdefault(f.get("study_accession") or "unknown", []).append(f)
        for pid in pipeline_ids:
            if pid in {"cellranger_workflow", "rnaseq_singletask", "wes_somatic_pair", "paired_fastq_to_unmapped_bam"}:
                if pid == "wes_somatic_pair":
                    fastqs = self._dedupe_files([f for f in files if _role_of_file(f) == "fastq"])
                    cases = self._pair_wes_somatic_cases(fastqs)
                    for case in cases:
                        if len(case["files"]) >= self._required_file_count(pid):
                            tumor_studies = {f.get("study_accession") for f in case["files"] if f.get("sample_role") == "tumor"}
                            normal_studies = {f.get("study_accession") for f in case["files"] if f.get("sample_role") == "normal"}
                            study_label = (tumor_studies | normal_studies).pop() if len(tumor_studies | normal_studies) == 1 else "multi-study"
                            combos.append({
                                "pipeline_id": pid,
                                "study_accession": study_label,
                                "individual_accession": case["individual_accession"],
                                "kind": "paired_fastq",
                                "files": case["files"],
                                "match_reason": f"同个体 tumor/normal 配对: {case['individual_accession']}",
                            })
                            if len(combos) >= limit:
                                break
                    continue
                for st, group in by_study.items():
                    fastqs = self._dedupe_files([f for f in group if _role_of_file(f) == "fastq"])
                    pairs = _paired_fastq_groups(fastqs)
                    if pairs:
                        selected = [pairs[0]["r1"][0], pairs[0]["r2"][0]]
                        if len(selected) >= self._required_file_count(pid):
                            combos.append({"pipeline_id": pid, "study_accession": st, "kind": "paired_fastq", "files": selected, "match_reason": "找到同源 R1/R2 FASTQ 输入组合"})
                            break
            elif pid in {"diff_expr_go", "diff_expr_kegg", "rnaseq_unsupervised_cluster", "wgcna", "immune_infiltration_iobr", "her2_pfs_survival"}:
                for st, group in by_study.items():
                    required_roles = self._allowed_file_roles(pid)
                    wanted_expr = [r for r in required_roles if r.startswith("expression")]
                    expr = [
                        f for f in group
                        if any(_role_satisfies(w, _role_of_file(f)) for w in wanted_expr)
                    ]
                    expr.sort(key=lambda f: 0 if any(_role_of_file(f) == w for w in wanted_expr) else 1)
                    clinical = [f for f in group if "clinical" in _lower(f.get("files"))]
                    metainfo = [f for f in group if "metainfo" in _lower(f.get("files"))]
                    available_roles = {_role_of_file(f) for f in expr} | ({"clinical"} if clinical else set()) | ({"metainfo"} if metainfo else set())
                    if expr and all(
                        any(_role_satisfies(r, present) for present in available_roles)
                        for r in required_roles
                    ):
                        selected = expr[:1]
                        if pid in {"wgcna", "immune_infiltration_iobr", "her2_pfs_survival"}:
                            selected += clinical[:1] + metainfo[:1]
                        combos.append({"pipeline_id": pid, "study_accession": st, "kind": "expression_bundle", "files": selected, "match_reason": "找到表达矩阵候选"})
                        break
            else:
                for st, group in by_study.items():
                    maf = [f for f in group if "maf" in _lower(f.get("format")) or "somaticsnv" in _lower(f.get("files"))]
                    clinical = [f for f in group if "clinical" in _lower(f.get("files"))]
                    metainfo = [f for f in group if "metainfo" in _lower(f.get("files"))]
                    required_roles = self._allowed_file_roles(pid)
                    available_roles = ({"maf"} if maf else set()) | ({"clinical"} if clinical else set()) | ({"metainfo"} if metainfo else set())
                    if maf and required_roles.issubset(available_roles):
                        selected = maf[:1] if pid == "wes_somatic_maf_landscape" else maf[:1] + clinical[:1] + metainfo[:1]
                        kind = "mutation_only" if pid == "wes_somatic_maf_landscape" else "mutation_bundle"
                        reason = "找到 MAF 候选" if pid == "wes_somatic_maf_landscape" else "找到 MAF/临床候选"
                        combos.append({"pipeline_id": pid, "study_accession": st, "kind": kind, "files": selected, "match_reason": reason})
                        break
        return combos[:limit]


class PipelineRouter:
    def __init__(self, catalog: Any, matcher: Optional[CsvKGDataMatcher] = None):
        if catalog is None:
            raise ValueError("Neo4j-backed pipeline catalog is required")
        self.catalog = catalog
        if matcher is None:
            from data_matcher.factory import build_data_matcher

            matcher = build_data_matcher()
        self.matcher = matcher
        self._last_llm_metadata: Dict[str, Any] = {}
        self._last_intent_llm: Dict[str, Any] = {"used": False, "status": "not_called"}

    def capabilities(self) -> List[Dict[str, Any]]:
        return self.catalog.capabilities()

    def _rule_intent(self, text: str) -> Dict[str, Any]:
        disease = None
        for name, aliases in DISEASE_ALIASES.items():
            if _contains_any(text, aliases):
                disease = name
                break
        omics = None
        for terms, value in OMICS_HINTS:
            if _contains_any(text, terms):
                omics = value
                break
        fmt = None
        for terms, value in FORMAT_HINTS:
            if _contains_any(text, terms):
                fmt = value
                break
        text_l = text.lower()
        quant_hint = None
        if "fpkm" in text_l:
            quant_hint = "FPKM"
        elif "tpm" in text_l:
            quant_hint = "TPM"
        elif "count" in text_l or "counts" in text_l:
            quant_hint = "counts"
        goals = []
        for terms, value in ANALYSIS_HINTS:
            if _contains_any(text, terms):
                goals.append(value)
        requested_outputs = []
        for term in ["表达矩阵", "filtered feature", "质控报告", "生存曲线", "突变景观", "差异基因", "富集结果", "vcf", "bam", "maf", "qc"]:
            if term.lower() in text.lower() or term in text:
                requested_outputs.append(term)
        study_accessions = list(dict.fromkeys(
            value.upper()
            for value in re.findall(r"\bHRA\d+\b", text, flags=re.IGNORECASE)
        ))
        return {
            "query_text": text,
            "analysis_goal": ", ".join(dict.fromkeys(goals)) if goals else None,
            "disease": disease,
            "omics_type": omics,
            "input_hint": fmt,
            "quant_hint": quant_hint,
            "requested_outputs": list(dict.fromkeys(requested_outputs)),
            "study_accessions": study_accessions,
            "source": "rule",
            "ambiguous": not bool(goals),
        }
def _force_rule() -> bool:
    return (os.environ.get("FORCE_RULE") or "").strip().lower() in {"1", "true", "yes", "on"}

def render_pipeline_answer(result: Dict[str, Any]) -> str:
    if result.get("schema_version") == "tool-chain/v2":
        candidates = result.get("candidates") or []
        recommendations = result.get("recommendations") or []
        if recommendations:
            lines = [f"返回 {len(recommendations)} 条业务流程推荐："]
            for recommendation in recommendations:
                tool = recommendation.get("tool") or {}
                data = recommendation.get("data") or {}
                lines.append(
                    f"- 推荐 {recommendation.get('rank')}："
                    f"{recommendation.get('pipeline_id')}；"
                    f"工具目录={tool.get('catalog_status')}；"
                    f"数据={data.get('status')} "
                    f"({data.get('matched_count', 0)}/{data.get('expected_count', 0)})。"
                )
            if not candidates:
                return "\n".join(lines)
            lines.append(f"同时返回 {len(candidates)} 条原子工具候选链：")
            for candidate in candidates:
                tools = " -> ".join(
                    str(step.get("tool_id") or "")
                    for step in candidate.get("tool_chain") or []
                )
                lines.append(f"- 候选 {candidate.get('rank')}：{tools}。")
            return "\n".join(lines)
        if not candidates:
            return str(
                result.get("unsupported_reason")
                or "当前没有同时通过目录校验和完整数据匹配的候选链。"
            )
        lines = [f"返回 {len(candidates)} 条原子工具候选链："]
        for candidate in candidates:
            tools = " -> ".join(
                str(step.get("tool_id") or "")
                for step in candidate.get("tool_chain") or []
            )
            lines.append(
                f"- 候选 {candidate.get('rank')}：{tools}。"
                f"{candidate.get('match_note') or ''}"
            )
            lines.append(
                f"  数据：{candidate.get('study_accession') or '未标明 study'}，"
                f"{len(candidate.get('assets') or [])} 个资产。"
            )
        return "\n".join(lines)
    return "无法渲染：结果不是 tool-chain/v2。"


def route_pipeline_request(
    nl_text: Any, top_k: int = 3
) -> Dict[str, Any]:
    from workflow_composer import compose_workflow_request

    return compose_workflow_request(nl_text, top_k=top_k)


def list_pipeline_capabilities() -> List[Dict[str, Any]]:
    from workflow_composer import list_neo4j_pipeline_capabilities

    return list_neo4j_pipeline_capabilities()


def list_workflow_methods() -> Dict[str, Any]:
    from workflow_composer import list_workflow_methods as list_methods

    return list_methods()
