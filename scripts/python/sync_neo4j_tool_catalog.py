#!/usr/bin/env python3
"""Synchronize reviewed NEXT edges, with explicit catalog bootstrap support."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime_config import initialize_runtime  # noqa: E402


CATALOG_TO_RUNTIME_ID = {
    "T01": "fastp",
    "T02": "fastqc",
    "T03": "bwa",
    "T04": "samtools",
    "T05": "gatk",
    "T06": "bcftools",
    "T07": "snpeff",
    "T08": "trim_galore",
    "T09": "star",
    "T10": "rsem",
    "T11": "featurecounts",
    "T12": "multiqc",
    "T13": "diff_expr_go",
    "T14": "diff_expr_kegg",
    "T15": "driver_gene_gender_analysis",
    "T16": "her2_pfs_survival",
    "T17": "immune_infiltration_iobr",
    "T18": "paired_fastq_to_unmapped_bam",
    "T19": "rnaseq_unsupervised_cluster",
    "T20": "survival_analysis",
    "T21": "tmb_survival_analysis",
    "T22": "wes_somatic_maf_landscape",
    "T23": "wgcna",
}

TASK_PIPELINE = {
    "catalog_id": "TASK_RNASEQ_SINGLETASK",
    "tool_id": "rnaseq_singletask",
    "tool_name": "RNA-seq 单任务完整上游流程",
    "description": "从双端 RNA-seq FASTQ 完成质控、剪切、rRNA 去除、STAR 比对、RSEM、featureCounts 和 MultiQC。",
    "omics": "RNA-seq",
    "tool_kind": "task_pipeline",
    "function": "RNA-seq FASTQ 完整上游分析",
    "slots": [
        ("input", "fastq_1", "raw_fastq_read", ["fq.gz"], True),
        ("input", "fastq_2", "raw_fastq_read", ["fq.gz"], True),
        ("input", "rrna_star_index", "genome_annotation", ["index"], True),
        ("input", "star_genome_index", "genome_annotation", ["index"], True),
        ("input", "rsem_index", "genome_annotation", ["index"], True),
        ("input", "gtf_file", "genome_annotation", ["gtf"], True),
        ("output", "expression_matrix", "expression_abundance_matrix", ["tsv"], False),
        ("output", "count_matrix", "expression_count_matrix", ["tsv", "txt"], False),
        ("output", "aligned_bam", "sorted_dedup_bam", ["bam", "bai"], False),
        ("output", "quality_control", "quality_control_report", ["html", "zip"], False),
    ],
    "steps": [
        {"step_id": "fastqc", "tool_id": "fastqc", "order": 1, "depends_on": []},
        {"step_id": "trim_galore", "tool_id": "trim_galore", "order": 2, "depends_on": ["fastqc"]},
        {"step_id": "star", "tool_id": "star", "order": 3, "depends_on": ["trim_galore"]},
        {"step_id": "rsem", "tool_id": "rsem", "order": 4, "depends_on": ["star"]},
        {"step_id": "samtools", "tool_id": "samtools", "order": 5, "depends_on": ["star"]},
        {"step_id": "featurecounts", "tool_id": "featurecounts", "order": 6, "depends_on": ["samtools"]},
        {"step_id": "multiqc", "tool_id": "multiqc", "order": 7, "depends_on": ["rsem", "featurecounts"]},
    ],
}

SEMANTIC_TO_ARTIFACT = {
    "Raw FASTQ": "raw_fastq_read",
    "Clean FASTQ": "clean_fastq_read",
    "Genome Annotation": "genome_annotation",
    "uBAM (Unmapped)": "unmapped_bam",
    "Aligned SAM/BAM": "aligned_bam",
    "Sorted/Dedup BAM": "sorted_dedup_bam",
    "Unfiltered VCF": "unfiltered_vcf",
    "Filtered (PASS) VCF": "filtered_vcf",
    "Annotated VCF": "annotated_vcf",
    "Transcriptome BAM": "transcriptome_bam",
    "TPM / FPKM": "expression_abundance_matrix",
    "Raw Counts": "expression_count_matrix",
    "Sample Metadata": "sample_metadata",
    "Quality Control Report": "quality_control_report",
    "DE Result": "differential_expression_table",
    "Processed Object": "processed_object",
    "Public Somatic MAF": "somatic_maf",
}

FORMAT_ALIASES = {
    "FASTQ": "fq.gz",
    "fq.gz": "fq.gz",
    "HTML": "html",
    "JSON": "json",
    "ZIP": "zip",
    "SAM": "sam",
    "BAM": "bam",
    "BAI": "bai",
    "TXT": "txt",
    "TSV": "tsv",
    "TXT/TSV": "tsv",
    "VCF": "vcf",
    "TBI": "tbi",
    "FASTA": "fasta",
    "GTF": "gtf",
    "索引": "index",
    "数据库": "database",
    "各类日志": "log",
    "tsv": "tsv",
    "xlsx": "xlsx",
    "xls": "xls",
    "maf": "maf",
    "pdf": "pdf",
    "png": "png",
    "gz": "gz",
    "list": "list",
    "bam": "bam",
}

OPTIONAL_INPUT_SLOTS = {
    ("fastqc", "raw_fastq_read"),
    ("fastqc", "clean_fastq_read"),
    ("multiqc", "quality_control_report"),
}

CATALOG_LABELS = {"tool_id", "Tool", "io_slot", "IOSlot", "artifact_type", "ArtifactType", "function", "Function", "format", "Format"}
CATALOG_OWNER_LABELS = {"tool_id", "io_slot", "artifact_type", "function", "format"}
CATALOG_RELATIONSHIP_TYPES = {
    "ALLOW_FORMAT", "HAS_FUNCTION", "HAS_INPUT_SLOT", "HAS_OUTPUT_SLOT",
    "HAS_STEP", "INPUT", "MANIFEST_AS", "OUTPUT", "PRODUCES", "REQUIRES",
}
CANONICAL_NODE_FILES = {
    "tool_id.csv": ("tool_id", {"identity", "labels"}),
    "io_slot.csv": ("io_slot", {"identity", "labels"}),
    "artifact_type.csv": ("artifact_type", {"identity", "labels"}),
    "function.csv": ("function", {"identity", "labels"}),
    "format.csv": ("format", {"identity", "labels"}),
}


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _split(value: str) -> List[str]:
    return [part.strip() for part in re.split(r"[,，]", value or "") if part.strip()]


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "artifact"


def _formats(value: str) -> List[str]:
    result: List[str] = []
    for part in _split(value):
        normalized = FORMAT_ALIASES.get(part, part.lower().replace(" ", "_"))
        if normalized not in result:
            result.append(normalized)
    return result


def _decode_property(key: str, value: str) -> Any:
    if key in {"required", "is_generic", "exactly_one_variant"}:
        return value.lower() == "true"
    return value


def load_canonical_catalog(root: Path = ROOT) -> Dict[str, Any]:
    catalog_dir = root / "data" / "csv" / "catalog"
    nodes: List[Dict[str, Any]] = []
    identities = set()
    for filename, (canonical_label, ignored) in CANONICAL_NODE_FILES.items():
        for row in _read_csv(catalog_dir / filename):
            identity = row.get("identity") or ""
            labels = sorted(part for part in (row.get("labels") or "").split("|") if part)
            if not identity.startswith(canonical_label + ":"):
                raise RuntimeError(f"invalid catalog identity in {filename}: {identity}")
            if identity in identities:
                raise RuntimeError(f"duplicate catalog identity: {identity}")
            if not labels or any(label not in CATALOG_LABELS for label in labels):
                raise RuntimeError(f"invalid catalog labels for {identity}: {labels}")
            properties = {
                key: _decode_property(key, value)
                for key, value in row.items()
                if key not in ignored and value not in {None, ""}
            }
            identities.add(identity)
            nodes.append({"identity": identity, "labels": labels, "properties": properties})
    relationships = []
    for row in _read_csv(catalog_dir / "relationships.csv"):
        rel_type = row.get("type") or ""
        start = row.get("start") or ""
        end = row.get("end") or ""
        if rel_type not in CATALOG_RELATIONSHIP_TYPES:
            raise RuntimeError(f"invalid catalog relationship type: {rel_type}")
        if start not in identities or end not in identities:
            raise RuntimeError(f"catalog relationship endpoint missing: {start} -> {end}")
        properties = json.loads(row.get("properties_json") or "{}")
        if not isinstance(properties, dict):
            raise RuntimeError(f"relationship properties must be an object: {start} -> {end}")
        relationships.append({
            "type": rel_type,
            "start": start,
            "end": end,
            "properties": properties,
        })
    return {
        "nodes": sorted(nodes, key=lambda item: item["identity"]),
        "relationships": relationships,
    }


def _replace_catalog(tx: Any, catalog: Dict[str, Any]) -> None:
    tx.run(
        "MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) DETACH DELETE n",
        labels=sorted(CATALOG_OWNER_LABELS),
    ).consume()
    grouped_nodes: Dict[tuple[str, ...], List[Dict[str, Any]]] = {}
    for node in catalog["nodes"]:
        grouped_nodes.setdefault(tuple(node["labels"]), []).append(node)
    for labels, rows in grouped_nodes.items():
        label_clause = "".join(f":`{label}`" for label in labels)
        tx.run(
            f"UNWIND $rows AS row CREATE (n{label_clause}) "
            "SET n = row.properties, n.__catalog_csv_identity = row.identity",
            rows=rows,
        ).consume()
    grouped_relationships: Dict[str, List[Dict[str, Any]]] = {}
    for relationship in catalog["relationships"]:
        grouped_relationships.setdefault(relationship["type"], []).append(relationship)
    for rel_type, rows in grouped_relationships.items():
        tx.run(
            "UNWIND $rows AS row "
            "MATCH (a {__catalog_csv_identity: row.start}) "
            "MATCH (b {__catalog_csv_identity: row.end}) "
            f"CREATE (a)-[r:`{rel_type}`]->(b) SET r = row.properties",
            rows=rows,
        ).consume()
    tx.run(
        "MATCH (n) WHERE n.__catalog_csv_identity IS NOT NULL REMOVE n.__catalog_csv_identity"
    ).consume()


def _replace_next(tx: Any, expected_next: Sequence[Dict[str, str]]) -> None:
    catalog_ids = sorted({
        edge["from_catalog_id"] for edge in expected_next
    } | {
        edge["to_catalog_id"] for edge in expected_next
    })
    existing_record = tx.run(
        """
        MATCH (tool:tool_id)
        WHERE tool.catalog_id IN $catalog_ids
        RETURN collect(DISTINCT tool.catalog_id) AS catalog_ids
        """,
        catalog_ids=catalog_ids,
    ).single()
    existing_ids = set(existing_record["catalog_ids"] if existing_record else [])
    missing_ids = [catalog_id for catalog_id in catalog_ids if catalog_id not in existing_ids]
    if missing_ids:
        raise RuntimeError(
            "NEXT endpoints are missing from Neo4j: " + ", ".join(missing_ids)
        )
    tx.run("MATCH ()-[r:NEXT {source:'curated-next-csv'}]->() DELETE r").consume()
    for edge in expected_next:
        tx.run(
            """
            MATCH (a:tool_id {catalog_id: $from_catalog_id})
            MATCH (b:tool_id {catalog_id: $to_catalog_id})
            MERGE (a)-[r:NEXT {
                source:'curated-next-csv', output:$output, input:$input
            }]->(b)
            SET r.reviewed = true,
                r.review_version = '2026-07-22',
                r.kind = $kind,
                r.output = $output,
                r.input = $input
            """,
            **edge,
        ).consume()


def _replace_catalog_and_next(
    tx: Any,
    catalog: Dict[str, Any],
    expected_next: Sequence[Dict[str, str]],
) -> None:
    _replace_catalog(tx, catalog)
    _replace_next(tx, expected_next)


def load_catalog(root: Path = ROOT) -> Dict[str, object]:
    csv_root = root / "data" / "csv"
    tools = _read_csv(csv_root / "entities" / "tool.csv")
    functions = {
        row["tool_id"]: row["function"]
        for row in _read_csv(csv_root / "relations" / "tool_has_function.csv")
    }
    inputs: Dict[str, List[str]] = {}
    outputs: Dict[str, List[str]] = {}
    for row in _read_csv(csv_root / "relations" / "tool_input_format.csv"):
        inputs.setdefault(row["tool_id"], []).append(row["语义输入格式"])
    for row in _read_csv(csv_root / "relations" / "tool_output_format.csv"):
        outputs.setdefault(row["tool_id"], []).append(row["语义输出格式"])
    next_rows = _read_csv(csv_root / "relations" / "tool_relationship.csv")

    catalog = []
    for row in tools:
        catalog_id = row["tool_id"]
        runtime_id = CATALOG_TO_RUNTIME_ID[catalog_id]
        catalog.append({
            "catalog_id": catalog_id,
            "tool_id": runtime_id,
            "tool_name": row["tool_name"],
            "description": row["function"],
            "omics": row["适用组学"],
            "tool_kind": "atomic" if int(catalog_id[1:]) <= 12 else "pipeline",
            "function": functions.get(catalog_id) or row["function"],
            "input_semantics": inputs.get(catalog_id, []),
            "output_semantics": outputs.get(catalog_id, []),
            "input_formats": _formats(row["输入格式"]),
            "output_formats": _formats(row["输出格式"]),
        })
    return {"tools": catalog, "next": next_rows}


def _sync_tool(tx, tool: Dict[str, object]) -> None:
    tx.run(
        """
        MERGE (t:tool_id {tool_id: $tool_id})
        SET t:Tool,
            t.catalog_id = $catalog_id,
            t.tool_name = $tool_name,
            t.description = coalesce(t.description, $description),
            t.omics = $omics,
            t.tool_kind = $tool_kind,
            t.catalog_source = 'sister-tool-csv'
        """,
        **tool,
    ).consume()
    tx.run(
        """
        MATCH (t:tool_id {tool_id: $tool_id})
        MERGE (f:function {function: $function})
        SET f:Function
        MERGE (t)-[:HAS_FUNCTION]->(f)
        """,
        tool_id=tool["tool_id"],
        function=tool["function"],
    ).consume()

    if tool["tool_kind"] != "atomic":
        return
    for direction, semantics, formats in (
        ("input", tool["input_semantics"], tool["input_formats"]),
        ("output", tool["output_semantics"], tool["output_formats"]),
    ):
        for semantic in semantics:
            artifact = SEMANTIC_TO_ARTIFACT.get(str(semantic), _slug(str(semantic)))
            slot_id = f"{tool['tool_id']}::{direction}::{artifact}"
            edge = "HAS_INPUT_SLOT" if direction == "input" else "HAS_OUTPUT_SLOT"
            artifact_edge = "REQUIRES" if direction == "input" else "PRODUCES"
            tx.run(
                f"""
                MATCH (t:tool_id {{tool_id: $tool_id}})
                MERGE (s:io_slot {{slot_id: $slot_id}})
                SET s:IOSlot,
                    s.tool_id = $tool_id,
                    s.slot_name = $artifact,
                    s.direction = $direction,
                    s.required = $required,
                    s.description = $semantic,
                    s.catalog_source = 'sister-tool-csv'
                MERGE (a:artifact_type {{artifact_type: $artifact}})
                SET a:ArtifactType,
                    a.description = coalesce(a.description, $semantic)
                MERGE (t)-[:{edge}]->(s)
                MERGE (s)-[:{artifact_edge}]->(a)
                """,
                tool_id=tool["tool_id"],
                slot_id=slot_id,
                artifact=artifact,
                direction=direction,
                required=(
                    direction == "input"
                    and (tool["tool_id"], artifact) not in OPTIONAL_INPUT_SLOTS
                ),
                semantic=semantic,
            ).consume()
            for fmt in formats:
                tx.run(
                    """
                    MATCH (s:io_slot {slot_id: $slot_id})
                    MATCH (a:artifact_type {artifact_type: $artifact})
                    MERGE (f:format {format: $format})
                    SET f:Format
                    MERGE (s)-[:ALLOW_FORMAT]->(f)
                    MERGE (a)-[:MANIFEST_AS]->(f)
                    """,
                    slot_id=slot_id,
                    artifact=artifact,
                    format=fmt,
                ).consume()


def _sync_task_pipeline(tx) -> None:
    tool = TASK_PIPELINE
    tx.run(
        """
        MERGE (t:tool_id {tool_id: $tool_id})
        SET t:Tool,
            t.catalog_id = $catalog_id,
            t.tool_name = $tool_name,
            t.description = $description,
            t.omics = $omics,
            t.tool_kind = $tool_kind,
            t.catalog_source = 'sister-task-pipeline'
        MERGE (f:function {function: $function})
        SET f:Function
        MERGE (t)-[:HAS_FUNCTION]->(f)
        """,
        **{key: value for key, value in tool.items() if key not in {"slots", "steps"}},
    ).consume()
    for direction, slot_name, artifact, formats, required in tool["slots"]:
        slot_id = f"{tool['tool_id']}::{direction}::{slot_name}"
        edge = "HAS_INPUT_SLOT" if direction == "input" else "HAS_OUTPUT_SLOT"
        artifact_edge = "REQUIRES" if direction == "input" else "PRODUCES"
        tx.run(
            f"""
            MATCH (t:tool_id {{tool_id: $tool_id}})
            MERGE (s:io_slot {{slot_id: $slot_id}})
            SET s:IOSlot,
                s.tool_id = $tool_id,
                s.slot_name = $slot_name,
                s.direction = $direction,
                s.required = $required,
                s.description = $slot_name,
                s.catalog_source = 'sister-task-pipeline'
            MERGE (a:artifact_type {{artifact_type: $artifact}})
            SET a:ArtifactType
            MERGE (t)-[:{edge}]->(s)
            MERGE (s)-[:{artifact_edge}]->(a)
            """,
            tool_id=tool["tool_id"],
            slot_id=slot_id,
            slot_name=slot_name,
            direction=direction,
            required=required,
            artifact=artifact,
        ).consume()
        for fmt in formats:
            tx.run(
                """
                MATCH (s:io_slot {slot_id: $slot_id})
                MATCH (a:artifact_type {artifact_type: $artifact})
                MERGE (f:format {format: $format})
                SET f:Format
                MERGE (s)-[:ALLOW_FORMAT]->(f)
                MERGE (a)-[:MANIFEST_AS]->(f)
                """,
                slot_id=slot_id,
                artifact=artifact,
                format=fmt,
            ).consume()
    tx.run(
        """
        MATCH (pipeline:tool_id {tool_id: $pipeline_id})
              -[edge:HAS_STEP {source:'sister-task-pipeline'}]->()
        DELETE edge
        """,
        pipeline_id=tool["tool_id"],
    ).consume()
    for step in tool["steps"]:
        tx.run(
            """
            MATCH (pipeline:tool_id {tool_id: $pipeline_id})
            MATCH (method:tool_id {tool_id: $tool_id, tool_kind:'atomic'})
            MERGE (pipeline)-[edge:HAS_STEP {source:'sister-task-pipeline', step_id:$step_id}]->(method)
            SET edge.order = $order,
                edge.depends_on = $depends_on,
                edge.locked = true
            """,
            pipeline_id=tool["tool_id"],
            **step,
        ).consume()


def sync_catalog(
    database: str,
    apply: bool,
    bootstrap_catalog: bool = False,
) -> Dict[str, object]:
    initialize_runtime()
    payload = load_catalog()
    canonical = load_canonical_catalog() if bootstrap_catalog else None
    expected_next = [
        {
            "from_catalog_id": row["tool_id"],
            "to_catalog_id": row["next_tool_id"],
            "kind": row.get("kind") or "order",
            "output": row.get("output") or "",
            "input": row.get("input") or "",
        }
        for row in payload["next"]
    ]
    summary: Dict[str, object] = {
        "mode": "apply-next" if apply else "dry-run",
        "catalog_bootstrap": bootstrap_catalog,
        "tool_count": len(payload["tools"]) + 1,
        "atomic_tool_count": sum(t["tool_kind"] == "atomic" for t in payload["tools"]),
        "pipeline_tool_count": sum(t["tool_kind"] == "pipeline" for t in payload["tools"]) + 1,
        "task_pipeline_count": 1,
        "next_count": len(expected_next),
    }
    if canonical:
        summary["canonical_csv"] = {
            "nodes": len(canonical["nodes"]),
            "relationships_excluding_next": len(canonical["relationships"]),
        }
    if not apply:
        summary["next"] = expected_next
        return summary

    from neo4j import GraphDatabase, READ_ACCESS

    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )
    try:
        with driver.session(database=database) as session:
            if bootstrap_catalog:
                session.run(
                    "CREATE CONSTRAINT tool_catalog_id_unique IF NOT EXISTS "
                    "FOR (t:tool_id) REQUIRE t.catalog_id IS UNIQUE"
                ).consume()
                session.execute_write(
                    _replace_catalog_and_next, canonical, expected_next
                )
            else:
                session.execute_write(_replace_next, expected_next)
        with driver.session(database=database, default_access_mode=READ_ACCESS) as session:
            record = session.run(
                """
                MATCH (t:tool_id) WHERE t.catalog_id IS NOT NULL
                WITH count(t) AS tools
                MATCH ()-[r:NEXT {source:'curated-next-csv'}]->()
                RETURN tools, count(r) AS next_count,
                       count(CASE WHEN startNode(r)=endNode(r) THEN 1 END) AS self_loops
                """
            ).single()
            summary["database"] = {
                "catalog_tools": record["tools"],
                "next_count": record["next_count"],
                "self_loops": record["self_loops"],
            }
    finally:
        driver.close()
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write reviewed NEXT edges only; tool definitions are not modified",
    )
    parser.add_argument(
        "--bootstrap-catalog",
        action="store_true",
        help="explicitly initialize/update tool nodes and slots before writing NEXT",
    )
    parser.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    args = parser.parse_args(argv)
    print(json.dumps(
        sync_catalog(args.database, args.apply, args.bootstrap_catalog),
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
