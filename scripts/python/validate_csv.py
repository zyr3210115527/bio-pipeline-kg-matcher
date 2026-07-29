#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path
from collections import Counter


def load_csv(file_path: Path):
    """
    自动识别 CSV 编码并返回表头和行数据
    """
    # Try utf-8-sig first so a BOM is not retained in the first header name.
    encodings_to_try = ["utf-8-sig", "utf-8", "gbk", "gb2312", "latin1"]
    last_error = None

    for encoding in encodings_to_try:
        try:
            with file_path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                headers = reader.fieldnames or []
            return headers, rows
        except UnicodeDecodeError as e:
            last_error = e
            continue
    raise UnicodeDecodeError(f"Unable to decode {file_path}", b"", 0, 1, str(last_error))


def require_file(file_path: Path, errors: list):
    if not file_path.exists():
        errors.append(f"[MISSING FILE] {file_path}")


def check_required_columns(file_path: Path, headers: list, required_cols: list, errors: list):
    missing = [c for c in required_cols if c not in headers]
    if missing:
        errors.append(f"[MISSING COLUMNS] {file_path.name}: missing {missing}")


def check_non_empty_unique(file_path: Path, rows: list, column: str, errors: list):
    values = []
    for i, row in enumerate(rows, start=2):
        value = (row.get(column) or "").strip()
        if not value:
            errors.append(f"[EMPTY VALUE] {file_path.name}:{i} column '{column}' is empty")
        values.append(value)

    counter = Counter(values)
    duplicates = [v for v, c in counter.items() if c > 1 and v != ""]
    if duplicates:
        errors.append(f"[DUPLICATE VALUES] {file_path.name}: duplicated values in '{column}': {duplicates}")


def check_non_empty(file_path: Path, rows: list, columns: list, errors: list):
    for i, row in enumerate(rows, start=2):
        for col in columns:
            value = (row.get(col) or "").strip()
            if not value:
                errors.append(f"[EMPTY VALUE] {file_path.name}:{i} column '{col}' is empty")


def build_value_set(rows: list, key: str):
    return {(row.get(key) or "").strip().lower() for row in rows if (row.get(key) or "").strip()}


def check_fk(file_path: Path, rows: list, fk_col: str, valid_set: set, errors: list):
    for i, row in enumerate(rows, start=2):
        value = (row.get(fk_col) or "").strip().lower()
        if value and value not in valid_set:
            errors.append(f"[FK NOT FOUND] {file_path.name}:{i} '{fk_col}'='{value}' not found")


def print_report_and_exit(errors):
    print("CSV validation failed:")
    for err in errors:
        print(f"  - {err}")
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="Validate CSV files for biomed-kg.")
    parser.add_argument("--project-root", required=True, help="Project root path")
    parser.add_argument(
        "--csv-dir",
        help="CSV directory to validate; defaults to <project-root>/data/csv",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    csv_root = Path(args.csv_dir).resolve() if args.csv_dir else project_root / "data" / "csv"
    ref_dir = csv_root / "reference"
    ent_dir = csv_root / "entities"
    rel_dir = csv_root / "relations"
    catalog_dir = csv_root / "catalog"

    errors = []

    # --------------------------------------------
    # 1. 配置各文件对应的真实表头 (完全对齐CSV数据)
    # --------------------------------------------
    reference_files = {
        "cohorts.csv": ["status", "description"],
        "cohort_subclass.csv": ["child", "parent"],
        "data_level.csv": ["level", "name", "description"],
        "formats.csv": ["语义格式", "description"],
        "function.csv": ["function", "description"], # 注意是function.csv
        "multimodal.csv": ["modal", "description"],
        "tool_types.csv": ["type", "description"],
        
    }

    entity_files = {
        "individual.csv": ["individual_accession", "study_accession", "project_accession"],
        "project.csv": ["project_accession", "project_name"],
        "sample.csv": ["sample_accession", "study_accession", "individual_accession"],
        "study.csv": ["study_accession", "title"],
        "T1.csv": ["runAccession", "dataName", "studyAccession"], # 驼峰命名
        "T2.csv": ["t2_id", "files", "study_accession"],
        "tool.csv": ["tool_id", "tool_name", "function"]
    }

    relation_files = {
        "individual_in_study.csv": ["individual_accession", "study_accession"],
        "run_in_sample.csv": ["run_accession", "sample_accession"],
        "sample_in_individual.csv": ["sample_accession", "individual_accession"],
        "study_in_project.csv": ["study_accession", "project_accession"],
        "T1_in_format.csv": ["files", "format"],
        "T1_in_level.csv": ["files", "data_level"],
        "T1_in_run.csv": ["files", "run_accession"],
        "T1_in_study.csv": ["files", "study_accession"],
        "T2_in_format.csv": ["t2_id", "format"],
        "T2_in_level.csv": ["t2_id", "level"],
        "T2_in_study.csv": ["t2_id", "study_accession"],
        "tool_has_function.csv": ["tool_id", "function"],
        "tool_input_format.csv": ["tool_id", "语义输入格式"],
        "tool_output_format.csv": ["tool_id", "语义输出格式"],
        "tool_relationship.csv": ["tool_id", "next_tool_id", "kind", "output", "input"]
    }

    # --------------------------------------------
    # 2. 加载与校验 (Existence & Required Columns)
    # --------------------------------------------
    loaded = {}
    all_configs = {ref_dir: reference_files, ent_dir: entity_files, rel_dir: relation_files}
    
    for folder, config in all_configs.items():
        for filename, cols in config.items():
            path = folder / filename
            require_file(path, errors)
            if path.exists():
                headers, rows = load_csv(path)
                loaded[filename] = (headers, rows)
                check_required_columns(path, headers, cols, errors)

    if errors: print_report_and_exit(errors)

    catalog_files = {
        "catalog_tool_id.csv": (
            catalog_dir / "tool_id.csv",
            [
                "identity", "labels", "catalog_id", "tool_id", "tool_kind", "tool_name",
                "input_variants_json", "input_aliases_json", "exactly_one_variant",
            ],
        ),
        "catalog_io_slot.csv": (
            catalog_dir / "io_slot.csv",
            [
                "identity", "labels", "direction", "required", "slot_id", "slot_name",
                "tool_id", "artifact", "wdl_type", "dimension", "dimension_value",
                "variant", "variant_alias_for",
            ],
        ),
        "catalog_artifact_type.csv": (
            catalog_dir / "artifact_type.csv",
            ["identity", "labels", "artifact_type"],
        ),
        "catalog_function.csv": (
            catalog_dir / "function.csv",
            ["identity", "labels", "function"],
        ),
        "catalog_format.csv": (
            catalog_dir / "format.csv",
            ["identity", "labels", "format"],
        ),
        "catalog_relationships.csv": (
            catalog_dir / "relationships.csv",
            ["type", "start", "end", "properties_json"],
        ),
    }
    catalog_loaded = {}
    for key, (path, columns) in catalog_files.items():
        require_file(path, errors)
        if path.exists():
            headers, rows = load_csv(path)
            catalog_loaded[key] = (headers, rows)
            check_required_columns(path, headers, columns, errors)
    if errors:
        print_report_and_exit(errors)

    # --------------------------------------------
    # 3. 唯一性检查 (Uniqueness)
    # --------------------------------------------
    check_non_empty_unique(ent_dir / "individual.csv", loaded["individual.csv"][1], "individual_accession", errors)
    check_non_empty_unique(ent_dir / "project.csv", loaded["project.csv"][1], "project_accession", errors)
    check_non_empty_unique(ent_dir / "study.csv", loaded["study.csv"][1], "study_accession", errors)
    # T1 is allowed to be outside the currently loaded Study/Sample scope.
    # Such rows remain searchable by file metadata, but are not eligible for
    # Study-constrained matching until an IN_STUDY edge is present.
    check_non_empty(ent_dir / "T1.csv", loaded["T1.csv"][1], ["runAccession"], errors)
    check_non_empty_unique(ent_dir / "T1.csv", loaded["T1.csv"][1], "dataName", errors)
    check_non_empty_unique(ent_dir / "T2.csv", loaded["T2.csv"][1], "t2_id", errors) # 这里必须是t2_id
    check_non_empty_unique(ent_dir / "tool.csv", loaded["tool.csv"][1], "tool_id", errors)
    catalog_identities = set()
    for key, (path, _columns) in catalog_files.items():
        if key == "catalog_relationships.csv":
            continue
        rows = catalog_loaded[key][1]
        check_non_empty_unique(path, rows, "identity", errors)
        check_non_empty(path, rows, ["labels"], errors)
        for row in rows:
            identity = (row.get("identity") or "").strip()
            if identity in catalog_identities:
                errors.append(f"[DUPLICATE CATALOG IDENTITY] {identity}")
            catalog_identities.add(identity)

    catalog_tools = {
        (row.get("tool_id") or "").strip()
        for row in catalog_loaded["catalog_tool_id.csv"][1]
    }
    slots_by_tool = {}
    slot_names_by_tool = {}
    for i, row in enumerate(catalog_loaded["catalog_io_slot.csv"][1], start=2):
        tool_id = (row.get("tool_id") or "").strip()
        slot_id = (row.get("slot_id") or "").strip()
        slot_name = (row.get("slot_name") or "").strip()
        if tool_id not in catalog_tools:
            errors.append(f"[CATALOG SLOT TOOL FK] io_slot.csv:{i} unknown tool_id")
        slots_by_tool.setdefault(tool_id, set()).add(slot_id)
        direction = (row.get("direction") or "").strip()
        direction_key = f"{tool_id}:{direction}"
        if slot_name in slot_names_by_tool.setdefault(direction_key, set()):
            errors.append(
                f"[DUPLICATE CATALOG SLOT NAME] io_slot.csv:{i} {tool_id}.{direction}.{slot_name}"
            )
        slot_names_by_tool[direction_key].add(slot_name)
        if direction not in {"input", "output"}:
            errors.append(f"[CATALOG SLOT DIRECTION] io_slot.csv:{i}")
        if (row.get("required") or "").strip().lower() not in {"true", "false"}:
            errors.append(f"[CATALOG SLOT REQUIRED] io_slot.csv:{i}")
        dimension = (row.get("dimension") or "").strip()
        dimension_value = (row.get("dimension_value") or "").strip()
        if dimension not in {"", "mate", "sample_role"}:
            errors.append(f"[CATALOG SLOT DIMENSION] io_slot.csv:{i} {dimension}")
        if dimension == "mate" and dimension_value not in {"r1", "r2"}:
            errors.append(f"[CATALOG SLOT DIMENSION VALUE] io_slot.csv:{i} mate={dimension_value}")
        if dimension == "sample_role" and dimension_value not in {"tumor", "normal", "inherit"}:
            errors.append(
                f"[CATALOG SLOT DIMENSION VALUE] io_slot.csv:{i} sample_role={dimension_value}"
            )
        if not dimension and dimension_value:
            errors.append(f"[CATALOG SLOT ORPHAN DIMENSION VALUE] io_slot.csv:{i}")

    for i, row in enumerate(catalog_loaded["catalog_tool_id.csv"][1], start=2):
        tool_id = (row.get("tool_id") or "").strip()
        exactly_one = (row.get("exactly_one_variant") or "").strip().lower()
        if exactly_one not in {"", "true", "false"}:
            errors.append(f"[CATALOG VARIANT BOOLEAN] tool_id.csv:{i} {exactly_one}")
        try:
            variants = json.loads(row.get("input_variants_json") or "{}")
            aliases = json.loads(row.get("input_aliases_json") or "{}")
            if not isinstance(variants, dict) or not all(
                isinstance(name, str)
                and isinstance(names, list)
                and names
                and all(isinstance(slot, str) and slot for slot in names)
                for name, names in variants.items()
            ):
                raise ValueError("input_variants_json must map names to non-empty slot-name arrays")
            if not isinstance(aliases, dict) or not all(
                isinstance(source, str) and source and isinstance(target, str) and target
                for source, target in aliases.items()
            ):
                raise ValueError("input_aliases_json must map non-empty slot names")
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"[CATALOG VARIANT JSON] tool_id.csv:{i} {exc}")
            continue
        input_names = {
            (slot.get("slot_name") or "").strip()
            for slot in catalog_loaded["catalog_io_slot.csv"][1]
            if (slot.get("tool_id") or "").strip() == tool_id
            and (slot.get("direction") or "").strip() == "input"
        }
        referenced = {slot for names in variants.values() for slot in names}
        unknown = sorted((referenced | set(aliases) | set(aliases.values())) - input_names)
        if unknown:
            errors.append(f"[CATALOG VARIANT SLOT FK] tool_id.csv:{i} {unknown}")
        if exactly_one == "true" and not variants:
            errors.append(f"[CATALOG VARIANT EMPTY] tool_id.csv:{i}")
        declared_variants = set(variants)
        for slot_line, slot in enumerate(catalog_loaded["catalog_io_slot.csv"][1], start=2):
            if (slot.get("tool_id") or "").strip() != tool_id:
                continue
            slot_variants = {
                value.strip() for value in (slot.get("variant") or "").split("|") if value.strip()
            }
            invalid = sorted(slot_variants - declared_variants)
            if invalid:
                errors.append(
                    f"[CATALOG SLOT VARIANT FK] io_slot.csv:{slot_line} {invalid}"
                )

    allowed_catalog_relationships = {
        "ALLOW_FORMAT", "HAS_FUNCTION", "HAS_INPUT_SLOT", "HAS_OUTPUT_SLOT",
        "HAS_STEP", "INPUT", "MANIFEST_AS", "OUTPUT", "PRODUCES", "REQUIRES",
    }
    for i, row in enumerate(catalog_loaded["catalog_relationships.csv"][1], start=2):
        rel_type = (row.get("type") or "").strip()
        start = (row.get("start") or "").strip()
        end = (row.get("end") or "").strip()
        if rel_type not in allowed_catalog_relationships:
            errors.append(f"[CATALOG REL TYPE] relationships.csv:{i} {rel_type}")
        if start not in catalog_identities or end not in catalog_identities:
            errors.append(f"[CATALOG REL FK] relationships.csv:{i} {start} -> {end}")
        try:
            properties = json.loads(row.get("properties_json") or "")
            if not isinstance(properties, dict):
                raise ValueError("not an object")
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"[CATALOG REL PROPERTIES] relationships.csv:{i} {exc}")

    # --------------------------------------------
    # 4. 构建外键校验集合
    # --------------------------------------------
    tool_ids = build_value_set(loaded["tool.csv"][1], "tool_id")
    study_accessions = build_value_set(loaded["study.csv"][1], "study_accession")
    individual_accessions = build_value_set(loaded["individual.csv"][1], "individual_accession")
    project_accessions = build_value_set(loaded["project.csv"][1], "project_accession")
    sample_accessions = build_value_set(loaded["sample.csv"][1], "sample_accession")
    run_accessions = build_value_set(loaded["T1.csv"][1], "runAccession")
    t1_data_names = build_value_set(loaded["T1.csv"][1], "dataName")
    t2_ids = build_value_set(loaded["T2.csv"][1], "t2_id")
    
    format_names = build_value_set(loaded["formats.csv"][1], "语义格式")
    function_names = build_value_set(loaded["function.csv"][1], "function")
    level_values = build_value_set(loaded["data_level.csv"][1], "level")
    cohort_statuses = build_value_set(loaded["cohorts.csv"][1], "status")

    # --------------------------------------------
    # 5. 关系表外键检查
    # --------------------------------------------
    # T1 系列 (通过 dataName 关联)
    check_fk(rel_dir / "T1_in_format.csv", loaded["T1_in_format.csv"][1], "files", t1_data_names, errors)
    check_fk(rel_dir / "T1_in_format.csv", loaded["T1_in_format.csv"][1], "format", format_names, errors)
    check_fk(rel_dir / "T1_in_level.csv", loaded["T1_in_level.csv"][1], "files", t1_data_names, errors)
    check_fk(rel_dir / "T1_in_level.csv", loaded["T1_in_level.csv"][1], "data_level", level_values, errors)
    check_fk(rel_dir / "T1_in_run.csv", loaded["T1_in_run.csv"][1], "files", t1_data_names, errors)
    check_fk(rel_dir / "T1_in_run.csv", loaded["T1_in_run.csv"][1], "run_accession", run_accessions, errors)
    check_fk(rel_dir / "T1_in_study.csv", loaded["T1_in_study.csv"][1], "files", t1_data_names, errors)
    check_fk(rel_dir / "T1_in_study.csv", loaded["T1_in_study.csv"][1], "study_accession", study_accessions, errors)

    # T2 系列 (通过 t2_id 关联)
    check_fk(rel_dir / "T2_in_format.csv", loaded["T2_in_format.csv"][1], "t2_id", t2_ids, errors)
    check_fk(rel_dir / "T2_in_format.csv", loaded["T2_in_format.csv"][1], "format", format_names, errors)
    check_fk(rel_dir / "T2_in_level.csv", loaded["T2_in_level.csv"][1], "t2_id", t2_ids, errors)
    check_fk(rel_dir / "T2_in_level.csv", loaded["T2_in_level.csv"][1], "level", level_values, errors)
    check_fk(rel_dir / "T2_in_study.csv", loaded["T2_in_study.csv"][1], "t2_id", t2_ids, errors)
    check_fk(rel_dir / "T2_in_study.csv", loaded["T2_in_study.csv"][1], "study_accession", study_accessions, errors)

    # 工具系列
    check_fk(rel_dir / "tool_has_function.csv", loaded["tool_has_function.csv"][1], "tool_id", tool_ids, errors)
    check_fk(rel_dir / "tool_has_function.csv", loaded["tool_has_function.csv"][1], "function", function_names, errors)
    check_fk(rel_dir / "tool_input_format.csv", loaded["tool_input_format.csv"][1], "tool_id", tool_ids, errors)
    check_fk(rel_dir / "tool_input_format.csv", loaded["tool_input_format.csv"][1], "语义输入格式", format_names, errors)
    check_fk(rel_dir / "tool_output_format.csv", loaded["tool_output_format.csv"][1], "tool_id", tool_ids, errors)
    check_fk(rel_dir / "tool_output_format.csv", loaded["tool_output_format.csv"][1], "语义输出格式", format_names, errors)
    check_fk(rel_dir / "tool_relationship.csv", loaded["tool_relationship.csv"][1], "tool_id", tool_ids, errors)
    check_fk(rel_dir / "tool_relationship.csv", loaded["tool_relationship.csv"][1], "next_tool_id", tool_ids, errors)
    runtime_by_catalog_id = {
        (row.get("catalog_id") or "").strip().lower(): (row.get("tool_id") or "").strip()
        for row in catalog_loaded["catalog_tool_id.csv"][1]
    }
    seen_next = set()
    input_names_by_tool = {}
    output_names_by_tool = {}
    for slot in catalog_loaded["catalog_io_slot.csv"][1]:
        target = input_names_by_tool if (slot.get("direction") or "").strip() == "input" else output_names_by_tool
        target.setdefault((slot.get("tool_id") or "").strip(), set()).add(
            (slot.get("slot_name") or "").strip()
        )
    for i, row in enumerate(loaded["tool_relationship.csv"][1], start=2):
        kind = (row.get("kind") or "").strip()
        output = (row.get("output") or "").strip()
        input_name = (row.get("input") or "").strip()
        source_tool = runtime_by_catalog_id.get((row.get("tool_id") or "").strip().lower(), "")
        target_tool = runtime_by_catalog_id.get((row.get("next_tool_id") or "").strip().lower(), "")
        if kind not in {"data", "order"}:
            errors.append(f"[NEXT KIND] tool_relationship.csv:{i} {kind}")
        if kind == "data":
            if not output or not input_name:
                errors.append(f"[NEXT DATA FOUR-TUPLE] tool_relationship.csv:{i}")
            if output not in output_names_by_tool.get(source_tool, set()):
                errors.append(
                    f"[NEXT OUTPUT SLOT FK] tool_relationship.csv:{i} {source_tool}.{output}"
                )
            if input_name not in input_names_by_tool.get(target_tool, set()):
                errors.append(
                    f"[NEXT INPUT SLOT FK] tool_relationship.csv:{i} {target_tool}.{input_name}"
                )
        elif output or input_name:
            errors.append(f"[NEXT ORDER PAYLOAD] tool_relationship.csv:{i}")
        key = (source_tool, target_tool, kind, output, input_name)
        if key in seen_next:
            errors.append(f"[DUPLICATE NEXT FOUR-TUPLE] tool_relationship.csv:{i} {key}")
        seen_next.add(key)

    # 基础层级
    check_non_empty(rel_dir / "run_in_sample.csv", loaded["run_in_sample.csv"][1], ["run_accession"], errors)
    check_non_empty(rel_dir / "run_in_sample.csv", loaded["run_in_sample.csv"][1], ["sample_accession"], errors)
    check_non_empty(rel_dir / "individual_in_study.csv", loaded["individual_in_study.csv"][1], ["individual_accession"], errors)
    check_fk(rel_dir / "individual_in_study.csv", loaded["individual_in_study.csv"][1], "study_accession", study_accessions, errors)
    check_non_empty(rel_dir / "sample_in_individual.csv", loaded["sample_in_individual.csv"][1], ["sample_accession"], errors)
    check_non_empty(rel_dir / "sample_in_individual.csv", loaded["sample_in_individual.csv"][1], ["individual_accession"], errors)
    check_fk(rel_dir / "study_in_project.csv", loaded["study_in_project.csv"][1], "study_accession", study_accessions, errors)
    check_fk(rel_dir / "study_in_project.csv", loaded["study_in_project.csv"][1], "project_accession", project_accessions, errors)
    check_fk(rel_dir / "cohort_subclass.csv", loaded["cohort_subclass.csv"][1], "child", cohort_statuses, errors)
    check_fk(rel_dir / "cohort_subclass.csv", loaded["cohort_subclass.csv"][1], "parent", cohort_statuses, errors)

    # --------------------------------------------
    # 6. 报告结果
    # --------------------------------------------
    if errors:
        print_report_and_exit(errors)
    else:
        print("CSV validation passed. All files, columns, and relations are consistent.")

if __name__ == "__main__":
    main()
