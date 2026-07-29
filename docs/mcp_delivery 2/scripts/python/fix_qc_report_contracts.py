#!/usr/bin/env python3
"""Correct FastQC/MultiQC report artifacts without changing NEXT edges."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime_config import initialize_runtime  # noqa: E402


SOURCE = "qc-report-contract-fix-2026-07-22"


def _merge_slot(
    tx: Any,
    *,
    tool_id: str,
    direction: str,
    required: bool,
    formats: Sequence[str],
) -> None:
    artifact = "quality_control_report"
    slot_id = f"{tool_id}::{direction}::{artifact}"
    edge = "HAS_INPUT_SLOT" if direction == "input" else "HAS_OUTPUT_SLOT"
    artifact_edge = "REQUIRES" if direction == "input" else "PRODUCES"
    tx.run(
        f"""
        MATCH (tool:tool_id {{tool_id: $tool_id}})
        MERGE (slot:io_slot {{slot_id: $slot_id}})
        SET slot:IOSlot,
            slot.tool_id = $tool_id,
            slot.slot_name = $artifact,
            slot.direction = $direction,
            slot.required = $required,
            slot.description = 'Quality Control Report',
            slot.catalog_source = $source
        MERGE (artifact:artifact_type {{artifact_type: $artifact}})
        SET artifact:ArtifactType,
            artifact.description = 'Quality control reports and logs'
        MERGE (tool)-[:{edge}]->(slot)
        MERGE (slot)-[:{artifact_edge}]->(artifact)
        """,
        tool_id=tool_id,
        slot_id=slot_id,
        artifact=artifact,
        direction=direction,
        required=required,
        source=SOURCE,
    ).consume()
    for fmt in formats:
        tx.run(
            """
            MATCH (slot:io_slot {slot_id: $slot_id})
            MATCH (artifact:artifact_type {artifact_type: $artifact})
            MERGE (format:format {format: $format})
            SET format:Format
            MERGE (slot)-[:ALLOW_FORMAT]->(format)
            MERGE (artifact)-[:MANIFEST_AS]->(format)
            """,
            slot_id=slot_id,
            artifact=artifact,
            format=fmt,
        ).consume()


def _apply(tx: Any) -> None:
    record = tx.run(
        """
        MATCH (tool:tool_id)
        WHERE tool.tool_id IN ['fastqc', 'multiqc']
        RETURN collect(tool.tool_id) AS tool_ids
        """
    ).single()
    found = set(record["tool_ids"] if record else [])
    missing = sorted({"fastqc", "multiqc"} - found)
    if missing:
        raise RuntimeError("required Neo4j tools are missing: " + ", ".join(missing))

    tx.run(
        """
        MATCH (slot:io_slot)
        WHERE slot.slot_id IN [
            'fastqc::output::sample_metadata',
            'multiqc::input::sample_metadata',
            'multiqc::output::sample_metadata'
        ]
        DETACH DELETE slot
        """
    ).consume()
    tx.run(
        """
        MATCH (:tool_id {tool_id:'fastqc'})-[:HAS_INPUT_SLOT]->(slot:io_slot)
        WHERE slot.slot_name IN ['raw_fastq_read', 'clean_fastq_read']
        SET slot.required = false,
            slot.one_of_group = 'fastq_reads'
        """
    ).consume()
    _merge_slot(
        tx,
        tool_id="fastqc",
        direction="output",
        required=False,
        formats=("html", "zip"),
    )
    _merge_slot(
        tx,
        tool_id="multiqc",
        direction="input",
        required=False,
        formats=("log", "html", "zip", "tsv"),
    )
    _merge_slot(
        tx,
        tool_id="multiqc",
        direction="output",
        required=False,
        formats=("html", "tsv"),
    )


def migrate(database: str, apply: bool) -> Dict[str, Any]:
    initialize_runtime()
    result: Dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "source": SOURCE,
        "changes": [
            "FastQC output: sample_metadata -> quality_control_report",
            "MultiQC optional input: sample_metadata -> quality_control_report",
            "MultiQC output: sample_metadata -> quality_control_report",
            "FastQC raw/clean FASTQ inputs: optional alternatives",
        ],
    }
    if not apply:
        return result

    from neo4j import GraphDatabase, READ_ACCESS

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        with driver.session(database=database) as session:
            session.execute_write(_apply)
        with driver.session(database=database, default_access_mode=READ_ACCESS) as session:
            rows = [dict(row) for row in session.run(
                """
                MATCH (tool:tool_id)-[edge:HAS_INPUT_SLOT|HAS_OUTPUT_SLOT]->(slot:io_slot)
                WHERE tool.tool_id IN ['fastqc', 'multiqc']
                OPTIONAL MATCH (slot)-[:REQUIRES|PRODUCES]->(artifact:artifact_type)
                RETURN tool.tool_id AS tool_id, type(edge) AS edge_type,
                       slot.slot_name AS slot_name, slot.required AS required,
                       artifact.artifact_type AS artifact
                ORDER BY tool_id, edge_type, slot_name
                """
            )]
            stale = session.run(
                """
                MATCH (slot:io_slot)
                WHERE slot.slot_id IN [
                    'fastqc::output::sample_metadata',
                    'multiqc::input::sample_metadata',
                    'multiqc::output::sample_metadata'
                ]
                RETURN count(slot) AS count
                """
            ).single()
        result["contracts"] = rows
        result["stale_slot_count"] = stale["count"] if stale else None
    finally:
        driver.close()
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    args = parser.parse_args(argv)
    print(json.dumps(migrate(args.database, args.apply), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
