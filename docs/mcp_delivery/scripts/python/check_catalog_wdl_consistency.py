#!/usr/bin/env python3
"""Audit WDL declarations against the current or proposed tool catalog.

This script is deliberately independent from the runtime composer. It reads WDL,
CSV, an optional read-only Neo4j catalog, and the target slot table embedded in
docs/target_catalog_spec.md. It never writes catalog data or Neo4j.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
WDL_ROOT = ROOT / "incoming" / "bio_pipelines_repo" / "pipelines"

CATALOG_TO_RUNTIME_ID = {
    "T01": "fastp", "T02": "fastqc", "T03": "bwa", "T04": "samtools",
    "T05": "gatk", "T06": "bcftools", "T07": "snpeff",
    "T08": "trim_galore", "T09": "star", "T10": "rsem",
    "T11": "featurecounts", "T12": "multiqc",
}

SEMANTIC_TO_ARTIFACT = {
    "Raw FASTQ": "raw_fastq_read",
    "Clean FASTQ": "clean_fastq_read",
    "Genome Annotation": "genome_annotation",
    "Aligned SAM/BAM": "aligned_bam",
    "Sorted/Dedup BAM": "sorted_dedup_bam",
    "Unfiltered VCF": "unfiltered_vcf",
    "Filtered (PASS) VCF": "filtered_vcf",
    "Annotated VCF": "annotated_vcf",
    "Transcriptome BAM": "transcriptome_bam",
    "TPM / FPKM": "expression_abundance_matrix",
    "Raw Counts": "expression_count_matrix",
    "Quality Control Report": "quality_control_report",
}

OPTIONAL_CURRENT_INPUTS = {
    ("fastqc", "raw_fastq_read"),
    ("fastqc", "clean_fastq_read"),
    ("multiqc", "quality_control_report"),
}

UNATOMIZED_TOOL_TERMS = {
    "cellranger": ("cellranger",),
    "limma": ("limma",),
    "clusterprofiler": ("clusterprofiler", "clusterProfiler"),
    "reactomepa": ("reactomepa", "ReactomePA"),
    "annotationdbi_org_hs": ("annotationdbi", "AnnotationDbi", "org.Hs.eg.db"),
    "edger": ("edger", "edgeR"),
    "mclust": ("mclust",),
    "iobr_cibersort": ("iobr", "IOBR", "cibersort", "CIBERSORT"),
    "survival_survminer": ("survival", "survminer"),
    "dbscan": ("dbscan",),
    "maftools": ("maftools",),
    "deseq2": ("deseq2", "DESeq2"),
    "wgcna": ("WGCNA",),
    "stringdb_igraph": ("STRINGdb", "igraph"),
    "driver_gene_gender": ("analyze_driver_gene_gender",),
    "tmb_calculation": ("PreparePatientTMB", "prepare_tmb_inputs"),
}

DIRECT_TASK_BOUNDARIES = {
    "cellranger": ["RunFullPipeline"],
    "driver_gene_gender": ["analyze_driver_gene_gender"],
    "tmb_calculation": ["PreparePatientTMB"],
}

COMMAND_PATTERNS = [
    ("cellranger count", r"\bcellranger\s+count\b"),
    ("fastp", r"\bfastp\b"),
    ("fastqc", r"\bfastqc\b"),
    ("bwa mem", r"\bbwa\s+mem\b"),
    ("STAR", r"(?:^|\s)STAR\s"),
    ("samtools sort", r"\bsamtools\s+sort\b"),
    ("samtools fixmate", r"\bsamtools\s+fixmate\b"),
    ("samtools markdup", r"\bsamtools\s+markdup\b"),
    ("samtools index", r"\bsamtools\s+index\b"),
    ("samtools flagstat", r"\bsamtools\s+flagstat\b"),
    ("samtools stats", r"\bsamtools\s+stats\b"),
    ("samtools idxstats", r"\bsamtools\s+idxstats\b"),
    ("gatk MarkDuplicates", r"\bgatk\b[^\n]*\bMarkDuplicates\b"),
    ("gatk BaseRecalibrator", r"\bgatk\b[^\n]*\bBaseRecalibrator\b"),
    ("gatk ApplyBQSR", r"\bgatk\b[^\n]*\bApplyBQSR\b"),
    ("gatk Mutect2", r"\bgatk\b[^\n]*\bMutect2\b"),
    ("gatk GetPileupSummaries", r"\bgatk\b[^\n]*\bGetPileupSummaries\b"),
    ("gatk CalculateContamination", r"\bgatk\b[^\n]*\bCalculateContamination\b"),
    ("gatk LearnReadOrientationModel", r"\bgatk\b[^\n]*\bLearnReadOrientationModel\b"),
    ("gatk FilterMutectCalls", r"\bgatk\b[^\n]*\bFilterMutectCalls\b"),
    ("gatk FastqToSam", r"\bFastqToSam\b"),
    ("bcftools view", r"\bbcftools\s+view\b"),
    ("bcftools norm", r"\bbcftools\s+norm\b"),
    ("bcftools index", r"\bbcftools\s+index\b"),
    ("bcftools stats", r"\bbcftools\s+stats\b"),
    ("bcftools query", r"\bbcftools\s+query\b"),
    ("snpEff ann", r"\bsnpEff\s+ann\b"),
    ("rsem-calculate-expression", r"\brsem-calculate-expression\b"),
    ("featureCounts", r"\bfeatureCounts\b"),
    ("multiqc", r"\bmultiqc\b"),
    ("Rscript", r"\bRscript\b"),
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def matching_brace(text: str, opening: int) -> int:
    depth = 0
    quote: Optional[str] = None
    escaped = False
    i = opening
    while i < len(text):
        char = text[i]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            i += 1
            continue
        if text.startswith("<<<", i):
            end = text.find(">>>", i + 3)
            if end < 0:
                return len(text) - 1
            i = end + 3
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text) - 1


def definition_slices(text: str) -> List[Tuple[str, str, int, int, str]]:
    matches = list(re.finditer(r"(?m)^(workflow|task)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", text))
    result = []
    for match in matches:
        opening = text.find("{", match.start(), match.end())
        end = matching_brace(text, opening)
        result.append((match.group(1), match.group(2), match.start(), end + 1, text[match.start():end + 1]))
    return result


def named_block(body: str, name: str) -> Optional[Tuple[str, int]]:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*\{{", body)
    if not match:
        return None
    opening = body.find("{", match.start(), match.end())
    end = matching_brace(body, opening)
    return body[opening + 1:end], opening + 1


DECL_RE = re.compile(
    r"^\s*(Array\[[^\]]+\]\??|Map\[[^\]]+\]\??|Pair\[[^\]]+\]\??|"
    r"File\??|String\??|Int\??|Float\??|Boolean\??)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)(?:\s*=\s*(.*))?$"
)


def declarations(block: Optional[Tuple[str, int]], block_start_line: int) -> List[Dict[str, Any]]:
    if not block:
        return []
    text, offset = block
    lines = text.splitlines()
    result: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        raw = lines[i].split("#", 1)[0].rstrip().rstrip(",")
        match = DECL_RE.match(raw)
        if not match:
            i += 1
            continue
        wdl_type, name, default = match.groups()
        start = i
        if default is not None:
            value = default.strip()
            while value.count("[") > value.count("]") and i + 1 < len(lines):
                i += 1
                value += " " + lines[i].split("#", 1)[0].strip().rstrip(",")
            default = value
        result.append({
            "name": name,
            "type": wdl_type,
            "optional": wdl_type.endswith("?"),
            "has_default": default is not None,
            "default": default,
            "line": block_start_line + start,
        })
        i += 1
    return result


def command_block(body: str) -> str:
    heredoc = re.search(r"(?s)\bcommand\s*<<<(.*?)>>>", body)
    if heredoc:
        return heredoc.group(1).strip()
    block = named_block(body, "command")
    return block[0].strip() if block else ""


def command_summary(command: str) -> Dict[str, Any]:
    commands = [label for label, pattern in COMMAND_PATTERNS if re.search(pattern, command, re.I | re.M)]
    script_paths = sorted(set(re.findall(r"(?:/[^\s\"']+\.(?:R|py)|~\{[^}]*script[^}]*\})", command)))
    return {
        "commands": commands,
        "script_paths": script_paths,
        "summary": "; ".join(commands + script_paths) if command else "",
    }


def runtime_values(block: Optional[Tuple[str, int]]) -> Dict[str, str]:
    if not block:
        return {}
    values: Dict[str, str] = {}
    for line in block[0].splitlines():
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$", line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def parse_wdl(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    definitions = definition_slices(text)
    workflows = []
    tasks = []
    for kind, name, start, _end, body in definitions:
        base_line = line_number(text, start)
        input_block = named_block(body, "input")
        output_block = named_block(body, "output")
        input_line = base_line + body.count("\n", 0, input_block[1]) if input_block else base_line
        output_line = base_line + body.count("\n", 0, output_block[1]) if output_block else base_line
        record: Dict[str, Any] = {
            "name": name,
            "line": base_line,
            "inputs": declarations(input_block, input_line),
            "outputs": declarations(output_block, output_line),
        }
        if kind == "workflow":
            record["calls"] = [
                {
                    "task": match.group(1),
                    "alias": match.group(2) or match.group(1),
                    "line": base_line + body.count("\n", 0, match.start()),
                }
                for match in re.finditer(
                    r"(?m)^\s*call\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?",
                    body,
                )
            ]
            workflows.append(record)
        else:
            command = command_block(body)
            record["command"] = command_summary(command)
            record["runtime"] = runtime_values(named_block(body, "runtime"))
            tasks.append(record)
    companions = sorted(
        str(item.relative_to(ROOT))
        for item in path.parent.iterdir()
        if item.is_file() and item != path
    )
    return {
        "pipeline_id": path.parent.name,
        "path": str(path.relative_to(ROOT)),
        "line_count": len(text.splitlines()),
        "companion_files": companions,
        "workflows": workflows,
        "tasks": tasks,
    }


def build_inventory() -> Dict[str, Any]:
    files = [parse_wdl(path) for path in sorted(WDL_ROOT.glob("*/*.wdl"))]
    all_text = "\n".join((ROOT / item["path"]).read_text(encoding="utf-8") for item in files)
    coverage = []
    for tool_id, terms in UNATOMIZED_TOOL_TERMS.items():
        evidence_files = []
        for item in files:
            text = (ROOT / item["path"]).read_text(encoding="utf-8")
            if any(term.lower() in text.lower() for term in terms):
                evidence_files.append(item["path"])
        coverage.append({
            "tool_id": tool_id,
            "mentioned_in_wdl": any(term.lower() in all_text.lower() for term in terms),
            "evidence_files": evidence_files,
            "independent_task_names": DIRECT_TASK_BOUNDARIES.get(tool_id, []),
            "has_independent_task_boundary": bool(DIRECT_TASK_BOUNDARIES.get(tool_id)),
        })
    companion_counts = Counter(Path(path).suffix or "no_extension" for item in files for path in item["companion_files"])
    return {
        "schema_version": "wdl-inventory/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(WDL_ROOT.relative_to(ROOT)),
        "summary": {
            "wdl_files": len(files),
            "workflow_definitions": sum(len(item["workflows"]) for item in files),
            "task_definitions": sum(len(item["tasks"]) for item in files),
            "companion_file_counts": dict(sorted(companion_counts.items())),
        },
        "files": files,
        "unatomized_tool_coverage": coverage,
        "judgment": {
            "most_surprising_gap": (
                "The 26 WDL tasks are not the proposed 28 atomic catalog tools; most software "
                "boundaries are embedded in composite tasks."
            ),
            "subcommand_model": (
                "Prefer one node per materializable biological stage plus an operation profile; "
                "do not create a node for every CLI subcommand without a declared boundary."
            ),
            "additional_gaps": [
                "RSEM gene and isoform outputs are collapsed in the current catalog.",
                "STAR clean_fastq_read actually represents rRNA-depleted/unmapped reads.",
                "MultiQC needs named producer fan-in plus an at-least-one constraint.",
            ],
            "decide_before_decomposition": [
                "Canonical slot names and WDL-local binding rules.",
                "Composite-task materialization and operation/subcommand boundaries.",
                "Variant selection, conditional requiredness, and asset-dimension validation.",
            ],
        },
    }


def current_csv_slots() -> List[Dict[str, Any]]:
    root = ROOT / "data" / "csv" / "relations"
    slots = []
    for direction, filename, semantic_key in (
        ("input", "tool_input_format.csv", "语义输入格式"),
        ("output", "tool_output_format.csv", "语义输出格式"),
    ):
        for row in read_csv(root / filename):
            tool_id = CATALOG_TO_RUNTIME_ID.get(row.get("tool_id", ""))
            if not tool_id:
                continue
            semantic = row.get(semantic_key, "")
            artifact = SEMANTIC_TO_ARTIFACT.get(semantic, re.sub(r"[^a-z0-9]+", "_", semantic.lower()).strip("_"))
            slots.append({
                "tool_id": tool_id,
                "slot_name": artifact,
                "direction": direction,
                "artifact": artifact,
                "required": direction == "input" and (tool_id, artifact) not in OPTIONAL_CURRENT_INPUTS,
                "type": "File",
                "source": f"data/csv/relations/{filename}",
            })
    return slots


def current_neo4j_slots() -> List[Dict[str, Any]]:
    sys.path.insert(0, str(ROOT))
    from runtime_config import initialize_runtime  # type: ignore
    from neo4j_observability import Neo4jClient  # type: ignore

    initialize_runtime()
    client = Neo4jClient()
    try:
        payload = client.tool_catalog()
    finally:
        client.close()
    if not payload.get("connected"):
        raise RuntimeError(f"Neo4j unavailable: {payload.get('error')}")
    slots = []
    for tool in payload.get("tools") or []:
        if tool.get("tool_kind") != "atomic":
            continue
        for direction, key in (("input", "inputs"), ("output", "outputs")):
            for slot in tool.get(key) or []:
                artifacts = slot.get("artifacts") or []
                slots.append({
                    "tool_id": tool.get("tool_id"),
                    "slot_name": slot.get("slot_name"),
                    "direction": direction,
                    "artifact": artifacts[0] if artifacts else None,
                    "required": bool(slot.get("required")) if direction == "input" else False,
                    "type": "File",
                    "source": "neo4j",
                })
    return slots


TARGET_HEADER = ["tool_id", "slot_name", "direction", "artifact", "required", "variant", "wdl_variable", "evidence"]


def declaration_type_index(inventory: Dict[str, Any]) -> Dict[str, List[str]]:
    """Index WDL declaration names without pretending task-local names are global IDs."""
    result: Dict[str, set[str]] = defaultdict(set)
    for item in inventory.get("files") or []:
        for definition in (item.get("workflows") or []) + (item.get("tasks") or []):
            for declaration in (definition.get("inputs") or []) + (definition.get("outputs") or []):
                name = str(declaration.get("name") or "")
                wdl_type = str(declaration.get("type") or "")
                if name and wdl_type:
                    result[name].add(wdl_type)
    return {name: sorted(types) for name, types in result.items()}


def inferred_wdl_type(reference: str, type_index: Dict[str, List[str]]) -> str:
    names = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", reference)
    types = sorted({wdl_type for name in names for wdl_type in type_index.get(name, [])})
    if len(types) == 1:
        return types[0]
    if types:
        return "mixed[" + ",".join(types) + "]"
    return "unknown"


def target_slots(path: Path, inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    type_index = declaration_type_index(inventory)
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("| tool_id | slot_name | direction | artifact | required | variant | WDL variable | evidence |"):
            continue
        for row_line in lines[index + 2:]:
            if not row_line.startswith("|"):
                break
            cells = [cell.strip().strip("`") for cell in row_line.strip().strip("|").split("|")]
            if len(cells) != 8:
                continue
            if cells[2] not in {"input", "output"}:
                continue
            rows.append({
                "tool_id": cells[0], "slot_name": cells[1], "direction": cells[2],
                "artifact": cells[3], "required": cells[4].lower() == "true",
                "variant": cells[5], "wdl_variable": cells[6], "evidence": cells[7],
                "type": inferred_wdl_type(cells[6], type_index),
            })
        break
    if not rows:
        raise ValueError(f"No machine-readable target slot table found in {path}")
    return rows


def slot_key(slot: Dict[str, Any]) -> Tuple[str, str, str]:
    return str(slot.get("tool_id")), str(slot.get("direction")), str(slot.get("slot_name"))


def compare_slots(current: Sequence[Dict[str, Any]], target: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    current_map = {slot_key(slot): slot for slot in current}
    target_map = {slot_key(slot): slot for slot in target}
    missing = [target_map[key] for key in sorted(target_map.keys() - current_map.keys())]
    extra = [current_map[key] for key in sorted(current_map.keys() - target_map.keys())]
    mismatched = []
    for key in sorted(current_map.keys() & target_map.keys()):
        differences = {}
        for field in ("artifact", "required", "type"):
            if field == "type" and str(target_map[key].get(field, "")).startswith(("unknown", "mixed[")):
                continue
            if current_map[key].get(field) != target_map[key].get(field):
                differences[field] = {
                    "current": current_map[key].get(field),
                    "target": target_map[key].get(field),
                }
        if differences:
            mismatched.append({"key": key, "differences": differences})
    tool_ids = sorted({str(slot.get("tool_id")) for slot in current} | {str(slot.get("tool_id")) for slot in target})
    by_tool = {}
    for tool_id in tool_ids:
        by_tool[tool_id] = {
            "current": sum(str(slot.get("tool_id")) == tool_id for slot in current),
            "target": sum(str(slot.get("tool_id")) == tool_id for slot in target),
            "missing": sum(str(slot.get("tool_id")) == tool_id for slot in missing),
            "extra": sum(str(slot.get("tool_id")) == tool_id for slot in extra),
            "mismatched": sum(str(item["key"][0]) == tool_id for item in mismatched),
        }
    return {
        "current_slot_count": len(current),
        "target_slot_count": len(target),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "mismatched_count": len(mismatched),
        "by_tool": by_tool,
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
    }


def inventory_name_audit(inventory: Dict[str, Any], current: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    wdl_file_variables = set()
    task_names = set()
    for item in inventory.get("files") or []:
        for task in item.get("tasks") or []:
            task_names.add(task.get("name"))
            for declaration in (task.get("inputs") or []) + (task.get("outputs") or []):
                if str(declaration.get("type", "")).startswith(("File", "Array[File]")):
                    wdl_file_variables.add(declaration.get("name"))
    unmatched = [
        slot for slot in current
        if slot.get("slot_name") not in wdl_file_variables
    ]
    return {
        "task_count": len(task_names),
        "wdl_file_variable_count": len(wdl_file_variables),
        "catalog_slot_count": len(current),
        "exact_name_match_count": len(current) - len(unmatched),
        "name_mismatch_count": len(unmatched),
        "name_mismatches": unmatched,
        "note": "Exact names are diagnostic only: the current catalog uses semantic names while WDL uses task-local variables.",
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=ROOT / "docs" / "wdl_inventory.json")
    parser.add_argument("--generate-inventory", action="store_true")
    parser.add_argument("--catalog-source", choices=("csv", "neo4j"), default="csv")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON report path; stdout is always used")
    args = parser.parse_args(argv)

    if args.generate_inventory:
        inventory = build_inventory()
        args.inventory.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))

    current = current_neo4j_slots() if args.catalog_source == "neo4j" else current_csv_slots()
    report: Dict[str, Any] = {
        "schema_version": "catalog-wdl-consistency/v1",
        "catalog_source": args.catalog_source,
        "inventory": str(args.inventory),
        "inventory_summary": inventory.get("summary"),
        "wdl_name_audit": inventory_name_audit(inventory, current),
    }
    if args.target:
        target = target_slots(args.target, inventory)
        report["target"] = str(args.target)
        report["target_distance"] = compare_slots(current, target)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
