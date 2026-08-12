#!/usr/bin/env python3
"""Apply the reviewed mate/sample-role/variant catalog delta idempotently."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "csv" / "catalog"
RELATIONS = ROOT / "data" / "csv" / "relations"


def read(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write(path: Path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def upsert(rows, key, value):
    identity = key(value)
    for index, row in enumerate(rows):
        if key(row) == identity:
            rows[index] = {**row, **value}
            return
    rows.append(value)


def main() -> int:
    tool_path = CATALOG / "tool_id.csv"
    tool_fields, tools = read(tool_path)
    for field in ("input_variants_json", "input_aliases_json", "exactly_one_variant"):
        if field not in tool_fields:
            tool_fields.append(field)
    for tool in tools:
        if tool.get("tool_id") == "fastp":
            tool.update({
                "input_variants_json": json.dumps({
                    "single_end": ["raw_fastq_read_r1"],
                    "paired_end": ["raw_fastq_read_r1", "raw_fastq_read_r2"],
                }, separators=(",", ":")),
                "input_aliases_json": json.dumps(
                    {"raw_fastq_read": "raw_fastq_read_r1"}, separators=(",", ":")
                ),
                "exactly_one_variant": "true",
            })
        elif tool.get("tool_id") == "gatk":
            tool.update({
                "input_variants_json": json.dumps({
                    "single": ["sorted_dedup_bam"],
                    "paired": ["tumor_bam", "tumor_bai", "normal_bam", "normal_bai"],
                }, separators=(",", ":")),
                "input_aliases_json": "{}",
                "exactly_one_variant": "true",
            })
    write(tool_path, tool_fields, tools)

    slot_path = CATALOG / "io_slot.csv"
    slot_fields, slots = read(slot_path)
    for field in (
        "artifact", "wdl_type", "dimension", "dimension_value", "variant",
        "variant_alias_for",
    ):
        if field not in slot_fields:
            slot_fields.append(field)
    for slot in slots:
        slot.setdefault("wdl_type", "File")
        if slot.get("slot_id") == "fastp::input::raw_fastq_read":
            slot.update({
                "required": "false", "artifact": "raw_fastq_read", "dimension": "mate",
                "dimension_value": "r1", "variant_alias_for": "raw_fastq_read_r1",
            })
        elif slot.get("slot_id") == "fastp::output::clean_fastq_read":
            slot.update({
                "artifact": "clean_fastq_read", "dimension": "mate",
                "dimension_value": "r1", "variant_alias_for": "clean_fastq_read_r1",
            })
        elif slot.get("slot_id") == "bwa::input::clean_fastq_read":
            slot.update({
                "required": "false", "artifact": "clean_fastq_read", "dimension": "mate",
                "dimension_value": "r1", "variant_alias_for": "clean_fastq_read_r1",
            })
        elif slot.get("slot_id") == "gatk::input::sorted_dedup_bam":
            slot.update({"required": "false", "artifact": "sorted_dedup_bam", "variant": "single"})

    def slot_row(tool, direction, name, artifact, required, dimension="", value="", variant=""):
        slot_id = f"{tool}::{direction}::{name}"
        return {
            "identity": f"io_slot:{slot_id}",
            "labels": "IOSlot|io_slot",
            "catalog_source": "slot-model-fix-2026-07-24",
            "description": name,
            "direction": direction,
            "one_of_group": "",
            "required": "true" if required else "false",
            "slot_id": slot_id,
            "slot_name": name,
            "tool_id": tool,
            "artifact": artifact,
            "wdl_type": "File",
            "dimension": dimension,
            "dimension_value": value,
            "variant": variant,
            "variant_alias_for": "",
        }

    new_slots = [
        slot_row("fastp", "input", "raw_fastq_read_r1", "raw_fastq_read", False, "mate", "r1", "single_end|paired_end"),
        slot_row("fastp", "input", "raw_fastq_read_r2", "raw_fastq_read", False, "mate", "r2", "paired_end"),
        slot_row("fastp", "output", "clean_fastq_read_r1", "clean_fastq_read", False, "mate", "r1"),
        slot_row("fastp", "output", "clean_fastq_read_r2", "clean_fastq_read", False, "mate", "r2"),
        slot_row("bwa", "input", "clean_fastq_read_r1", "clean_fastq_read", False, "mate", "r1"),
        slot_row("bwa", "input", "clean_fastq_read_r2", "clean_fastq_read", False, "mate", "r2"),
        slot_row("samtools", "output", "bai", "bai", False, "sample_role", "inherit"),
        slot_row("gatk", "input", "tumor_bam", "sorted_dedup_bam", False, "sample_role", "tumor", "paired"),
        slot_row("gatk", "input", "tumor_bai", "bai", False, "sample_role", "tumor", "paired"),
        slot_row("gatk", "input", "normal_bam", "sorted_dedup_bam", False, "sample_role", "normal", "paired"),
        slot_row("gatk", "input", "normal_bai", "bai", False, "sample_role", "normal", "paired"),
        slot_row("gatk", "input", "interval_list", "interval_list", True),
    ]
    for row in new_slots:
        upsert(slots, lambda item: item.get("identity"), row)
    write(slot_path, slot_fields, slots)

    artifact_path = CATALOG / "artifact_type.csv"
    artifact_fields, artifacts = read(artifact_path)
    for row in (
        {"identity": "artifact_type:bai", "labels": "ArtifactType|artifact_type", "artifact_type": "bai", "description": "BAM index", "is_generic": "false"},
        {"identity": "artifact_type:interval_list", "labels": "ArtifactType|artifact_type", "artifact_type": "interval_list", "description": "WES interval list", "is_generic": "false"},
    ):
        upsert(artifacts, lambda item: item.get("identity"), row)
    write(artifact_path, artifact_fields, artifacts)

    format_path = CATALOG / "format.csv"
    format_fields, formats = read(format_path)
    upsert(formats, lambda item: item.get("identity"), {
        "identity": "catalog_format:interval_list", "labels": "CatalogFormat|catalog_format",
        "format": "interval_list", "description": "GATK interval list",
    })
    write(format_path, format_fields, formats)

    relationship_path = CATALOG / "relationships.csv"
    rel_fields, relationships = read(relationship_path)
    def add_rel(rel_type, start, end, properties=None):
        row = {
            "type": rel_type,
            "start": start,
            "end": end,
            "properties_json": json.dumps(properties or {}, separators=(",", ":"), sort_keys=True),
        }
        upsert(
            relationships,
            lambda item: (item.get("type"), item.get("start"), item.get("end"), item.get("properties_json")),
            row,
        )
    for row in new_slots:
        slot_identity = row["identity"]
        direction = row["direction"]
        add_rel(
            "HAS_INPUT_SLOT" if direction == "input" else "HAS_OUTPUT_SLOT",
            f"tool_id:{row['tool_id']}", slot_identity,
        )
        add_rel(
            "REQUIRES" if direction == "input" else "PRODUCES",
            slot_identity, f"artifact_type:{row['artifact']}",
        )
        allowed_formats = (
            ["fq.gz"] if row["artifact"] in {"raw_fastq_read", "clean_fastq_read"}
            else ["bam"] if row["slot_name"].endswith("_bam")
            else ["bai"] if row["artifact"] == "bai"
            else ["interval_list"] if row["artifact"] == "interval_list"
            else []
        )
        for fmt in allowed_formats:
            add_rel("ALLOW_FORMAT", slot_identity, f"catalog_format:{fmt}")
            add_rel("MANIFEST_AS", f"artifact_type:{row['artifact']}", f"catalog_format:{fmt}")
    write(relationship_path, rel_fields, relationships)

    next_path = RELATIONS / "tool_relationship.csv"
    next_fields, next_rows = read(next_path)
    for row in (
        {"tool_id": "T001", "next_tool_id": "T006", "kind": "data", "output": "clean_fastq_read_r1", "input": "clean_fastq_read_r1"},
        {"tool_id": "T001", "next_tool_id": "T006", "kind": "data", "output": "clean_fastq_read_r2", "input": "clean_fastq_read_r2"},
        {"tool_id": "T007", "next_tool_id": "T008", "kind": "data", "output": "sorted_dedup_bam", "input": "tumor_bam"},
        {"tool_id": "T007", "next_tool_id": "T008", "kind": "data", "output": "bai", "input": "tumor_bai"},
        {"tool_id": "T007", "next_tool_id": "T008", "kind": "data", "output": "sorted_dedup_bam", "input": "normal_bam"},
        {"tool_id": "T007", "next_tool_id": "T008", "kind": "data", "output": "bai", "input": "normal_bai"},
    ):
        upsert(
            next_rows,
            lambda item: (
                item.get("tool_id"), item.get("next_tool_id"), item.get("kind"),
                item.get("output"), item.get("input"),
            ),
            row,
        )
    write(next_path, next_fields, next_rows)
    print("slot model CSV delta applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
