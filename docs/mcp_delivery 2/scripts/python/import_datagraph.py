#!/usr/bin/env python3
"""Deterministically replace a data graph in an explicitly isolated Neo4j database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from neo4j import GraphDatabase, WRITE_ACCESS

from datagraph_common import (
    DATAGRAPH_LABEL_KEYS,
    IMPORTER_VERSION,
    SCHEMA_VERSION,
    aggregate_dangling,
    assert_target_isolation,
    build_graph_spec,
    canonical_json,
    chunked,
    safe_identifier,
    sha256_text,
)


CONSTRAINTS = [
    ("dg_project_accession_unique", "project", "project_accession"),
    ("dg_study_accession_unique", "study", "study_accession"),
    ("dg_individual_accession_unique", "individual", "individual_accession"),
    ("dg_sample_accession_unique", "sample", "sample_accession"),
    ("dg_run_accession_unique", "run", "run_accession"),
    ("dg_t1_files_unique", "t1", "files"),
    ("dg_t2_id_unique", "t2", "t2_id"),
    ("dg_data_format_unique", "data_format", "format"),
    ("dg_data_format_row_unique", "data_format_row", "format_row_id"),
    ("dg_data_level_unique", "data_level", "level"),
    ("dg_cohort_status_unique", "cohort", "status"),
    ("dg_data_modal_unique", "data_modal", "modal"),
]

INDEXES = [
    ("dg_t1_study_index", "t1", "study_accession"),
    ("dg_t1_individual_index", "t1", "individual_accession"),
    ("dg_t1_sample_index", "t1", "sample_accession"),
    ("dg_t1_run_index", "t1", "run_accession"),
    ("dg_t1_strategy_index", "t1", "strategy"),
    ("dg_t1_physical_format_index", "t1", "physical_format"),
    ("dg_t2_study_index", "t2", "study_accession"),
    ("dg_t2_strategy_index", "t2", "strategy"),
    ("dg_t2_physical_format_index", "t2", "format"),
    ("dg_sample_study_index", "sample", "study_accession"),
    ("dg_sample_individual_index", "sample", "individual_accession"),
    ("dg_individual_study_index", "individual", "study_accession"),
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def script_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def git_state(project_root: Path) -> Dict[str, Any]:
    try:
        top = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--show-toplevel"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        commit_process = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=False,
            text=True,
            capture_output=True,
        )
        commit = commit_process.stdout.strip() if commit_process.returncode == 0 else None
        tracked_process = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "--error-unmatch", str(Path(__file__).resolve())],
            check=False,
            text=True,
            capture_output=True,
        )
        return {
            "git_toplevel": top,
            "git_commit": commit,
            "script_tracked": tracked_process.returncode == 0,
        }
    except (OSError, subprocess.SubprocessError):
        return {"git_toplevel": None, "git_commit": None, "script_tracked": False}


def schema_statements() -> List[str]:
    statements: List[str] = []
    for name, label, prop in CONSTRAINTS:
        statements.append(
            f"CREATE CONSTRAINT `{name}` IF NOT EXISTS FOR (n:`{safe_identifier(label)}`) "
            f"REQUIRE n.`{safe_identifier(prop)}` IS UNIQUE"
        )
    for name, label, prop in INDEXES:
        statements.append(
            f"CREATE INDEX `{name}` IF NOT EXISTS FOR (n:`{safe_identifier(label)}`) "
            f"ON (n.`{safe_identifier(prop)}`)"
        )
    return statements


def current_counts(session: Any) -> Dict[str, Dict[str, int]]:
    labels = {
        str(row["label"]): int(row["count"])
        for row in session.run(
            "MATCH (n) WHERE n.datagraph_managed = true "
            "UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY label"
        )
    }
    relationships = {
        str(row["type"]): int(row["count"])
        for row in session.run(
            "MATCH ()-[r]->() WHERE r.datagraph_managed = true "
            "RETURN type(r) AS type, count(*) AS count ORDER BY type"
        )
    }
    return {"labels": labels, "relationships": relationships}


def schema_inventory(session: Any) -> Dict[str, Any]:
    constraints = [
        dict(row)
        for row in session.run(
            "SHOW CONSTRAINTS YIELD name,type,entityType,labelsOrTypes,properties,ownedIndex "
            "RETURN name,type,entityType,labelsOrTypes,properties,ownedIndex ORDER BY name"
        )
    ]
    indexes = [
        dict(row)
        for row in session.run(
            "SHOW INDEXES YIELD name,type,entityType,labelsOrTypes,properties,state,owningConstraint,createStatement "
            "RETURN name,type,entityType,labelsOrTypes,properties,state,owningConstraint,createStatement ORDER BY name"
        )
    ]
    return {"constraints": constraints, "indexes": indexes}


def neo4j_components(session: Any) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in session.run(
            "CALL dbms.components() YIELD name,versions,edition RETURN name,versions,edition ORDER BY name"
        )
    ]


def actual_graph_fingerprint(session: Any) -> str:
    nodes: List[Dict[str, Any]] = []
    for row in session.run(
        "MATCH (n) WHERE n.datagraph_managed = true RETURN labels(n) AS labels, properties(n) AS properties"
    ):
        labels = [label for label in row["labels"] if label in DATAGRAPH_LABEL_KEYS]
        if len(labels) != 1:
            raise RuntimeError(f"managed node has unexpected labels: {row['labels']}")
        label = labels[0]
        props = dict(row["properties"])
        key_name = DATAGRAPH_LABEL_KEYS[label]
        key_value = str(props.get(key_name, ""))
        node_id = f"{label}:{key_value}"
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "key_name": key_name,
                "key_value": key_value,
                "properties": props,
            }
        )
    rels: List[Dict[str, Any]] = []
    for row in session.run(
        "MATCH (a)-[r]->(b) WHERE r.datagraph_managed = true "
        "RETURN labels(a) AS start_labels, properties(a) AS start_props, type(r) AS type, "
        "properties(r) AS properties, labels(b) AS end_labels, properties(b) AS end_props"
    ):
        start_labels = [label for label in row["start_labels"] if label in DATAGRAPH_LABEL_KEYS]
        end_labels = [label for label in row["end_labels"] if label in DATAGRAPH_LABEL_KEYS]
        if len(start_labels) != 1 or len(end_labels) != 1:
            raise RuntimeError("managed relationship endpoint has unexpected labels")
        start_label, end_label = start_labels[0], end_labels[0]
        start_key_name = DATAGRAPH_LABEL_KEYS[start_label]
        end_key_name = DATAGRAPH_LABEL_KEYS[end_label]
        start_key = str(row["start_props"].get(start_key_name, ""))
        end_key = str(row["end_props"].get(end_key_name, ""))
        start_id = f"{start_label}:{start_key}"
        end_id = f"{end_label}:{end_key}"
        rel_type = str(row["type"])
        rels.append(
            {
                "id": f"{rel_type}|{start_id}|{end_id}",
                "type": rel_type,
                "start_id": start_id,
                "start_label": start_label,
                "start_key_name": start_key_name,
                "start_key_value": start_key,
                "end_id": end_id,
                "end_label": end_label,
                "end_key_name": end_key_name,
                "end_key_value": end_key,
                "properties": dict(row["properties"]),
            }
        )
    payload = {
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "relationships": sorted(rels, key=lambda item: item["id"]),
    }
    return sha256_text(canonical_json(payload))


def guard(session: Any, args: argparse.Namespace) -> Dict[str, Any]:
    return assert_target_isolation(
        session,
        expected_database_id=args.expected_database_id,
        forbidden_database_ids=args.forbid_database_id,
        require_no_tools=True,
    )


def run_import(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    csv_dir = Path(args.csv_dir).resolve()
    custom_file = Path(args.custom_t1_file).resolve() if args.custom_t1_file else None
    started = time.perf_counter()
    spec = build_graph_spec(csv_dir=csv_dir, scope=args.scope, custom_t1_file=custom_file)
    expected_counts = spec.counts()

    if not args.dry_run and args.confirm_replace != spec.snapshot_id:
        raise RuntimeError(
            "write confirmation mismatch; run --dry-run and pass "
            f"--confirm-replace {spec.snapshot_id}"
        )

    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {args.password_env}")
    driver = GraphDatabase.driver(args.uri, auth=(args.user, password))
    try:
        with driver.session(database=args.database, default_access_mode=WRITE_ACCESS) as session:
            target = guard(session, args)
            before = current_counts(session)
            if args.dry_run:
                result = {
                    "mode": "dry-run",
                    "target": target,
                    "scope": args.scope,
                    "snapshot_id": spec.snapshot_id,
                    "existing_managed_counts": before,
                    "would_delete": before,
                    "would_create": expected_counts,
                    "dangling_fk_count": len(spec.dangling_fk),
                    "dangling_fk_summary": aggregate_dangling(spec.dangling_fk),
                    "expected_graph_fingerprint": spec.graph_fingerprint(),
                }
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
                return result

            print(f"[guard] isolated database id={target['database_id']} name={target['database_name']}")
            for index, statement in enumerate(schema_statements(), start=1):
                guard(session, args)
                session.run(statement).consume()
                print(f"[schema] {index}/{len(schema_statements())}")
            session.run("CALL db.awaitIndexes($seconds)", seconds=300).consume()

            guard(session, args)
            unmanaged = session.run(
                "MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) "
                "AND coalesce(n.datagraph_managed, false) = false RETURN count(n) AS count",
                labels=sorted(DATAGRAPH_LABEL_KEYS),
            ).single()["count"]
            if unmanaged:
                raise RuntimeError(f"refusing to replace target containing {unmanaged} unmanaged data-label nodes")
            deleted = 0
            while True:
                guard(session, args)
                batch_deleted = int(
                    session.run(
                        "MATCH (n) WHERE n.datagraph_managed = true "
                        "AND any(label IN labels(n) WHERE label IN $labels) "
                        "WITH n LIMIT $batch_size DETACH DELETE n RETURN count(*) AS count",
                        labels=sorted(DATAGRAPH_LABEL_KEYS),
                        batch_size=args.delete_batch_size,
                    ).single()["count"]
                )
                deleted += batch_deleted
                if batch_deleted == 0:
                    break
                print(f"[replace] deleted managed data nodes={deleted}")
            print(f"[replace] deletion complete nodes={deleted}")

            nodes_by_label: Dict[str, List[Dict[str, Any]]] = {}
            for node in spec.nodes.values():
                nodes_by_label.setdefault(node["label"], []).append(node)
            for label in sorted(nodes_by_label):
                rows = sorted(nodes_by_label[label], key=lambda item: item["id"])
                batches = list(chunked(rows, args.batch_size))
                query = f"UNWIND $rows AS row CREATE (n:`{safe_identifier(label)}`) SET n = row.properties"
                for batch_index, batch in enumerate(batches, start=1):
                    guard(session, args)
                    session.run(query, rows=list(batch)).consume()
                    print(f"[nodes:{label}] batch {batch_index}/{len(batches)} rows={len(batch)}")

            relationship_groups: Dict[tuple[str, str, str, str, str, str, str], List[Dict[str, Any]]] = {}
            for rel in spec.relationships.values():
                key = (
                    rel["type"],
                    rel["start_label"],
                    rel["start_key_name"],
                    rel["end_label"],
                    rel["end_key_name"],
                    rel["start_id"].split(":", 1)[0],
                    rel["end_id"].split(":", 1)[0],
                )
                relationship_groups.setdefault(key, []).append(rel)
            for key in sorted(relationship_groups):
                rel_type, start_label, start_key_name, end_label, end_key_name, _, _ = key
                rows = sorted(relationship_groups[key], key=lambda item: item["id"])
                batches = list(chunked(rows, args.batch_size))
                query = (
                    f"UNWIND $rows AS row "
                    f"MATCH (a:`{safe_identifier(start_label)}` "
                    f"{{`{safe_identifier(start_key_name)}`: row.start_key_value}}) "
                    f"MATCH (b:`{safe_identifier(end_label)}` "
                    f"{{`{safe_identifier(end_key_name)}`: row.end_key_value}}) "
                    f"CREATE (a)-[r:`{safe_identifier(rel_type)}`]->(b) SET r = row.properties"
                )
                for batch_index, batch in enumerate(batches, start=1):
                    guard(session, args)
                    session.run(query, rows=list(batch)).consume()
                    print(f"[rels:{rel_type}:{start_label}->{end_label}] batch {batch_index}/{len(batches)} rows={len(batch)}")

            guard(session, args)
            actual_counts = current_counts(session)
            actual_fingerprint = actual_graph_fingerprint(session)
            if actual_counts != expected_counts:
                raise RuntimeError(f"post-import count mismatch: expected={expected_counts}, actual={actual_counts}")
            if actual_fingerprint != spec.graph_fingerprint():
                raise RuntimeError(
                    f"post-import fingerprint mismatch: expected={spec.graph_fingerprint()} actual={actual_fingerprint}"
                )
            schema = schema_inventory(session)
            components = neo4j_components(session)
    finally:
        driver.close()

    finished = time.perf_counter()
    stable_manifest: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "importer_version": IMPORTER_VERSION,
        "importer_script_sha256": script_sha256(),
        "git": git_state(project_root),
        "scope": args.scope,
        "custom_t1_file": str(custom_file) if custom_file else None,
        "snapshot_id": spec.snapshot_id,
        "target": {
            "database": args.database,
            "database_id": target["database_id"],
            "database_creation_date": target["creation_date"],
        },
        "sources": spec.source_inventory,
        "counts": actual_counts,
        "dangling_fk": {
            "strategy": "skip_edge_and_report",
            "count": len(spec.dangling_fk),
            "summary": aggregate_dangling(spec.dangling_fk),
            "records": spec.dangling_fk,
        },
        "excluded_scope_rows": spec.excluded_scope_rows,
        "graph_fingerprint": actual_fingerprint,
        "neo4j_components": components,
        "constraints": schema["constraints"],
        "indexes": schema["indexes"],
    }
    stable_manifest["reproducible_fingerprint"] = sha256_text(canonical_json(stable_manifest))
    manifest = {
        "run_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(finished - started, 6),
            "target_uri": args.uri,
        },
        "reproducible": stable_manifest,
    }
    manifest_dir = Path(args.manifest_dir).resolve()
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"import_manifest_{utc_timestamp()}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[done] manifest={manifest_path}")
    print(f"[done] graph_fingerprint={actual_fingerprint}")
    print(f"[done] reproducible_fingerprint={stable_manifest['reproducible_fingerprint']}")
    return {"manifest_path": str(manifest_path), "manifest": manifest}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--csv-dir", required=True)
    parser.add_argument("--scope", choices=["t1", "t1_plus_t11", "custom"], default="t1")
    parser.add_argument("--custom-t1-file")
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--expected-database-id", required=True)
    parser.add_argument("--forbid-database-id", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-replace")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--delete-batch-size", type=int, default=500)
    parser.add_argument("--manifest-dir", required=True)
    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.delete_batch_size <= 0:
        parser.error("--delete-batch-size must be positive")
    if not args.dry_run and not args.confirm_replace:
        parser.error("--confirm-replace is required for a write import")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    try:
        run_import(parse_args(argv if argv is not None else sys.argv[1:]))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
