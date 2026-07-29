#!/usr/bin/env python3
"""Apply the reviewed BWA/STAR/SAMtools BAM artifact contract correction."""

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


MIGRATION_SOURCE = "bam-artifact-contract-fix-2026-07-22"


def _merge_slot(
    tx: Any,
    *,
    tool_id: str,
    direction: str,
    artifact: str,
    description: str,
    formats: Sequence[str],
) -> None:
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
            slot.description = $description,
            slot.catalog_source = $source
        MERGE (artifact:artifact_type {{artifact_type: $artifact}})
        SET artifact:ArtifactType,
            artifact.description = coalesce(artifact.description, $description)
        MERGE (tool)-[:{edge}]->(slot)
        MERGE (slot)-[:{artifact_edge}]->(artifact)
        """,
        tool_id=tool_id,
        slot_id=slot_id,
        artifact=artifact,
        direction=direction,
        required=direction == "input",
        description=description,
        source=MIGRATION_SOURCE,
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
        WHERE tool.tool_id IN ['bwa', 'star', 'samtools']
        RETURN collect(tool.tool_id) AS tool_ids
        """
    ).single()
    found = set(record["tool_ids"] if record else [])
    missing = sorted({"bwa", "star", "samtools"} - found)
    if missing:
        raise RuntimeError("required Neo4j tools are missing: " + ", ".join(missing))

    tx.run(
        """
        MATCH (:tool_id {tool_id:'bwa'})-[:HAS_OUTPUT_SLOT]->
              (slot:io_slot {slot_id:'bwa::output::unmapped_bam'})
        DETACH DELETE slot
        """
    ).consume()
    tx.run(
        """
        MATCH (:tool_id {tool_id:'samtools'})-[:HAS_INPUT_SLOT]->
              (slot:io_slot {slot_id:'samtools::input::unmapped_bam'})
        DETACH DELETE slot
        """
    ).consume()
    tx.run(
        """
        MATCH (:tool_id {tool_id:'samtools'})-[:HAS_INPUT_SLOT]->
              (slot:io_slot {slot_id:'samtools::input::sorted_dedup_bam'})
        DETACH DELETE slot
        """
    ).consume()
    tx.run(
        """
        MATCH (:tool_id {tool_id:'star'})-[:HAS_OUTPUT_SLOT]->
              (slot:io_slot {slot_id:'star::output::sorted_dedup_bam'})
        DETACH DELETE slot
        """
    ).consume()
    _merge_slot(
        tx,
        tool_id="bwa",
        direction="output",
        artifact="aligned_bam",
        description="Aligned SAM/BAM",
        formats=("sam", "bam"),
    )
    _merge_slot(
        tx,
        tool_id="samtools",
        direction="input",
        artifact="aligned_bam",
        description="Aligned SAM/BAM",
        formats=("sam", "bam"),
    )
    _merge_slot(
        tx,
        tool_id="star",
        direction="output",
        artifact="aligned_bam",
        description="Genome-aligned BAM from STAR",
        formats=("bam",),
    )


def migrate(database: str, apply: bool) -> Dict[str, Any]:
    initialize_runtime()
    summary: Dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "source": MIGRATION_SOURCE,
        "changes": [
            "BWA output: unmapped_bam -> aligned_bam",
            "SAMtools input: remove unmapped_bam",
            "SAMtools input: add aligned_bam; sorted_dedup_bam is a compatible subtype",
            "STAR genomic BAM output: sorted_dedup_bam -> aligned_bam",
        ],
    }
    if not apply:
        return summary

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
                WHERE tool.tool_id IN ['bwa', 'star', 'samtools']
                OPTIONAL MATCH (slot)-[:REQUIRES|PRODUCES]->(artifact:artifact_type)
                RETURN tool.tool_id AS tool_id, type(edge) AS edge_type,
                       slot.slot_name AS slot_name, artifact.artifact_type AS artifact
                ORDER BY tool_id, edge_type, slot_name
                """
            )]
            stale = session.run(
                """
                MATCH (slot:io_slot)
                WHERE slot.slot_id IN [
                    'bwa::output::unmapped_bam',
                    'samtools::input::unmapped_bam',
                    'samtools::input::sorted_dedup_bam',
                    'star::output::sorted_dedup_bam'
                ]
                RETURN count(slot) AS count
                """
            ).single()
        summary["contracts"] = rows
        summary["stale_slot_count"] = stale["count"] if stale else None
    finally:
        driver.close()
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    args = parser.parse_args(argv)
    print(json.dumps(migrate(args.database, args.apply), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
