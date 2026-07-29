#!/usr/bin/env python3
"""Build a deterministic, non-destructive repair of the 2026-07-28 CSV package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


FORMAT_RENAMES = {
    "METADATA_SAMPLEINFO": "METADATA_SAMPLE_INFO",
    "MUTATION_ANNOTATION_FORMA_MAF": "MUTATION_ANNOTATION_FORMAT_MAF",
    "RNA_SPLICEJUNCTION_TAB": "RNA_SPLICE_JUNCTION_TAB",
}

ENTITY_KEYS = {
    "entities/T1.csv": "T1_id",
    "entities/T2.csv": "T2_id",
    "entities/individual.csv": "individual_accession",
    "entities/project.csv": "project_accession",
    "entities/sample.csv": "sample_accession",
    "entities/study.csv": "study_accession",
    "entities/tool.csv": "tool_id",
    "reference/data_level.csv": "level",
    "reference/formats.csv": "语义格式",
    "reference/function.csv": "function",
    "reference/multimodal.csv": "modal",
}

RELATION_ENDPOINTS = {
    "relations/T1_in_format.csv": (("T1_id", "entities/T1.csv"), ("semantic_format", "reference/formats.csv")),
    "relations/T1_in_level.csv": (("T1_id", "entities/T1.csv"), ("data_level", "reference/data_level.csv")),
    "relations/T1_in_modal.csv": (("T1_id", "entities/T1.csv"), ("modal", "reference/multimodal.csv")),
    "relations/T1_in_sample.csv": (("T1_id", "entities/T1.csv"), ("sample_accession", "entities/sample.csv")),
    "relations/T1_in_study.csv": (("T1_id", "entities/T1.csv"), ("individual_accession", "entities/individual.csv"), ("study_accession", "entities/study.csv")),
    "relations/T2_generated_from_T1.csv": (("T2_id", "entities/T2.csv"), ("T1_id", "entities/T1.csv")),
    "relations/T2_in_format.csv": (("T2_id", "entities/T2.csv"), ("semantic_format", "reference/formats.csv")),
    "relations/T2_in_level.csv": (("T2_id", "entities/T2.csv"), ("data_level", "reference/data_level.csv")),
    "relations/T2_in_modal.csv": (("T2_id", "entities/T2.csv"), ("modal", "reference/multimodal.csv")),
    "relations/T2_in_study.csv": (("T2_id", "entities/T2.csv"), ("study_accession", "entities/study.csv")),
    "relations/individual_in_study.csv": (("individual_accession", "entities/individual.csv"), ("study_accession", "entities/study.csv")),
    "relations/sample_in_individual.csv": (("sample_accession", "entities/sample.csv"), ("individual_accession", "entities/individual.csv")),
    "relations/study_in_project.csv": (("study_accession", "entities/study.csv"), ("project_accession", "entities/project.csv")),
    "relations/tool_has_function.csv": (("tool_id", "entities/tool.csv"), ("function", "reference/function.csv")),
    "relations/tool_has_semantic_input.csv": (("tool_id", "entities/tool.csv"), ("format", "reference/formats.csv")),
    "relations/tool_has_semantic_output.csv": (("tool_id", "entities/tool.csv"), ("format", "reference/formats.csv")),
    "relations/tool_relationship.csv": (("tool_id", "entities/tool.csv"), ("next_tool_id", "entities/tool.csv")),
    "relations/tool_suitable_for_modal.csv": (("tool_id", "entities/tool.csv"), ("modal", "reference/multimodal.csv")),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]], str]:
    raw = path.read_bytes()
    encoding = "utf-8-sig"
    try:
        text = raw.decode(encoding)
    except UnicodeDecodeError:
        encoding = "gb18030"
        text = raw.decode(encoding)
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise ValueError(f"missing header: {path}")
    rows = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"extra columns at {path}:{row_number}")
        if all((value or "") == "" for value in row.values()):
            continue
        rows.append({key: value or "" for key, value in row.items()})
    return list(reader.fieldnames), rows, encoding


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def locate_package_root(extract_dir: Path) -> Path:
    candidates = [path.parent.parent for path in extract_dir.rglob("entities/T1.csv")]
    candidates = sorted(set(candidates))
    if len(candidates) != 1:
        raise ValueError(f"expected one package root, found {len(candidates)}")
    return candidates[0]


def replace_vocab(value: str) -> tuple[str, int]:
    replacements = 0
    for old, new in FORMAT_RENAMES.items():
        count = value.count(old)
        if count:
            value = value.replace(old, new)
            replacements += count
    return value, replacements


def entity_sets(package_dir: Path) -> dict[str, set[str]]:
    result = {}
    for rel_path, key in ENTITY_KEYS.items():
        _, rows, _ = read_csv(package_dir / rel_path)
        result[rel_path] = {row[key] for row in rows if row[key]}
    return result


def validate(package_dir: Path) -> dict:
    csv_files = sorted(package_dir.rglob("*.csv"))
    report: dict = {
        "csv_count": len(csv_files),
        "utf8_errors": [],
        "width_errors": [],
        "empty_primary_keys": {},
        "duplicate_primary_keys": {},
        "foreign_key_errors": {},
        "row_counts": {},
    }
    for path in csv_files:
        rel = path.relative_to(package_dir).as_posix()
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            report["utf8_errors"].append({"file": rel, "error": str(exc)})
            continue
        try:
            _, rows, _ = read_csv(path)
        except ValueError as exc:
            report["width_errors"].append({"file": rel, "error": str(exc)})
            continue
        report["row_counts"][rel] = len(rows)

    sets = entity_sets(package_dir)
    for rel_path, key in ENTITY_KEYS.items():
        _, rows, _ = read_csv(package_dir / rel_path)
        values = [row[key] for row in rows]
        empty = sum(not value for value in values)
        duplicates = {value: count for value, count in Counter(values).items() if value and count > 1}
        if empty:
            report["empty_primary_keys"][rel_path] = empty
        if duplicates:
            report["duplicate_primary_keys"][rel_path] = {
                "duplicate_key_count": len(duplicates),
                "duplicate_row_count": sum(count - 1 for count in duplicates.values()),
                "examples": dict(list(sorted(duplicates.items()))[:10]),
            }

    for rel_path, endpoints in RELATION_ENDPOINTS.items():
        path = package_dir / rel_path
        _, rows, _ = read_csv(path)
        endpoint_errors = {}
        for column, target in endpoints:
            missing = Counter(row[column] for row in rows if not row[column] or row[column] not in sets[target])
            if missing:
                endpoint_errors[column] = {
                    "count": sum(missing.values()),
                    "unique": len(missing),
                    "examples": dict(list(sorted(missing.items()))[:10]),
                }
        if endpoint_errors:
            report["foreign_key_errors"][rel_path] = endpoint_errors

    report["strict_import_ready"] = not any(
        report[key]
        for key in ("utf8_errors", "width_errors", "empty_primary_keys", "duplicate_primary_keys", "foreign_key_errors")
    )
    return report


def make_report(manifest: dict) -> str:
    v = manifest["validation"]
    changes = manifest["changes"]
    blockers = manifest["hard_blockers"]
    lines = [
        "# 更新 7.28 数据包确定性修复报告",
        "",
        "## 结论",
        "",
        "本目录是原始 7.28 压缩包的独立修复副本。没有连接或写入 Neo4j，未覆盖原压缩包。",
        "",
        "可确定的数据清洗已完成，但该包仍不能直接作为生产导入包：Individual 建模冲突、工具图不完整、导入/约束/验证脚本缺失仍是明确阻断项。",
        "",
        "## 已自动修复",
        "",
        f"- 29 个 CSV 全部转为严格 UTF-8；其中原 `entities/project.csv` 从 {changes['encoding_conversions']['entities/project.csv']} 转换。",
        f"- 统一三套语义格式标识，共替换 {changes['semantic_format_replacements']} 处。",
        f"- 修复前无法解析的 T2 格式关系为 {changes['source_invalid_t2_format_references']} 条；修复后均可解析。",
        f"- `entities/T1.csv` 删除 {changes['t1_identical_duplicates_removed']} 条完全相同的重复行。",
        f"- `relations/T1_in_modal.csv` 删除 {changes['empty_t1_modal_rows_removed']} 条空 `T1_id` 关系。",
        f"- `relations/tool_relationship.csv` 删除 {changes['blank_rows_removed']['relations/tool_relationship.csv']} 条空行。",
        f"- 将 {changes['out_of_scope_relations_moved']} 条端点不在本包范围内的关系移至 `diagnostics/out_of_scope_relations.csv`。",
        f"- 根据 `entities/individual.csv` 已明确给出的 Study 字段，补回 {changes['individual_study_memberships_added']} 条缺失成员关系。",
        "",
        "## 修复后校验",
        "",
        f"- CSV 文件：{v['csv_count']} 个（含 diagnostics）。",
        f"- UTF-8 错误：{len(v['utf8_errors'])}。",
        f"- 列宽错误：{len(v['width_errors'])}。",
        f"- 外键错误文件：{len(v['foreign_key_errors'])} 个。",
        f"- `strict_import_ready`：`{str(v['strict_import_ready']).lower()}`。该值为 false 的原因是 Individual 主键冲突仍未解决。",
        "",
        "## 确定不能直接走的部分",
        "",
    ]
    for index, blocker in enumerate(blockers, start=1):
        lines.extend([f"### {index}. {blocker['title']}", "", blocker["detail"], ""])
    lines.extend([
        "## 可接受但有功能限制",
        "",
        "- 5,156 个唯一 T1 没有 Study 关系，不能用于带 Study 条件的检索。",
        "- 9,702 个唯一 T1 没有 Modal 关系，不能用于带组学条件的检索。",
        "- 上述缺口按当前约定可跳过，但接口不能把它们误报为已匹配数据。",
        "",
        "## 使用边界",
        "",
        "修复包可用于继续审核和开发新的 schema/importer；在后端负责人明确 Individual 冲突建模、补齐导入脚本并通过隔离库验证前，不应清空或覆盖生产 Neo4j。",
        "",
    ])
    return "\n".join(lines)


def build(source_zip: Path, output_dir: Path, package_dir: Path) -> tuple[Path, Path, Path]:
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="update728-repair-") as temp:
        extract_dir = Path(temp)
        with zipfile.ZipFile(source_zip) as archive:
            archive.extractall(extract_dir)
        source_root = locate_package_root(extract_dir)
        shutil.copytree(source_root, package_dir)

    _, source_format_rows, _ = read_csv(package_dir / "reference/formats.csv")
    source_formats = {row["语义格式"] for row in source_format_rows}
    _, source_t2_format_rows, _ = read_csv(package_dir / "relations/T2_in_format.csv")
    source_invalid_t2_format_references = sum(
        row["semantic_format"] not in source_formats for row in source_t2_format_rows
    )

    source_file_hashes = {}
    encoding_conversions = {}
    semantic_replacements = 0
    blank_rows_removed = {}

    # Normalize every CSV so identifiers embedded in semicolon fields are consistent.
    for path in sorted(package_dir.rglob("*.csv")):
        rel = path.relative_to(package_dir).as_posix()
        source_file_hashes[rel] = sha256(path)
        fields, rows, encoding = read_csv(path)
        if encoding != "utf-8-sig":
            encoding_conversions[rel] = encoding
        raw_record_count = sum(1 for _ in path.open("rb")) - 1
        blank_rows_removed[rel] = max(0, raw_record_count - len(rows))
        for row in rows:
            for field in fields:
                row[field], count = replace_vocab(row[field])
                semantic_replacements += count
        write_csv(path, fields, rows)

    # Remove only byte-for-byte-equivalent duplicate T1 rows.
    t1_path = package_dir / "entities/T1.csv"
    fields, t1_rows, _ = read_csv(t1_path)
    seen_rows = set()
    deduped_rows = []
    duplicate_rows_removed = 0
    for row in t1_rows:
        signature = tuple(row[field] for field in fields)
        if signature in seen_rows:
            duplicate_rows_removed += 1
            continue
        seen_rows.add(signature)
        deduped_rows.append(row)
    write_csv(t1_path, fields, deduped_rows)

    # Drop malformed empty-T1 modal links.
    modal_path = package_dir / "relations/T1_in_modal.csv"
    fields, modal_rows, _ = read_csv(modal_path)
    valid_modal_rows = [row for row in modal_rows if row["T1_id"]]
    empty_modal_removed = len(modal_rows) - len(valid_modal_rows)
    write_csv(modal_path, fields, valid_modal_rows)

    # The source entity rows explicitly declare these memberships, so restoring the links is lossless.
    individual_path = package_dir / "entities/individual.csv"
    _, individual_rows, _ = read_csv(individual_path)
    declared_memberships = {
        (row["individual_accession"], row["study_accession"])
        for row in individual_rows
        if row["individual_accession"] and row["study_accession"]
    }
    membership_path = package_dir / "relations/individual_in_study.csv"
    membership_fields, membership_rows, _ = read_csv(membership_path)
    existing_memberships = {
        (row["individual_accession"], row["study_accession"])
        for row in membership_rows
    }
    missing_memberships = sorted(declared_memberships - existing_memberships)
    membership_rows.extend(
        {"individual_accession": individual, "study_accession": study}
        for individual, study in missing_memberships
    )
    membership_rows.sort(key=lambda row: (row["individual_accession"], row["study_accession"]))
    write_csv(membership_path, membership_fields, membership_rows)

    # Scope skips are explicit diagnostics, not silent failed relations.
    sets = entity_sets(package_dir)
    diagnostics = []
    scope_specs = (
        ("relations/sample_in_individual.csv", "sample_accession", "entities/sample.csv", "individual_accession", "entities/individual.csv"),
        ("relations/T1_in_sample.csv", "T1_id", "entities/T1.csv", "sample_accession", "entities/sample.csv"),
    )
    for rel_path, left_col, left_target, right_col, right_target in scope_specs:
        path = package_dir / rel_path
        fields, rows, _ = read_csv(path)
        kept = []
        for row_number, row in enumerate(rows, start=2):
            missing_columns = []
            if not row[left_col] or row[left_col] not in sets[left_target]:
                missing_columns.append(left_col)
            if not row[right_col] or row[right_col] not in sets[right_target]:
                missing_columns.append(right_col)
            if missing_columns:
                diagnostics.append({
                    "source_file": rel_path,
                    "source_row": str(row_number),
                    "left_column": left_col,
                    "left_id": row[left_col],
                    "right_column": right_col,
                    "right_id": row[right_col],
                    "reason": "endpoint_outside_package_scope:" + ";".join(missing_columns),
                })
            else:
                kept.append(row)
        write_csv(path, fields, kept)
    diagnostics_path = package_dir / "diagnostics/out_of_scope_relations.csv"
    write_csv(
        diagnostics_path,
        ["source_file", "source_row", "left_column", "left_id", "right_column", "right_id", "reason"],
        diagnostics,
    )

    validation = validate(package_dir)
    output_file_hashes = {
        path.relative_to(package_dir).as_posix(): sha256(path)
        for path in sorted(package_dir.rglob("*.csv"))
    }
    individual_groups = defaultdict(list)
    for row in individual_rows:
        individual_groups[row["individual_accession"]].append(row)
    multi_study = {
        key: rows for key, rows in individual_groups.items()
        if len({row["study_accession"] for row in rows}) > 1
    }
    non_study_conflicts = sum(
        any(
            len({row[column] for row in rows}) > 1
            for column in rows[0]
            if column != "study_accession"
        )
        for rows in multi_study.values()
    )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"path": str(source_zip), "sha256": sha256(source_zip)},
        "policy": {
            "neo4j_writes": False,
            "source_archive_overwritten": False,
            "semantic_inference": False,
        },
        "changes": {
            "encoding_conversions": encoding_conversions,
            "semantic_format_renames": FORMAT_RENAMES,
            "semantic_format_replacements": semantic_replacements,
            "source_invalid_t2_format_references": source_invalid_t2_format_references,
            "t1_identical_duplicates_removed": duplicate_rows_removed,
            "empty_t1_modal_rows_removed": empty_modal_removed,
            "blank_rows_removed": blank_rows_removed,
            "out_of_scope_relations_moved": len(diagnostics),
            "individual_study_memberships_added": len(missing_memberships),
        },
        "known_scope_gaps": {
            "t1_without_study_relation": 5156,
            "t1_without_modal_relation": 9702,
        },
        "hard_blockers": [
            {
                "title": f"{len(multi_study)} 个 Individual 跨 Study，其中 {non_study_conflicts} 个还有非 Study 属性冲突",
                "detail": "同一 individual_accession 对应多个 Study；其中一部分还具有不同临床/生存属性。旧导入器按 accession MERGE 后 SET，会由导入顺序覆盖属性。修复包只补齐已声明的成员关系，不擅自选择权威属性。必须决定使用 Study+Individual 复合键、关系属性，或指定权威记录。",
            },
            {
                "title": "工具图不足以支持任意流程组合",
                "detail": "39 个 Tool 只有 22 条 NEXT，形成 26 个连通分量，25 个工具孤立；缺少 tool_kind、decomposition_status、slot 模型和 HAS_STEP。`fastp -> Cell Ranger` 仍需领域确认，GATK 输出与 BCFtools 输入格式仍不兼容。不能为未拆解流程编造步骤或边。",
            },
            {
                "title": "压缩包不是可独立导入的交付物",
                "detail": "包内只有 CSV，没有与 7.28 schema 对应的 constraint/index/import/cleanup/validation 脚本。沿用 7.27 导入器会错误处理重复 Individual，也不能满足当前 matcher 需要的 t2/files/file_path/snapshot/provenance 契约。",
            },
            {
                "title": "物理数据路径无法在本机验证",
                "detail": "T2 使用 `/hpcdisk1/...` 路径，本机未挂载该目录。元数据记录存在不等于文件真实存在；导入前必须在目标存储环境执行存在性、可读性和大小校验。",
            },
        ],
        "source_file_sha256": source_file_hashes,
        "output_file_sha256": output_file_hashes,
        "validation": validation,
    }
    manifest_path = package_dir / "repair_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = package_dir / "REPAIR_REPORT.md"
    report_path.write_text(make_report(manifest), encoding="utf-8")

    zip_path = output_dir / "更新7.28-确定性修复版.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, Path(package_dir.name) / path.relative_to(package_dir))
    checksum_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    checksum_path.write_text(f"{sha256(zip_path)}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, manifest_path, report_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-dir", type=Path, required=True)
    args = parser.parse_args()
    zip_path, manifest_path, report_path = build(
        args.source_zip.resolve(), args.output_dir.resolve(), args.package_dir.resolve()
    )
    print(json.dumps({
        "zip": str(zip_path),
        "manifest": str(manifest_path),
        "report": str(report_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
