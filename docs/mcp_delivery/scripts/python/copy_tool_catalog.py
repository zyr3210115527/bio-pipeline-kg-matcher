#!/usr/bin/env python3
"""Copy the exact tool-catalog subgraph from a read-only source to an isolated target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from neo4j import GraphDatabase, READ_ACCESS, WRITE_ACCESS


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from datagraph_common import canonical_json, chunked, safe_identifier  # noqa: E402


CATALOG_LABEL_KEYS: Dict[str, str] = {
    "tool_id": "tool_id",
    "io_slot": "slot_id",
    "artifact_type": "artifact_type",
    "function": "function",
    "format": "format",
}

CATALOG_RELATIONSHIPS = {
    "ALLOW_FORMAT",
    "HAS_FUNCTION",
    "HAS_INPUT_SLOT",
    "HAS_OUTPUT_SLOT",
    "HAS_STEP",
    "INPUT",
    "MANIFEST_AS",
    "NEXT",
    "OUTPUT",
    "PRODUCES",
    "REQUIRES",
}


def _password(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        raise RuntimeError(f"password environment variable is not set: {env_name}")
    return value


def _database_info(session: Any) -> Dict[str, str]:
    row = session.run("CALL db.info() YIELD id,name,creationDate RETURN id,name,creationDate").single()
    if row is None:
        raise RuntimeError("CALL db.info() returned no row")
    return {"id": str(row["id"]), "name": str(row["name"]), "creation_date": str(row["creationDate"])}


def _catalog_identity(labels: Sequence[str], properties: Mapping[str, Any]) -> str:
    matching = [label for label in CATALOG_LABEL_KEYS if label in labels]
    if len(matching) != 1:
        raise RuntimeError(f"catalog node has ambiguous canonical labels: {labels}")
    label = matching[0]
    key = CATALOG_LABEL_KEYS[label]
    value = properties.get(key)
    if value is None or str(value) == "":
        raise RuntimeError(f"catalog node has empty key {key}: {properties}")
    return f"{label}:{value}"


def load_catalog(session: Any) -> Dict[str, Any]:
    labels = sorted(CATALOG_LABEL_KEYS)
    nodes: Dict[str, Dict[str, Any]] = {}
    result = session.run(
        "MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) "
        "RETURN labels(n) AS labels, properties(n) AS properties",
        labels=labels,
    )
    for row in result:
        node_labels = sorted(str(label) for label in row["labels"])
        properties = dict(row["properties"])
        identity = _catalog_identity(node_labels, properties)
        if identity in nodes:
            raise RuntimeError(f"duplicate catalog identity: {identity}")
        nodes[identity] = {
            "identity": identity,
            "labels": node_labels,
            "properties": properties,
        }

    relationships: List[Dict[str, Any]] = []
    result = session.run(
        "MATCH (a)-[r]->(b) "
        "WHERE type(r) IN $types "
        "AND any(label IN labels(a) WHERE label IN $labels) "
        "AND any(label IN labels(b) WHERE label IN $labels) "
        "RETURN labels(a) AS start_labels, properties(a) AS start_properties, "
        "type(r) AS type, properties(r) AS properties, "
        "labels(b) AS end_labels, properties(b) AS end_properties",
        types=sorted(CATALOG_RELATIONSHIPS),
        labels=labels,
    )
    for row in result:
        start = _catalog_identity(row["start_labels"], row["start_properties"])
        end = _catalog_identity(row["end_labels"], row["end_properties"])
        relationships.append(
            {
                "type": str(row["type"]),
                "start": start,
                "end": end,
                "properties": dict(row["properties"]),
            }
        )
    relationships.sort(
        key=lambda item: (
            item["type"],
            item["start"],
            item["end"],
            canonical_json(item["properties"]),
        )
    )
    return {
        "nodes": [nodes[key] for key in sorted(nodes)],
        "relationships": relationships,
    }


def catalog_fingerprint(catalog: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(catalog).encode("utf-8")).hexdigest()


def catalog_counts(catalog: Mapping[str, Any]) -> Dict[str, Any]:
    labels: Dict[str, int] = defaultdict(int)
    relationships: Dict[str, int] = defaultdict(int)
    for node in catalog["nodes"]:
        canonical = node["identity"].split(":", 1)[0]
        labels[canonical] += 1
    for relationship in catalog["relationships"]:
        relationships[relationship["type"]] += 1
    return {
        "nodes": len(catalog["nodes"]),
        "relationships": len(catalog["relationships"]),
        "labels": dict(sorted(labels.items())),
        "relationship_types": dict(sorted(relationships.items())),
    }


def _assert_source(session: Any, expected_id: str) -> Dict[str, str]:
    info = _database_info(session)
    if info["id"] != expected_id:
        raise RuntimeError(f"source database id mismatch: expected {expected_id}, got {info['id']}")
    return info


def _assert_target(session: Any, expected_id: str, forbidden_ids: Sequence[str]) -> Dict[str, str]:
    info = _database_info(session)
    if info["id"] != expected_id:
        raise RuntimeError(f"target database id mismatch: expected {expected_id}, got {info['id']}")
    if info["id"] in set(forbidden_ids):
        raise RuntimeError(f"refusing forbidden target database id: {info['id']}")
    data_nodes = int(
        session.run("MATCH (n) WHERE n.datagraph_managed = true RETURN count(n) AS count").single()["count"]
    )
    if data_nodes == 0:
        raise RuntimeError("target has no managed data graph; refusing catalog copy")
    cross_domain = int(
        session.run(
            "MATCH (a)-[r]-(b) "
            "WHERE any(label IN labels(a) WHERE label IN $labels) "
            "AND NOT any(label IN labels(b) WHERE label IN $labels) "
            "RETURN count(r) AS count",
            labels=sorted(CATALOG_LABEL_KEYS),
        ).single()["count"]
    )
    if cross_domain:
        raise RuntimeError(f"target catalog has {cross_domain} cross-domain relationships; refusing replacement")
    return {**info, "managed_data_nodes": str(data_nodes)}


def copy_catalog(args: argparse.Namespace) -> Dict[str, Any]:
    source_driver = GraphDatabase.driver(
        args.source_uri,
        auth=(args.source_user, _password(args.source_password_env)),
    )
    target_driver = GraphDatabase.driver(
        args.target_uri,
        auth=(args.target_user, _password(args.target_password_env)),
    )
    try:
        with source_driver.session(database=args.source_database, default_access_mode=READ_ACCESS) as session:
            source_info = _assert_source(session, args.expected_source_database_id)
            source_catalog = load_catalog(session)
        with target_driver.session(database=args.target_database, default_access_mode=WRITE_ACCESS) as session:
            target_info = _assert_target(
                session,
                args.expected_target_database_id,
                args.forbid_target_database_id,
            )
            before = load_catalog(session)
            summary = {
                "mode": "dry-run" if args.dry_run else "apply",
                "source": source_info,
                "target": target_info,
                "source_counts": catalog_counts(source_catalog),
                "target_counts_before": catalog_counts(before),
                "source_fingerprint": catalog_fingerprint(source_catalog),
            }
            if args.dry_run:
                return summary
            if args.confirm_fingerprint != summary["source_fingerprint"]:
                raise RuntimeError(
                    "catalog confirmation mismatch; run --dry-run and pass "
                    f"--confirm-fingerprint {summary['source_fingerprint']}"
                )

            _assert_target(session, args.expected_target_database_id, args.forbid_target_database_id)
            session.run(
                "MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) "
                "WITH n LIMIT 10000 DETACH DELETE n",
                labels=sorted(CATALOG_LABEL_KEYS),
            ).consume()

            grouped_nodes: Dict[Tuple[str, ...], List[Dict[str, Any]]] = defaultdict(list)
            for node in source_catalog["nodes"]:
                grouped_nodes[tuple(node["labels"])].append(node)
            for node_labels in sorted(grouped_nodes):
                label_clause = "".join(f":`{safe_identifier(label)}`" for label in node_labels)
                query = (
                    f"UNWIND $rows AS row CREATE (n{label_clause}) "
                    "SET n = row.properties, n.__catalog_copy_id = row.identity"
                )
                for batch in chunked(sorted(grouped_nodes[node_labels], key=lambda item: item["identity"]), args.batch_size):
                    _assert_target(session, args.expected_target_database_id, args.forbid_target_database_id)
                    session.run(query, rows=list(batch)).consume()

            grouped_relationships: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for relationship in source_catalog["relationships"]:
                grouped_relationships[relationship["type"]].append(relationship)
            for rel_type in sorted(grouped_relationships):
                query = (
                    "UNWIND $rows AS row "
                    "MATCH (a {__catalog_copy_id: row.start}) "
                    "MATCH (b {__catalog_copy_id: row.end}) "
                    f"CREATE (a)-[r:`{safe_identifier(rel_type)}`]->(b) SET r = row.properties"
                )
                for batch in chunked(grouped_relationships[rel_type], args.batch_size):
                    _assert_target(session, args.expected_target_database_id, args.forbid_target_database_id)
                    session.run(query, rows=list(batch)).consume()
            session.run(
                "MATCH (n) WHERE n.__catalog_copy_id IS NOT NULL REMOVE n.__catalog_copy_id"
            ).consume()

            after = load_catalog(session)
            summary["target_counts_after"] = catalog_counts(after)
            summary["target_fingerprint_after"] = catalog_fingerprint(after)
            summary["equal"] = source_catalog == after
            if not summary["equal"]:
                raise RuntimeError("post-copy catalog differs from source")
            return summary
    finally:
        source_driver.close()
        target_driver.close()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-uri", required=True)
    parser.add_argument("--source-database", required=True)
    parser.add_argument("--source-user", required=True)
    parser.add_argument("--source-password-env", required=True)
    parser.add_argument("--expected-source-database-id", required=True)
    parser.add_argument("--target-uri", required=True)
    parser.add_argument("--target-database", required=True)
    parser.add_argument("--target-user", required=True)
    parser.add_argument("--target-password-env", required=True)
    parser.add_argument("--expected-target-database-id", required=True)
    parser.add_argument("--forbid-target-database-id", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-fingerprint")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args(argv)
    if not args.dry_run and not args.confirm_fingerprint:
        parser.error("--confirm-fingerprint is required for apply")
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = copy_catalog(parse_args(argv if argv is not None else sys.argv[1:]))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
