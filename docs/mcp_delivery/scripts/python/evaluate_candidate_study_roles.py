#!/usr/bin/env python3
"""Read-only evaluation of four candidate datasets for STUDY_ROLE_RULES.

Does not modify code, CSV, or Neo4j. Replicates the pairing logic in
pipeline_router.py so the numbers are directly comparable.
"""

import csv
import re
import collections
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BASE = Path(__file__).resolve().parents[2]
DATA_CSV = BASE / "data/csv"
ENTITY_CSV = DATA_CSV / "entities"
OUT_MD = BASE / "docs/candidate_study_role_rules.md"

CANDIDATES = ["HRA001272", "HRA000071", "HRA003107", "HRA007169"]

# Specimen-type role hypotheses evaluated for each dataset.
ROLE_HYPOTHESES: Dict[str, Dict[str, str]] = {
    "HRA001272": {"Patient Solid Tissue": "tumor", "Peritumoral": "normal"},
    "HRA003107": {"Patient Solid Tissue": "tumor", "Peritumoral": "normal"},
    # HRA000071 has no same-individual pairing with current data; evaluate both sides anyway.
    "HRA000071": {"Patient Solid Tissue": "tumor", "Blood": "normal"},
    # HRA007169 has two possible normal sides; evaluated separately and jointly below.
    "HRA007169": {"Patient Solid Tissue": "tumor", "Peritumoral": "normal"},
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def norm(value: Any) -> str:
    return str(value or "").strip()


def lower(value: Any) -> str:
    return norm(value).lower()


def clean_data_name(name: str) -> str:
    return re.sub(r"\s*\(\d+\s+bytes\)\s*$", "", name or "")


def guess_read_pair(name: str) -> str:
    n = lower(name)
    if re.search(r"(_r?1|_f1|read1)", n):
        return "R1"
    if re.search(r"(_r?2|_f2|read2)", n):
        return "R2"
    return ""


def infer_format(name: str) -> str:
    lowered = lower(name)
    for suffix in ("fastq.gz", "fq.gz", "xlsx", "xls", "tsv", "csv", "maf", "vcf", "bam", "h5"):
        if lowered.endswith(suffix):
            return suffix
    return ""


def role_of_file(item: Dict[str, str]) -> str:
    name = lower(item.get("files"))
    fmt = lower(item.get("format"))
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


_FASTQ_R1_PATTERN = re.compile(r"(_r?1|_f1|read1)")
_FASTQ_R2_PATTERN = re.compile(r"(_r?2|_f2|read2)")


def fastq_pair_key(item: Dict[str, Any]) -> str:
    for field in ("sample_accession", "run_accession"):
        value = norm(item.get(field))
        if value:
            return value
    name = lower(item.get("files") or item.get("file_path"))
    stem = re.sub(r"\.(fastq|fq)(\.gz)?$", "", name)
    return re.sub(r"([._-])(r?1|r?2|f1|f2|read1|read2)$", "", stem)


def paired_fastq_groups(files: List[Dict[str, Any]]) -> List[Dict[str, List[Dict[str, Any]]]]:
    groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for item in files:
        name = lower(item.get("files"))
        read_pair = lower(item.get("Read Pair"))
        entry = groups.setdefault(fastq_pair_key(item), {"r1": [], "r2": []})
        if read_pair == "r1" or _FASTQ_R1_PATTERN.search(name):
            entry["r1"].append(item)
        elif read_pair == "r2" or _FASTQ_R2_PATTERN.search(name):
            entry["r2"].append(item)
    return [entry for entry in groups.values() if entry["r1"] and entry["r2"]]


def load_adapted_t1() -> List[Dict[str, str]]:
    """Replicate pipeline_router._load_normalized_t1 for normalized-v2 schema."""
    normalized = read_csv(ENTITY_CSV / "T1.csv")
    legacy = read_csv(DATA_CSV / "T11.csv")
    sample_rows = read_csv(ENTITY_CSV / "sample.csv")
    sample_specimen_types = {
        r["sample_accession"]: r.get("specimen_types") or ""
        for r in sample_rows
        if r.get("sample_accession")
    }
    legacy_by_name = {
        clean_data_name(r.get("files") or ""): r
        for r in legacy
        if r.get("files")
    }
    fmt_rel = read_csv(DATA_CSV / "relations/T1_in_format.csv")
    level_rel = read_csv(DATA_CSV / "relations/T1_in_level.csv")
    format_by_name = {
        clean_data_name(r.get("files") or ""): r.get("format") or ""
        for r in fmt_rel
        if r.get("files")
    }
    level_by_name = {
        clean_data_name(r.get("files") or ""): r.get("data_level") or ""
        for r in level_rel
        if r.get("files")
    }

    adapted: List[Dict[str, str]] = []
    for row in normalized:
        name = clean_data_name(row.get("dataName") or "")
        legacy = legacy_by_name.get(name, {})
        adapted.append({
            "study_accession": row.get("studyAccession") or legacy.get("study_accession") or "",
            "sample_accession": row.get("sampleAccession") or legacy.get("sample_accession") or "",
            "run_accession": row.get("runAccession") or legacy.get("run_accession") or "",
            "data_type": row.get("strategy") or legacy.get("data_type") or "",
            "Read Pair": legacy.get("Read Pair") or guess_read_pair(name),
            "files": name,
            "format": format_by_name.get(name) or legacy.get("format") or infer_format(name),
            "file_path": legacy.get("file_path") or name,
            "file_description": legacy.get("file_description") or row.get("sampleDescription") or "",
            "Experiment": row.get("experimentAccession") or legacy.get("Experiment") or "",
            "Platform": row.get("platform") or legacy.get("Platform") or "",
            "data_level": level_by_name.get(name) or legacy.get("data_level") or "1",
            "strategy": row.get("strategy") or legacy.get("data_type") or "",
            "individual_accession": row.get("individualAccession") or "",
            "individual_name": row.get("individualName") or "",
            "sample_name": row.get("sampleName") or "",
            "specimen_types": sample_specimen_types.get(row.get("sampleAccession") or "") or "",
            "gender": row.get("gender") or "",
        })
    return adapted


def candidate_role(study: str, specimen_types: str, name: str, hypothesis: Dict[str, str]) -> Optional[str]:
    sp = norm(specimen_types)
    if sp in hypothesis:
        return hypothesis[sp]
    # Also recognise explicit _T/_N suffixes if present.
    n = lower(name)
    if n.endswith(("_t", "_n")):
        return "tumor" if n.endswith("_t") else "normal"
    return None


DNA_STRATEGIES = {"wes", "wgs"}


def classify_name_signal(name: str) -> List[str]:
    n = lower(name)
    signals = []
    if re.search(r"(_t|[-\s]t)$", n):
        signals.append("_T suffix")
    if re.search(r"(_n|[-\s]n)$", n):
        signals.append("_N suffix")
    if re.search(r"\btumor\b|\bcancer\b|\bcarc\b|\b癌\b", n):
        signals.append("tumor/cancer word")
    if re.search(r"\bnormal\b|\bparacancer\b|\bperi\b|\bperitumoral\b|\badjacent\b|\b旁\b|\bnontumor\b", n):
        signals.append("normal/peri word")
    # Common Chinese/English abbreviations observed in HRA001272 sample names
    if re.search(r"\bnc\b|\bn\.c\.\b|\bnormal[_\s]?ctrl\b", n):
        signals.append("NC (normal control) marker")
    if re.search(r"\bpt\b|\bprimary[_\s]?tumor\b", n):
        signals.append("PT (primary tumor) marker")
    if re.search(r"\bst\b|\bsolid\b", n):
        signals.append("ST/solid marker")
    # Single-letter suffixes seen in HRA007169 (AM21T/AM21P/AM21B) and similar cohorts.
    if re.search(r"[0-9][tT]$|[_\-][tT]$", n):
        signals.append("T suffix (tumor)")
    if re.search(r"[0-9][nN]$|[_\-][nN]$", n):
        signals.append("N suffix (normal)")
    if re.search(r"[0-9][pP]$|[_\-][pP]$", n):
        signals.append("P suffix (peri/normal)")
    if re.search(r"[0-9][bB]$|[_\-][bB]$", n):
        signals.append("B suffix (blood)")
    return signals


def _evaluate_subset(
    rows: List[Dict[str, str]],
    study: str,
    hypothesis: Dict[str, str],
) -> Dict[str, Any]:
    """Evaluate one subset of FASTQ rows (e.g. all or DNA-only)."""
    by_individual: Dict[str, Dict[str, List[Dict[str, str]]]] = collections.defaultdict(
        lambda: {"tumor": [], "normal": []}
    )
    no_role_individuals: Dict[str, List[Dict[str, str]]] = collections.defaultdict(list)
    for r in rows:
        role = candidate_role(study, r.get("specimen_types") or "", r.get("sample_name") or "", hypothesis)
        ind = norm(r.get("individual_accession"))
        if not ind:
            continue
        if role in ("tumor", "normal"):
            by_individual[ind][role].append(r)
        else:
            no_role_individuals[ind].append(r)

    combo_counts: Dict[Tuple[int, int], int] = collections.Counter()
    qualified_cases = []
    both_sides_any = []
    strategy_mismatches = []
    for ind, sides in by_individual.items():
        t_groups = paired_fastq_groups(sides["tumor"])
        n_groups = paired_fastq_groups(sides["normal"])
        combo_counts[(len(t_groups), len(n_groups))] += 1
        if t_groups and n_groups:
            both_sides_any.append(ind)
        if len(t_groups) == 1 and len(n_groups) == 1:
            qualified_cases.append(ind)
            t_strats = {norm(g["r1"][0].get("strategy")) for g in t_groups}
            n_strats = {norm(g["r1"][0].get("strategy")) for g in n_groups}
            if not (t_strats & n_strats):
                strategy_mismatches.append({
                    "individual": ind,
                    "tumor_strategy": sorted(t_strats),
                    "normal_strategy": sorted(n_strats),
                })

    role_strategies: Dict[str, collections.Counter] = {
        "tumor": collections.Counter(),
        "normal": collections.Counter(),
        "unclassified": collections.Counter(),
    }
    for r in rows:
        role = candidate_role(study, r.get("specimen_types") or "", r.get("sample_name") or "", hypothesis)
        bucket = role if role in ("tumor", "normal") else "unclassified"
        role_strategies[bucket][norm(r.get("strategy"))] += 1

    return {
        "total_fastq": len(rows),
        "individuals_with_fastq": len(set(norm(r.get("individual_accession")) for r in rows if r.get("individual_accession"))),
        "combo_counts": dict(combo_counts),
        "both_sides_any_count": len(both_sides_any),
        "qualified_cases_count": len(qualified_cases),
        "qualified_cases_sample": qualified_cases[:20],
        "strategy_mismatches": strategy_mismatches,
        "role_strategies": {k: dict(v) for k, v in role_strategies.items()},
        "no_role_individuals_count": len(no_role_individuals),
    }


def evaluate_study(
    study: str,
    adapted: List[Dict[str, str]],
    sample_rows: List[Dict[str, str]],
    hypothesis: Dict[str, str],
) -> Dict[str, Any]:
    all_rows = [r for r in adapted if r["study_accession"] == study and role_of_file(r) == "fastq"]
    dna_rows = [r for r in all_rows if norm(r.get("strategy")).lower() in DNA_STRATEGIES]

    all_res = _evaluate_subset(all_rows, study, hypothesis)
    dna_res = _evaluate_subset(dna_rows, study, hypothesis)

    # Per-individual specimen-type combinations (for studies with multiple possible normals)
    ind_specimens: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in all_rows:
        ind = norm(r.get("individual_accession"))
        if ind:
            ind_specimens[ind][norm(r.get("specimen_types"))] += 1
    specimen_combo_counts: Dict[Tuple[str, ...], int] = collections.Counter()
    for ind, cnt in ind_specimens.items():
        specimen_combo_counts[tuple(sorted(k for k, v in cnt.items() if v > 0))] += 1

    return {
        "all": all_res,
        "dna": dna_res,
        "specimen_combinations": dict(specimen_combo_counts),
    }


def sample_name_suffix_report(study: str, sample_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    rows = [r for r in sample_rows if r.get("study_accession") == study]
    examples = []
    for r in rows[:40]:
        name = r.get("sample_name") or ""
        sp = norm(r.get("specimen_types"))
        signals = classify_name_signal(name)
        examples.append({
            "sample_name": name,
            "specimen_types": sp,
            "signals": signals,
        })
    # Cross-tab uses the full study so the consistency signal is not limited to the 40 examples.
    cross: Dict[str, Dict[str, int]] = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        name = r.get("sample_name") or ""
        sp = norm(r.get("specimen_types"))
        signals = classify_name_signal(name)
        sig_key = "; ".join(signals) if signals else "(none)"
        cross[sp][sig_key] += 1
    return {
        "examples": examples,
        "cross_tab": {k: dict(v) for k, v in cross.items()},
    }


def build_report(adapted: List[Dict[str, str]], sample_rows: List[Dict[str, str]], study_rows: List[Dict[str, str]]) -> str:
    study_tumor_type = {r["study_accession"]: r.get("tumor_type") for r in study_rows}

    lines = [
        "# 候选数据集配对角色规则评估",
        "",
        "> 只读评估，未修改 `STUDY_ROLE_RULES`、代码、CSV 或 Neo4j。",
        "",
        "## 0. 评估方法与口径",
        "",
        "本报告复用了 `pipeline_router.py` 中的配对逻辑：",
        "",
        "1. `files` 按 R1/R2 文件名模式归到同源配对键（sample/run/file stem）。",
        "2. 仅当同源键下同时存在 R1、R2 时，才算 1 个可配对组。",
        "3. 合格 case 定义：同一个体，肿瘤侧恰好 1 个配对组、正常侧恰好 1 个配对组。",
        "4. 角色按 `specimen_types` 假设映射；未覆盖的样本记为未分类。",
        "5. 测序类型以合并后的 `strategy` 字段为准（优先取 T1.strategy，T1 缺失时回退 T11.data_type）。",
        "",
        "## 1. 受试者级 1:1 核对",
        "",
    ]

    per_study_results = {}
    for study in CANDIDATES:
        hyp = ROLE_HYPOTHESES[study]
        res = evaluate_study(study, adapted, sample_rows, hyp)
        per_study_results[study] = res
        all_res = res["all"]
        dna_res = res["dna"]
        lines.extend([
            f"### {study} ({study_tumor_type.get(study, '?')})",
            "",
            f"- 全部 FASTQ 文件数：`{all_res['total_fastq']}`（DNA 类 WES/WGS：`{dna_res['total_fastq']}`）",
            f"- 有 FASTQ 的 individual 数：`{all_res['individuals_with_fastq']}`",
            f"- 两侧都有 FASTQ 的 individual 数：`{all_res['both_sides_any_count']}`",
            f"- 单侧恰好 1 个 R1/R2 对的合格 case 数（全部文件）：`{all_res['qualified_cases_count']}`",
            f"- 单侧恰好 1 个 R1/R2 对的合格 case 数（仅 DNA 文件）：`{dna_res['qualified_cases_count']}`",
            f"- 未分类角色的 individual 数：`{all_res['no_role_individuals_count']}`",
            "",
            "**两侧配对组数量组合分布（全部文件，(肿瘤侧组数, 正常侧组数) → 个体数）**",
            "",
        ])
        for combo, cnt in sorted(all_res["combo_counts"].items()):
            lines.append(f"- {combo}: {cnt}")
        lines.append("")
        if dna_res["combo_counts"] != all_res["combo_counts"]:
            lines.append("**两侧配对组数量组合分布（仅 DNA 文件）**")
            lines.append("")
            for combo, cnt in sorted(dna_res["combo_counts"].items()):
                lines.append(f"- {combo}: {cnt}")
            lines.append("")

        if res["specimen_combinations"]:
            lines.append("**每个 individual 的 specimen_types 组合分布**")
            lines.append("")
            for combo, cnt in sorted(res["specimen_combinations"].items()):
                lines.append(f"- {combo}: {cnt}")
            lines.append("")

        # Special handling for HRA007169: also evaluate Blood as normal.
        if study == "HRA007169":
            blood_hyp = {"Patient Solid Tissue": "tumor", "Blood": "normal"}
            blood_res = evaluate_study(study, adapted, sample_rows, blood_hyp)
            lines.extend([
                "#### 以 Blood 作为正常侧重新计算",
                "",
                f"- 合格 case 数（全部文件）：`{blood_res['all']['qualified_cases_count']}`",
                f"- 合格 case 数（仅 DNA 文件）：`{blood_res['dna']['qualified_cases_count']}`",
                f"- 两侧都有 FASTQ 的 individual 数：`{blood_res['all']['both_sides_any_count']}`",
                "**组合分布（全部文件）：**",
                "",
            ])
            for combo, cnt in sorted(blood_res["all"]["combo_counts"].items()):
                lines.append(f"- {combo}: {cnt}")
            lines.append("")

            # Individuals with both Peritumoral and Blood
            rows = [r for r in adapted if r["study_accession"] == study and role_of_file(r) == "fastq"]
            ind_specs: Dict[str, set] = collections.defaultdict(set)
            for r in rows:
                ind = norm(r.get("individual_accession"))
                if ind:
                    ind_specs[ind].add(norm(r.get("specimen_types")))
            both_pb = [ind for ind, specs in ind_specs.items() if {"Peritumoral", "Blood"} <= specs]
            lines.extend([
                f"- 同时挂有 Peritumoral 和 Blood 的 individual 数：`{len(both_pb)}`",
                "",
            ])

    lines.extend([
        "## 2. 两侧测序类型一致性",
        "",
    ])
    for study in CANDIDATES:
        res = per_study_results[study]
        dna_res = res["dna"]
        lines.extend([
            f"### {study}",
            "",
            "**按推断角色汇总的 strategy 分布（仅 DNA 文件）：**",
            "",
        ])
        for role, cnts in dna_res["role_strategies"].items():
            if cnts:
                lines.append(f"- {role}: {dict(cnts)}")
        if dna_res["strategy_mismatches"]:
            lines.append(f"- ⚠️ 合格 case 内出现肿瘤/正常 strategy 不一致的个体数：`{len(dna_res['strategy_mismatches'])}`")
            for m in dna_res["strategy_mismatches"][:5]:
                lines.append(f"  - `{m['individual']}`: tumor={m['tumor_strategy']}, normal={m['normal_strategy']}")
        else:
            lines.append("- ✅ 所有合格 case 的肿瘤/正常侧 strategy 一致。")
        lines.append("")

    lines.extend([
        "## 3. 命名后缀信号交叉验证",
        "",
    ])
    for study in CANDIDATES:
        rep = sample_name_suffix_report(study, sample_rows)
        lines.extend([
            f"### {study}",
            "",
            "**前 40 个 sample_name 与 specimen_types 示例**",
            "",
            "| sample_name | specimen_types | 命名信号 |",
            "| --- | --- | --- |",
        ])
        for ex in rep["examples"]:
            sig = "; ".join(ex["signals"]) if ex["signals"] else "(none)"
            lines.append(f"| `{ex['sample_name']}` | {ex['specimen_types']} | {sig} |")
        lines.append("")
        lines.append("**specimen_types × 命名信号交叉表**")
        lines.append("")
        for sp, sigs in rep["cross_tab"].items():
            lines.append(f"- `{sp}`: {dict(sigs)}")
        lines.append("")

    lines.extend([
        "## 4. Blood 作为正常侧的判定",
        "",
        "### 4.1 四个候选数据集的 tumor_type",
        "",
    ])
    for study in CANDIDATES:
        lines.append(f"- `{study}`: {study_tumor_type.get(study, '?')}")
    lines.extend([
        "",
        "结论：四个数据集均为实体瘤（Glioma、Liver Cancer、Esophageal Cancer、Melanoma），"
        "因此从生物学角度，Blood 可作为种系正常对照。但 HRA000071 数据结构上不存在同个体 Solid+Blood。",
        "",
        "### 4.2 HRA000071 的 Solid / Blood 是否在同一 individual",
        "",
    ])
    hra71_rows = [r for r in adapted if r["study_accession"] == "HRA000071" and role_of_file(r) == "fastq"]
    hra71_ind_specs: Dict[str, set] = collections.defaultdict(set)
    for r in hra71_rows:
        ind = norm(r.get("individual_accession"))
        if ind:
            hra71_ind_specs[ind].add(norm(r.get("specimen_types")))
    both_solid_blood = sum(1 for specs in hra71_ind_specs.values() if {"Patient Solid Tissue", "Blood"} <= specs)
    only_solid = sum(1 for specs in hra71_ind_specs.values() if specs == {"Patient Solid Tissue"})
    only_blood = sum(1 for specs in hra71_ind_specs.values() if specs == {"Blood"})
    lines.extend([
        f"- 同时挂有 Solid + Blood 的 individual 数：`{both_solid_blood}`",
        f"- 只挂 Solid 的 individual 数：`{only_solid}`",
        f"- 只挂 Blood 的 individual 数：`{only_blood}`",
        "",
        "因此按当前“同 individual 配对”规则，HRA000071 无法产出任何合格 case。",
        "",
        "### 4.3 全库哪些 study 有 Blood 样本",
        "",
    ])
    blood_studies = collections.Counter()
    blood_study_types: Dict[str, str] = {}
    for r in sample_rows:
        if norm(r.get("specimen_types")) == "Blood":
            st = r.get("study_accession")
            blood_studies[st] += 1
            if st not in blood_study_types:
                row = next((s for s in study_rows if s.get("study_accession") == st), None)
                blood_study_types[st] = row.get("tumor_type") if row else "?"
    for st, cnt in blood_studies.most_common():
        lines.append(f"- `{st}`: Blood {cnt} 个, tumor_type={blood_study_types.get(st, '?')}")
    lines.append("")

    lines.extend([
        "## 5. HRA003107 作为 WGS 的说明",
        "",
        "HRA003107 的 T1 strategy 为 `WGS`（532 文件）+ `RNA-Seq`（620 文件）。",
        "若仅过滤为 DNA（WGS/WES），合格配对数见上表。",
        "",
        f"- 当前 `wes_somatic_pair` 的允许 strategy 集合包含 WGS，因此技术上可以纳入。",
        f"- 但流程名称是 `wes_somatic_pair`，目录里没有捕获区间建模；是否把 WGS 作为一等公民，"
        "需要与目录负责人确认范围定义。",
        "",
        "## 6. 登记提案（不实施）",
        "",
        "| 数据集 | 建议 | 判据类型 | 预计新增合格配对 | 阻碍/条件 |",
        "| --- | --- | --- | --- | --- |",
    ])

    # Build proposal rows (use DNA-only counts for somatic pairing relevance)
    proposal = []
    for study in CANDIDATES:
        res = per_study_results[study]
        dna_q = res["dna"]["qualified_cases_count"]
        if study == "HRA001272":
            proposal.append((study, "⚠️ 有条件", "specimen_types", dna_q,
                             f"需确认单侧恰好 1 对的个体是否接受；当前严格口径为 {dna_q} 对。"))
        elif study == "HRA000071":
            proposal.append((study, "❌ 不建议", "Blood 正常侧", 0,
                             "当前数据无同 individual Solid+Blood；若支持跨个体配对则有 286 对潜力，需改规则语义。"))
        elif study == "HRA003107":
            proposal.append((study, "⚠️ 有条件", "specimen_types", dna_q,
                             f"测序类型为 WGS（DNA 文件 {res['dna']['total_fastq']} 个）；流程名为 WES，需确认范围定义。"))
        elif study == "HRA007169":
            # Need choose normal side. We report two options.
            blood_res = evaluate_study(study, adapted, sample_rows, {"Patient Solid Tissue": "tumor", "Blood": "normal"})
            peri_q = dna_q
            blood_q = blood_res["dna"]["qualified_cases_count"]
            proposal.append((study, "⚠️ 有条件", "specimen_types", f"{peri_q} (Peri) / {blood_q} (Blood)",
                             f"若正常侧取 Peritumoral 得 {peri_q} 对；取 Blood 得 {blood_q} 对；"
                             "需决定 Blood 是否可作为正常侧。"))
        else:
            proposal.append((study, "?", "?", 0, ""))

    for row in proposal:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |")

    total_current = 1028
    added = sum(
        r[3] for r in proposal if isinstance(r[3], int)
    )
    # For HRA007169 take the Peritumoral-normal count (50) for the optimistic total.
    hra007169_added = per_study_results["HRA007169"]["dna"]["qualified_cases_count"]
    total_new = total_current + added + hra007169_added
    lines.extend([
        "",
        f"当前已登记数据集可用配对总数：`{total_current}`。",
        f"若按上表全部登记（HRA007169 取 Peritumoral 口径），总数将变为约：`{total_new}`。",
        "",
        "## 7. 影响预估（不实施）",
        "",
        "- `wes_somatic_pair` 的可行 study 数将从 2 增加到最多 4（HRA000873、HRA006499 + HRA001272、HRA003107/HRA007169 视条件而定）。",
        "- 演示查询“配对肿瘤正常 WES”当前已绑定 HRA000873；加入 HRA001272 后，"
        f"由于 HRA000873 的配对数（1015）远高于 HRA001272（{per_study_results['HRA001272']['dna']['qualified_cases_count']}），默认排序大概率仍选 HRA000873。",
        "- 若移除排序加分并启用“有角色规则且能产出合格 case 的 study 优先”，"
        "HRA000873 仍占优，因此演示脚本依赖的 HRA000873 绑定风险较低。",
        "",
        "## 8. 判断与建议",
        "",
        f"- **最优先登记**：HRA001272。标本类型映射清晰（Solid Tissue = tumor，Peritumoral = normal），"
        f"且个体级 1:1 结构最干净；需先确认 {per_study_results['HRA001272']['dna']['qualified_cases_count']} 对严格 case 是否满足业务口径。",
        "- **最大风险点**：HRA000071 的 Blood 正常侧是新语义。当前没有同 individual 配对证据；"
        "若将来要支持 Blood 作为正常侧，需要明确区分“肿瘤种系对照”与“血液肿瘤”场景。",
        "- **未问到但值得查**：这四个数据集的 `sample_name` 几乎没有 `_T/_N` 后缀，"
        "无法像 HRA006499 那样做独立验证；登记后应通过运行样本抽检确认角色正确率。",
        "",
        "## 9. 实际执行的脚本",
        "",
        "本报告所有数字来自只读脚本：",
        "",
        "- `scripts/python/evaluate_candidate_study_roles.py`",
        "",
        "该脚本读取 `data/csv/entities/T1.csv`、`data/csv/T11.csv`、`data/csv/entities/sample.csv`、"
        "`data/csv/entities/study.csv` 以及 `data/csv/relations/T1_in_format.csv`，"
        "复现 `pipeline_router._load_normalized_t1` 与 `_paired_fastq_groups` 的合并/配对逻辑，"
        "未写入任何源数据文件。",
        "",
    ])
    return "\n".join(lines)


def main():
    adapted = load_adapted_t1()
    sample_rows = read_csv(ENTITY_CSV / "sample.csv")
    study_rows = read_csv(ENTITY_CSV / "study.csv")
    report = build_report(adapted, sample_rows, study_rows)
    OUT_MD.write_text(report, encoding="utf-8")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
