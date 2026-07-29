#!/usr/bin/env python3
"""Normalize the 7.28 data package into the MCP CSV data contract.

The source package owns the data domain.  The existing MCP package owns the
tool catalog, NEXT edges, slots, and execution contracts.  This command writes
a new data directory and never overwrites the current ``data/csv`` directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping


FORMAT_RENAMES = {
    "METADATA_SAMPLEINFO": "METADATA_SAMPLE_INFO",
    "MUTATION_ANNOTATION_FORMA_MAF": "MUTATION_ANNOTATION_FORMAT_MAF",
    "RNA_SPLICEJUNCTION_TAB": "RNA_SPLICE_JUNCTION_TAB",
}

MODAL_TO_STRATEGY = {
    "WES": "WES",
    "RNA": "RNA-Seq",
    "sc-RNA": "scRNA-seq",
    "Clinical": "Clinical",
    "Meta": "Meta",
}

TOOL_CATALOG_FILES = (
    "catalog/artifact_type.csv",
    "catalog/format.csv",
    "catalog/function.csv",
    "catalog/io_slot.csv",
    "catalog/relationships.csv",
    "catalog/tool_id.csv",
    "entities/tool.csv",
    "reference/function.csv",
    "reference/tool_types.csv",
)

T1_HEADERS = [
    "studyAccession",
    "individualAccession",
    "individualName",
    "sampleAccession",
    "sampleDescription",
    "sampleName",
    "gender",
    "runAccession",
    "dataName",
    "experimentAccession",
    "platform",
    "strategy",
]

T11_HEADERS = [
    "study_accession",
    "sample_accession",
    "run_accession",
    "data_type",
    "Read Pair",
    "files",
    "file_name",
    "format",
    "file_path",
    "file_description",
    "Experiment",
    "Platform",
    "data_level",
    "pipeline-id",
    "parameter",
]

T2_HEADERS = [
    "study_accession",
    "t2_id",
    "files",
    "file_type",
    "format",
    "size",
    "data_level",
    "size_bytes",
    "file_path",
    "strategy",
    "run_accession",
    "semantic_format",
    "sample_accession",
    "individual_accession",
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gb18030")
    reader = csv.DictReader(text.splitlines())
    fields = list(reader.fieldnames or [])
    if not fields:
        raise ValueError(f"missing CSV header: {path}")
    rows = []
    for row in reader:
        if None in row:
            raise ValueError(f"extra CSV columns: {path}")
        values = {field: row.get(field) or "" for field in fields}
        if any(values.values()):
            rows.append(values)
    return fields, rows


def read_optional(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    return read_csv(path)


def write_csv(path: Path, fields: list[str], rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: str(row.get(field) or "") for field in fields} for row in rows)


def dedupe_exact(rows: Iterable[Mapping[str, str]], fields: list[str]) -> list[dict[str, str]]:
    seen: set[tuple[str, ...]] = set()
    result = []
    for row in rows:
        key = tuple(str(row.get(field) or "") for field in fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(row))
    return result


def first_by(rows: Iterable[Mapping[str, str]], key: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if value and value not in result:
            result[value] = dict(row)
    return result


def rename_format(value: str) -> str:
    result = value or ""
    for old, new in FORMAT_RENAMES.items():
        result = result.replace(old, new)
    return result


def infer_read_pair(name: str) -> str:
    lowered = (name or "").lower()
    if re.search(r"(?:^|[_ .-])(?:r?1|f1|read1)(?:[_ .-]|$)", lowered):
        return "R1"
    if re.search(r"(?:^|[_ .-])(?:r?2|f2|read2)(?:[_ .-]|$)", lowered):
        return "R2"
    return ""


def locate_root(extract_dir: Path) -> Path:
    matches = sorted({path.parent.parent for path in extract_dir.rglob("entities/T1.csv")})
    if len(matches) != 1:
        raise ValueError(f"expected one 7.28 package root, found {len(matches)}")
    return matches[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_tool_catalog(base_csv: Path, output_csv: Path) -> None:
    for relative in TOOL_CATALOG_FILES:
        source = base_csv / relative
        if not source.exists():
            raise FileNotFoundError(f"missing current MCP tool file: {source}")
        target = output_csv / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    source_relations = base_csv / "relations"
    for source in source_relations.glob("tool_*.csv"):
        target = output_csv / "relations" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def normalize(source_zip: Path, output_csv: Path, base_csv: Path) -> dict:
    if output_csv.exists():
        raise FileExistsError(f"output already exists: {output_csv}; remove it or choose another path")
    output_csv.mkdir(parents=True)
    copy_tool_catalog(base_csv, output_csv)

    with tempfile.TemporaryDirectory(prefix="mcp-update728-") as temp:
        extract_dir = Path(temp)
        with zipfile.ZipFile(source_zip) as archive:
            archive.extractall(extract_dir)
        source = locate_root(extract_dir)

        _, projects = read_csv(source / "entities/project.csv")
        _, studies = read_csv(source / "entities/study.csv")
        _, individuals_raw = read_csv(source / "entities/individual.csv")
        _, samples_raw = read_csv(source / "entities/sample.csv")
        _, t1_raw = read_csv(source / "entities/T1.csv")
        _, t2_raw = read_csv(source / "entities/T2.csv")

        _, t1_study_raw = read_optional(source / "relations/T1_in_study.csv")
        _, t1_sample_raw = read_optional(source / "relations/T1_in_sample.csv")
        _, t1_format_raw = read_optional(source / "relations/T1_in_format.csv")
        _, t1_level_raw = read_optional(source / "relations/T1_in_level.csv")
        _, t1_modal_raw = read_optional(source / "relations/T1_in_modal.csv")
        _, t2_parent_raw = read_optional(source / "relations/T2_generated_from_T1.csv")
        _, t2_study_raw = read_optional(source / "relations/T2_in_study.csv")
        _, t2_format_raw = read_optional(source / "relations/T2_in_format.csv")
        _, t2_level_raw = read_optional(source / "relations/T2_in_level.csv")
        _, t2_modal_raw = read_optional(source / "relations/T2_in_modal.csv")
        _, individual_study_raw = read_optional(source / "relations/individual_in_study.csv")
        _, sample_individual_raw = read_optional(source / "relations/sample_in_individual.csv")
        _, study_project_raw = read_optional(source / "relations/study_in_project.csv")

        t1_rows = dedupe_exact(t1_raw, list(t1_raw[0]) if t1_raw else ["T1_id"])
        t1_by_id = first_by(t1_rows, "T1_id")
        t2_rows = dedupe_exact(t2_raw, list(t2_raw[0]) if t2_raw else ["T2_id"])
        t2_by_id = first_by(t2_rows, "T2_id")

        # The runtime historically treats individual_accession as the matching
        # key. Keep the first source row deterministically; study-specific rows
        # remain available through the individual_in_study relation.
        individuals = list(first_by(individuals_raw, "individual_accession").values())
        samples = dedupe_exact(samples_raw, list(samples_raw[0]) if samples_raw else ["sample_accession"])
        sample_by_id = first_by(samples, "sample_accession")

        t1_study = defaultdict(set)
        for row in t1_study_raw:
            if row.get("T1_id") and row.get("study_accession"):
                t1_study[row["T1_id"]].add(row["study_accession"])
        t1_sample = {row.get("T1_id"): row.get("sample_accession") for row in t1_sample_raw if row.get("T1_id")}
        t1_format = {row.get("T1_id"): rename_format(row.get("semantic_format") or row.get("format")) for row in t1_format_raw if row.get("T1_id")}
        t1_level = {row.get("T1_id"): row.get("data_level") for row in t1_level_raw if row.get("T1_id")}
        t1_modal = defaultdict(set)
        for row in t1_modal_raw:
            if row.get("T1_id") and row.get("modal"):
                t1_modal[row["T1_id"]].add(row["modal"])

        individual_studies = defaultdict(set)
        for row in individual_study_raw:
            if row.get("individual_accession") and row.get("study_accession"):
                individual_studies[row["individual_accession"]].add(row["study_accession"])
        sample_studies = {
            row.get("sample_accession"): row.get("study_accession")
            for row in samples
            if row.get("sample_accession")
        }

        project_fields = [
            "project_accession", "project_name", "project_code", "relevance", "project_description",
            "data_types", "organisms", "sample_scope", "individual_count", "country", "tumor_type",
            "study_accession", "type", "health_conditions", "organization", "submission_date",
            "release_date", "information_source",
        ]
        project_rows = []
        for row in projects:
            project_rows.append({
                "project_accession": row.get("project_accession"),
                "project_name": row.get("project_name"),
                "project_code": row.get("project_code"),
                "relevance": row.get("relevance"),
                "project_description": row.get("project_description"),
                "data_types": row.get("data_types") or row.get("data_type"),
                "organisms": row.get("organisms") or row.get("organism"),
                "sample_scope": row.get("sample_scope"),
                "individual_count": row.get("individual_count"),
                "country": row.get("country"),
                "tumor_type": row.get("tumor_type"),
                "study_accession": row.get("study_accession"),
                "type": row.get("type"),
                "health_conditions": row.get("health_conditions"),
                "organization": row.get("organization"),
                "submission_date": row.get("submission_date"),
                "release_date": row.get("release_date"),
                "information_source": row.get("information_source"),
            })
        project_rows = list(first_by(project_rows, "project_accession").values())

        study_fields = [
            "study_accession", "title", "study_description", "study_type", "tumor_type",
            "individual_count", "sample_count", "information_source",
        ]
        study_rows = []
        for row in studies:
            copied = dict(row)
            copied["title"] = copied.get("title") or copied.get("Title")
            study_rows.append({field: copied.get(field) for field in study_fields})
        study_rows = list(first_by(study_rows, "study_accession").values())

        sample_fields = [
            "study_accession", "sample_accession", "sample_name", "sample_description",
            "individual_accession", "individual_name", "biospecimen_anatomic_site", "sample_type",
            "specimen_types", "strategy", "tissue_type",
        ]
        sample_rows = []
        for row in samples:
            sample_rows.append({
                "study_accession": row.get("study_accession"),
                "sample_accession": row.get("sample_accession"),
                "sample_name": row.get("sample_name"),
                "sample_description": row.get("sample_description"),
                "individual_accession": row.get("individual_accession"),
                "individual_name": row.get("individual_name"),
                "biospecimen_anatomic_site": row.get("biospecimen_anatomic_site"),
                "sample_type": row.get("tumor_descriptor") or row.get("specimen_type"),
                "specimen_types": row.get("specimen_type") or row.get("specimen_types"),
                "strategy": row.get("experimental_strategy") or row.get("strategy"),
                "tissue_type": row.get("tissue_type"),
            })

        t1_entities = []
        t11_rows = []
        for row in t1_rows:
            t1_id = row.get("T1_id")
            if not t1_id:
                continue
            sample_accession = row.get("sample_accession") or t1_sample.get(t1_id) or ""
            sample = sample_by_id.get(sample_accession, {})
            studies_for_t1 = sorted(t1_study.get(t1_id) or set())
            study_accession = (
                studies_for_t1[0]
                if studies_for_t1
                else sample.get("study_accession")
                or sorted(individual_studies.get(row.get("individual_accession")) or set())[0]
                if individual_studies.get(row.get("individual_accession"))
                else ""
            )
            modals = sorted(t1_modal.get(t1_id) or set())
            strategy = MODAL_TO_STRATEGY.get(modals[0], "") if modals else sample.get("strategy") or ""
            file_name = row.get("file_name") or t1_id
            t1_entities.append({
                "studyAccession": study_accession,
                "individualAccession": row.get("individual_accession"),
                "individualName": row.get("individual_name") or sample.get("individual_name"),
                "sampleAccession": sample_accession,
                "sampleDescription": sample.get("sample_description"),
                "sampleName": row.get("sample_name") or sample.get("sample_name"),
                "gender": row.get("gender") or "",
                "runAccession": row.get("run_accession"),
                "dataName": t1_id,
                "experimentAccession": row.get("experiment_accession"),
                "platform": row.get("platform"),
                "strategy": strategy,
            })
            t11_rows.append({
                "study_accession": study_accession,
                "sample_accession": sample_accession,
                "run_accession": row.get("run_accession"),
                "data_type": strategy,
                "Read Pair": infer_read_pair(file_name),
                "files": t1_id,
                "file_name": file_name,
                "format": row.get("format"),
                "file_path": row.get("file_path") or file_name,
                "file_description": sample.get("sample_description"),
                "Experiment": row.get("experiment_accession"),
                "Platform": row.get("platform"),
                "data_level": t1_level.get(t1_id) or row.get("data_level"),
                "pipeline-id": "",
                "parameter": "",
            })

        t2_parent = defaultdict(list)
        for row in t2_parent_raw:
            if row.get("T2_id") and row.get("T1_id"):
                t2_parent[row["T2_id"]].append(row)
        t2_entities = []
        for row in t2_rows:
            t2_id = row.get("T2_id")
            parents = t2_parent.get(t2_id) or []
            first_parent = t1_by_id.get(parents[0].get("T1_id")) if parents else {}
            t2_entities.append({
                "study_accession": row.get("study_accession"),
                "t2_id": t2_id,
                "files": row.get("sub_file_name") or row.get("file_name") or t2_id,
                "file_type": row.get("file_name"),
                "format": row.get("format"),
                "size": row.get("size"),
                "data_level": row.get("data_level"),
                "size_bytes": "",
                "file_path": row.get("file_path"),
                "strategy": row.get("strategy"),
                "run_accession": row.get("run_accession") or (parents[0].get("run_accession") if parents else ""),
                "semantic_format": rename_format(row.get("semantic_format")),
                "sample_accession": first_parent.get("sample_accession"),
                "individual_accession": first_parent.get("individual_accession"),
            })

        # Entity and legacy mirror tables used by the existing matcher.
        write_csv(output_csv / "entities/project.csv", project_fields, project_rows)
        write_csv(output_csv / "entities/study.csv", study_fields, study_rows)
        individual_fields = list(individuals[0]) if individuals else ["project_accession", "individual_accession", "study_accession"]
        write_csv(output_csv / "entities/individual.csv", individual_fields, individuals)
        write_csv(output_csv / "entities/sample.csv", sample_fields, sample_rows)
        write_csv(output_csv / "entities/T1.csv", T1_HEADERS, t1_entities)
        write_csv(output_csv / "entities/T2.csv", T2_HEADERS, t2_entities)
        write_csv(output_csv / "T11.csv", T11_HEADERS, t11_rows)

        # Keep the older flat mirrors present for callers that still inspect them.
        write_csv(output_csv / "project.csv", project_fields, project_rows)
        write_csv(output_csv / "study.csv", study_fields, study_rows)
        write_csv(output_csv / "sample.csv", sample_fields, sample_rows)

        # Preserve the existing data reference tables and union in 7.28 data vocab.
        for name in ("cohort_subclass.csv", "cohorts.csv"):
            shutil.copy2(base_csv / "reference" / name, output_csv / "reference" / name)
        _, base_levels = read_csv(base_csv / "reference/data_level.csv")
        _, source_levels = read_csv(source / "reference/data_level.csv")
        write_csv(output_csv / "reference/data_level.csv", ["level", "name", "description"], dedupe_exact(base_levels + source_levels, ["level", "name", "description"]))
        _, base_formats = read_csv(base_csv / "reference/formats.csv")
        _, source_formats = read_csv(source / "reference/formats.csv")
        format_rows = [
            {"语义格式": rename_format(row.get("语义格式")), "description": row.get("description")}
            for row in base_formats + source_formats
        ]
        write_csv(output_csv / "reference/formats.csv", ["语义格式", "description"], dedupe_exact(format_rows, ["语义格式", "description"]))
        _, base_modals = read_csv(base_csv / "reference/multimodal.csv")
        _, source_modals = read_csv(source / "reference/multimodal.csv")
        write_csv(output_csv / "reference/multimodal.csv", ["modal", "description"], dedupe_exact(base_modals + source_modals, ["modal", "description"]))

        # Core data relations in the legacy MCP shape.
        study_project = dedupe_exact(
            [{"study_accession": row.get("study_accession"), "project_accession": row.get("project_accession")} for row in study_project_raw],
            ["study_accession", "project_accession"],
        )
        individual_study = dedupe_exact(
            [{"individual_accession": row.get("individual_accession"), "study_accession": row.get("study_accession")} for row in individual_study_raw],
            ["individual_accession", "study_accession"],
        )
        sample_individual = dedupe_exact(
            [{"sample_accession": row.get("sample_accession"), "individual_accession": row.get("individual_accession")} for row in sample_individual_raw],
            ["sample_accession", "individual_accession"],
        )
        t1_keys = set(t1_by_id)
        t2_keys = set(t2_by_id)
        study_keys = {row.get("study_accession") for row in study_rows}
        sample_keys = {row.get("sample_accession") for row in sample_rows}
        run_sample = dedupe_exact(
            [{"run_accession": row.get("run_accession"), "sample_accession": row.get("sample_accession")} for row in t1_rows if row.get("run_accession") and row.get("sample_accession")],
            ["run_accession", "sample_accession"],
        )
        write_csv(output_csv / "relations/study_in_project.csv", ["study_accession", "project_accession"], study_project)
        write_csv(output_csv / "relations/individual_in_study.csv", ["individual_accession", "study_accession"], individual_study)
        write_csv(output_csv / "relations/sample_in_individual.csv", ["sample_accession", "individual_accession"], sample_individual)
        write_csv(output_csv / "relations/run_in_sample.csv", ["run_accession", "sample_accession"], run_sample)

        t1_study_rows = dedupe_exact(
            [{"files": row.get("T1_id"), "study_accession": row.get("study_accession")} for row in t1_study_raw if row.get("T1_id") in t1_keys and row.get("study_accession") in study_keys],
            ["files", "study_accession"],
        )
        t1_sample_rows = dedupe_exact(
            [{"files": row.get("T1_id"), "sample_accession": row.get("sample_accession")} for row in t1_sample_raw if row.get("T1_id") in t1_keys and row.get("sample_accession") in sample_keys],
            ["files", "sample_accession"],
        )
        t1_run_rows = dedupe_exact(
            [{"files": row.get("T1_id"), "run_accession": t1_by_id.get(row.get("T1_id"), {}).get("run_accession")} for row in t1_rows if row.get("T1_id") in t1_keys and t1_by_id.get(row.get("T1_id"), {}).get("run_accession")],
            ["files", "run_accession"],
        )
        t1_format_rows = dedupe_exact(
            [{"files": row.get("T1_id"), "format": rename_format(row.get("semantic_format") or row.get("format"))} for row in t1_format_raw if row.get("T1_id") in t1_keys and (row.get("semantic_format") or row.get("format"))],
            ["files", "format"],
        )
        t1_level_rows = dedupe_exact(
            [{"files": row.get("T1_id"), "data_level": row.get("data_level")} for row in t1_level_raw if row.get("T1_id") in t1_keys and row.get("data_level")],
            ["files", "data_level"],
        )
        t1_modal_rows = dedupe_exact(
            [{"files": row.get("T1_id"), "modal": row.get("modal")} for row in t1_modal_raw if row.get("T1_id") in t1_keys and row.get("modal")],
            ["files", "modal"],
        )
        write_csv(output_csv / "relations/T1_in_study.csv", ["files", "study_accession"], t1_study_rows)
        write_csv(output_csv / "relations/T1_in_sample.csv", ["files", "sample_accession"], t1_sample_rows)
        write_csv(output_csv / "relations/T1_in_run.csv", ["files", "run_accession"], t1_run_rows)
        write_csv(output_csv / "relations/T1_in_format.csv", ["files", "format"], t1_format_rows)
        write_csv(output_csv / "relations/T1_in_level.csv", ["files", "data_level"], t1_level_rows)
        write_csv(output_csv / "relations/T1_in_modal.csv", ["files", "modal"], t1_modal_rows)

        t2_study_rows = dedupe_exact(
            [{"t2_id": row.get("T2_id"), "study_accession": row.get("study_accession")} for row in t2_study_raw if row.get("T2_id") in t2_keys and row.get("study_accession") in study_keys],
            ["t2_id", "study_accession"],
        )
        t2_format_rows = dedupe_exact(
            [{"t2_id": row.get("T2_id"), "format": rename_format(row.get("semantic_format") or row.get("format"))} for row in t2_format_raw if row.get("T2_id") in t2_keys and (row.get("semantic_format") or row.get("format"))],
            ["t2_id", "format"],
        )
        t2_level_rows = dedupe_exact(
            [{"t2_id": row.get("T2_id"), "level": row.get("data_level")} for row in t2_level_raw if row.get("T2_id") in t2_keys and row.get("data_level")],
            ["t2_id", "level"],
        )
        t2_modal_rows = dedupe_exact(
            [{"t2_id": row.get("T2_id"), "modal": row.get("modal")} for row in t2_modal_raw if row.get("T2_id") in t2_keys and row.get("modal")],
            ["t2_id", "modal"],
        )
        t2_parent_rows = dedupe_exact(
            [{"t2_id": row.get("T2_id"), "run_accession": row.get("run_accession"), "files": row.get("T1_id")} for row in t2_parent_raw if row.get("T2_id") in t2_keys and row.get("T1_id") in t1_keys],
            ["t2_id", "run_accession", "files"],
        )
        write_csv(output_csv / "relations/T2_in_study.csv", ["t2_id", "study_accession"], t2_study_rows)
        write_csv(output_csv / "relations/T2_in_format.csv", ["t2_id", "format"], t2_format_rows)
        write_csv(output_csv / "relations/T2_in_level.csv", ["t2_id", "level"], t2_level_rows)
        write_csv(output_csv / "relations/T2_in_modal.csv", ["t2_id", "modal"], t2_modal_rows)
        write_csv(output_csv / "relations/T2_generated_from_T1.csv", ["t2_id", "run_accession", "files"], t2_parent_rows)

    csv_files = sorted(output_csv.rglob("*.csv"))
    manifest = {
        "schema_version": "mcp-update728-adapter/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_zip": str(source_zip),
        "source_sha256": sha256(source_zip),
        "output_csv": str(output_csv),
        "tool_catalog_source": str(base_csv),
        "csv_count": len(csv_files),
        "row_counts": {
            path.relative_to(output_csv).as_posix(): sum(1 for _ in path.open(encoding="utf-8")) - 1
            for path in csv_files
        },
        "tool_file_sha256": {
            relative: sha256(output_csv / relative)
            for relative in TOOL_CATALOG_FILES
        },
        "policies": {
            "source_overwritten": False,
            "tool_catalog_reused": True,
            "duplicate_t1_rows_deduplicated": True,
            "duplicate_individual_accessions_first_row_retained": True,
            "semantic_format_normalized": True,
        },
    }
    manifest_path = output_csv.parent / "compatibility_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/update728/csv"))
    parser.add_argument("--base-csv-dir", type=Path, default=Path("data/csv"))
    args = parser.parse_args()
    manifest = normalize(args.source_zip.resolve(), args.output_dir.resolve(), args.base_csv_dir.resolve())
    print(json.dumps({
        "output_dir": manifest["output_csv"],
        "manifest": str(Path(manifest["output_csv"]).parent / "compatibility_manifest.json"),
        "csv_count": manifest["csv_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
