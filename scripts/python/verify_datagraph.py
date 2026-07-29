#!/usr/bin/env python3
"""Verify an isolated Neo4j data graph against its CSV snapshot at value level."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple

from neo4j import GraphDatabase, READ_ACCESS

from datagraph_common import (
    DATAGRAPH_LABEL_KEYS,
    SCHEMA_VERSION,
    aggregate_dangling,
    assert_target_isolation,
    build_graph_spec,
    canonical_json,
    sha256_text,
)


def load_allowlist(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "datagraph-representation-allowlist/v1":
        raise ValueError(f"unsupported allowlist schema: {payload.get('schema_version')}")
    return payload


def normalize_known(value: Any, label: str, prop: str, allowlist: Mapping[str, Any]) -> Tuple[Any, List[str]]:
    current = value
    applied: List[str] = []
    for rule in allowlist.get("rules", []):
        if not rule.get("enabled", False):
            continue
        labels = set(rule.get("labels") or [])
        properties = set(rule.get("properties") or [])
        if labels and label not in labels:
            continue
        if properties and prop not in properties:
            continue
        kind = rule.get("kind")
        if kind == "empty_string_null" and current is None:
            current = ""
            applied.append(str(rule["id"]))
        elif kind == "regex_sub" and isinstance(current, str):
            changed = re.sub(str(rule["pattern"]), str(rule.get("replacement", "")), current)
            if changed != current:
                current = changed
                applied.append(str(rule["id"]))
    return current, applied


def load_actual_graph(session: Any) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    nodes: Dict[str, Dict[str, Any]] = {}
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
        if node_id in nodes:
            raise RuntimeError(f"duplicate actual node id: {node_id}")
        nodes[node_id] = {
            "id": node_id,
            "label": label,
            "key_name": key_name,
            "key_value": key_value,
            "properties": props,
        }

    relationships: Dict[str, Dict[str, Any]] = {}
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
        rel_id = f"{rel_type}|{start_id}|{end_id}"
        if rel_id in relationships:
            raise RuntimeError(f"duplicate actual relationship id: {rel_id}")
        relationships[rel_id] = {
            "id": rel_id,
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
    return nodes, relationships


def counts(nodes: Mapping[str, Mapping[str, Any]], relationships: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, int]]:
    label_counts = Counter(node["label"] for node in nodes.values())
    rel_counts = Counter(rel["type"] for rel in relationships.values())
    return {
        "labels": dict(sorted(label_counts.items())),
        "relationships": dict(sorted(rel_counts.items())),
    }


def nonempty(value: Any) -> bool:
    return value is not None and value != ""


def field_coverage(nodes: Mapping[str, Mapping[str, Any]]) -> Dict[str, Dict[str, Dict[str, int]]]:
    output: Dict[str, Dict[str, Dict[str, int]]] = {}
    labels = sorted({node["label"] for node in nodes.values()})
    for label in labels:
        label_nodes = [node for node in nodes.values() if node["label"] == label]
        props = sorted({prop for node in label_nodes for prop in node["properties"]})
        output[label] = {
            prop: {
                "nonempty": sum(nonempty(node["properties"].get(prop)) for node in label_nodes),
                "total": len(label_nodes),
            }
            for prop in props
        }
    return output


def compare_properties(
    expected_nodes: Mapping[str, Mapping[str, Any]],
    actual_nodes: Mapping[str, Mapping[str, Any]],
    expected_relationships: Mapping[str, Mapping[str, Any]],
    actual_relationships: Mapping[str, Mapping[str, Any]],
    allowlist: Mapping[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    material: List[Dict[str, Any]] = []
    known: List[Dict[str, Any]] = []

    def compare_entity(kind: str, entity_id: str, expected: Mapping[str, Any], actual: Mapping[str, Any], label: str) -> None:
        props = sorted(set(expected) | set(actual))
        for prop in props:
            left = expected.get(prop)
            right = actual.get(prop)
            if left == right:
                continue
            norm_left, left_rules = normalize_known(left, label, prop, allowlist)
            norm_right, right_rules = normalize_known(right, label, prop, allowlist)
            diff = {
                "kind": kind,
                "identity": entity_id,
                "field": prop,
                "expected": left,
                "actual": right,
            }
            if norm_left == norm_right and (left_rules or right_rules):
                diff["allowlist_rules"] = sorted(set(left_rules + right_rules))
                known.append(diff)
            else:
                material.append(diff)

    expected_ids = set(expected_nodes)
    actual_ids = set(actual_nodes)
    for node_id in sorted(expected_ids - actual_ids):
        material.append({"kind": "node_missing", "identity": node_id})
    for node_id in sorted(actual_ids - expected_ids):
        material.append({"kind": "node_extra", "identity": node_id})
    for node_id in sorted(expected_ids & actual_ids):
        compare_entity(
            "node_field",
            node_id,
            expected_nodes[node_id]["properties"],
            actual_nodes[node_id]["properties"],
            expected_nodes[node_id]["label"],
        )

    expected_rel_ids = set(expected_relationships)
    actual_rel_ids = set(actual_relationships)
    for rel_id in sorted(expected_rel_ids - actual_rel_ids):
        material.append({"kind": "relationship_missing", "identity": rel_id})
    for rel_id in sorted(actual_rel_ids - expected_rel_ids):
        material.append({"kind": "relationship_extra", "identity": rel_id})
    for rel_id in sorted(expected_rel_ids & actual_rel_ids):
        compare_entity(
            "relationship_field",
            rel_id,
            expected_relationships[rel_id]["properties"],
            actual_relationships[rel_id]["properties"],
            expected_relationships[rel_id]["type"],
        )
    return material, known


def roundtrip_rows(
    nodes: Mapping[str, Mapping[str, Any]],
    relationships: Mapping[str, Mapping[str, Any]],
    manifest_dangling: Sequence[Mapping[str, Any]],
) -> Dict[str, List[str]]:
    output: Dict[str, List[str]] = {}

    def add(table: str, row_json: str) -> None:
        if table and row_json:
            output.setdefault(table, []).append(row_json)

    for node in nodes.values():
        props = node["properties"]
        add(str(props.get("source_table", "")), str(props.get("source_row_json", "")))
        if node["label"] == "t1":
            add("entities/T1.csv", str(props.get("normalized_source_row_json", "")))
            add("T11.csv", str(props.get("legacy_source_row_json", "")))
    for rel in relationships.values():
        props = rel["properties"]
        if not props.get("derived", False):
            add(str(props.get("source_table", "")), str(props.get("source_row_json", "")))
    for dangling in manifest_dangling:
        add(str(dangling.get("source_table", "")), str(dangling.get("source_row_json", "")))
    return {table: sorted(rows) for table, rows in sorted(output.items())}


def compare_roundtrip(expected: Mapping[str, Sequence[str]], actual: Mapping[str, Sequence[str]]) -> List[Dict[str, Any]]:
    diffs: List[Dict[str, Any]] = []
    for table in sorted(set(expected) | set(actual)):
        expected_counter = Counter(expected.get(table, []))
        actual_counter = Counter(actual.get(table, []))
        if expected_counter == actual_counter:
            continue
        missing = list((expected_counter - actual_counter).elements())
        extra = list((actual_counter - expected_counter).elements())
        diffs.append(
            {
                "table": table,
                "expected_rows": sum(expected_counter.values()),
                "actual_rows": sum(actual_counter.values()),
                "missing_count": len(missing),
                "extra_count": len(extra),
                "missing_examples": missing[:5],
                "extra_examples": extra[:5],
            }
        )
    return diffs


def deterministic_samples(
    expected_nodes: Mapping[str, Mapping[str, Any]],
    actual_nodes: Mapping[str, Mapping[str, Any]],
    expected_roundtrip: Mapping[str, Sequence[str]],
    actual_roundtrip: Mapping[str, Sequence[str]],
    sample_size: int,
    seed: int,
) -> Dict[str, Any]:
    rng = random.Random(seed)
    table_results: Dict[str, Any] = {}
    for table in sorted(expected_roundtrip):
        rows = sorted(expected_roundtrip[table])
        chosen = rows if len(rows) <= sample_size else rng.sample(rows, sample_size)
        actual_counter = Counter(actual_roundtrip.get(table, []))
        missing = [row for row in chosen if actual_counter[row] <= 0]
        table_results[table] = {
            "available": len(rows),
            "sampled": len(chosen),
            "missing": len(missing),
        }

    special_results: Dict[str, Any] = {}
    for study in ["HRA000021", "HRA000122", "HRA000321", "HRA000873"]:
        candidates = sorted(
            node_id
            for node_id, node in expected_nodes.items()
            if node["properties"].get("study_accession") == study
        )
        chosen = candidates[:20]
        missing = [node_id for node_id in chosen if node_id not in actual_nodes]
        special_results[study] = {
            "available_in_authoritative_scope": len(candidates),
            "sampled": len(chosen),
            "required": 20,
            "shortfall": max(0, 20 - len(chosen)),
            "missing": len(missing),
        }
    return {"seed": seed, "tables": table_results, "special_studies": special_results}


def primary_key_checks(session: Any) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    for label, key in sorted(DATAGRAPH_LABEL_KEYS.items()):
        row = session.run(
            f"MATCH (n:`{label}`) WHERE n.datagraph_managed = true "
            f"RETURN count(n) AS total, count(DISTINCT n.`{key}`) AS distinct_count, "
            f"sum(CASE WHEN n.`{key}` IS NULL OR toString(n.`{key}`) = '' THEN 1 ELSE 0 END) AS empty_count"
        ).single()
        checks.append(
            {
                "label": label,
                "key": key,
                "total": int(row["total"]),
                "distinct": int(row["distinct_count"]),
                "empty": int(row["empty_count"]),
                "ok": int(row["total"]) == int(row["distinct_count"]) and int(row["empty_count"]) == 0,
            }
        )
    return checks


def markdown_report(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 数据图验证报告",
        "",
        f"生成时间：{report['generated_at']}",
        f"目标 database：`{report['target']['database']}` (`{report['target']['database_id']}`)",
        f"scope：`{report['scope']}`；snapshot：`{report['snapshot_id']}`",
        "",
        "## 结论",
        "",
        ("✅" if summary["ok"] else "❌")
        + f" 实质差异 {summary['material_difference_count']}；已知表示差异 {summary['known_representation_difference_count']}。",
        "",
        "## 六层验证",
        "",
    ]
    for layer in report["layers"]:
        icon = "✅" if layer["ok"] else "❌"
        lines.append(f"- {icon} **{layer['name']}**：{layer['summary']}")
    lines.extend(
        [
            "",
            "## 悬空外键",
            "",
            f"策略：`skip_edge_and_report`；共 {report['dangling_fk']['count']} 条。",
            "",
            "| 来源 | 关系 | 缺失端 | 数量 |",
            "|---|---|---|---:|",
        ]
    )
    for row in report["dangling_fk"]["summary"]:
        lines.append(
            f"| `{row['source_table']}` | `{row['relationship_type']}` | `{','.join(row['missing'])}` | {row['count']} |"
        )
    lines.extend(["", "## 特殊 study 抽样", "", "| study | 权威范围可用 | 已检查 | 目标 | 短缺 |", "|---|---:|---:|---:|---:|"])
    for study, row in report["value_sampling"]["special_studies"].items():
        lines.append(
            f"| {study} | {row['available_in_authoritative_scope']} | {row['sampled']} | {row['required']} | {row['shortfall']} |"
        )
    shortfall_studies = [
        study
        for study, row in report["value_sampling"]["special_studies"].items()
        if row["shortfall"]
    ]
    lines.extend(
        [
            "",
            (
                f"权威范围内不足 20 条可按 study 标识的记录：{', '.join(shortfall_studies)}；"
                "这些 study 的全部可用记录均已检查。"
                if shortfall_studies
                else "四个指定 study 均已完成 20 条确定性抽样。"
            ),
            "HRA000321 生产图额外 T1 的负向对照放在生产/隔离对照报告中完成。",
            "",
            "## 差异",
            "",
            f"实质差异：{summary['material_difference_count']}；已知表示差异：{summary['known_representation_difference_count']}。",
        ]
    )
    if report["material_differences"]:
        lines.extend(["", "```json", json.dumps(report["material_differences"][:20], ensure_ascii=False, indent=2), "```"])
    lines.extend(
        [
            "",
            "## 判断",
            "",
            "### 导入过程中遇到的最大意外",
            "",
            "待实际导入完成后补充。",
            "",
            "### CSV 数据质量问题",
            "",
            "待实际导入完成后补充。",
            "",
            "### 非确定性来源",
            "",
            "待两次导入对照完成后补充。",
            "",
            "### 能否直接作为打包 gate",
            "",
            "待恢复演练后补充。",
            "",
            "### 下一轮 Neo4j matcher 风险",
            "",
            "待实际查询验证后补充。",
            "",
            "### 其他关键问题",
            "",
            "待实际导入完成后补充。",
            "",
        ]
    )
    return "\n".join(lines)


def verify(args: argparse.Namespace) -> Dict[str, Any]:
    started = time.perf_counter()
    csv_dir = Path(args.csv_dir).resolve()
    custom_file = Path(args.custom_t1_file).resolve() if args.custom_t1_file else None
    spec = build_graph_spec(csv_dir, args.scope, custom_file)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    reproducible_manifest = manifest["reproducible"]
    allowlist = load_allowlist(Path(args.allowlist))
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is not set: {args.password_env}")

    driver = GraphDatabase.driver(args.uri, auth=(args.user, password))
    try:
        with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
            target = assert_target_isolation(
                session,
                args.expected_database_id,
                args.forbid_database_id,
                require_no_tools=not args.allow_tool_catalog,
            )
            actual_nodes, actual_relationships = load_actual_graph(session)
            pk_checks = primary_key_checks(session)
    finally:
        driver.close()

    expected_counts = spec.counts()
    actual_counts = counts(actual_nodes, actual_relationships)
    material, known = compare_properties(
        spec.nodes,
        actual_nodes,
        spec.relationships,
        actual_relationships,
        allowlist,
    )
    if expected_counts != actual_counts:
        material.append({"kind": "count_mismatch", "expected": expected_counts, "actual": actual_counts})

    expected_coverage = field_coverage(spec.nodes)
    actual_coverage = field_coverage(actual_nodes)
    if expected_coverage != actual_coverage:
        material.append({"kind": "field_coverage_mismatch"})

    expected_dangling = spec.dangling_fk
    manifest_dangling = reproducible_manifest["dangling_fk"]["records"]
    if expected_dangling != manifest_dangling:
        material.append(
            {
                "kind": "dangling_manifest_mismatch",
                "expected_count": len(expected_dangling),
                "manifest_count": len(manifest_dangling),
            }
        )
    if reproducible_manifest.get("snapshot_id") != spec.snapshot_id:
        material.append(
            {
                "kind": "snapshot_mismatch",
                "expected": spec.snapshot_id,
                "manifest": reproducible_manifest.get("snapshot_id"),
            }
        )

    actual_roundtrip = roundtrip_rows(actual_nodes, actual_relationships, manifest_dangling)
    roundtrip_diffs = compare_roundtrip(spec.roundtrip_expected, actual_roundtrip)
    for diff in roundtrip_diffs:
        material.append({"kind": "roundtrip_csv_mismatch", **diff})

    value_sampling = deterministic_samples(
        spec.nodes,
        actual_nodes,
        spec.roundtrip_expected,
        actual_roundtrip,
        args.sample_size,
        args.random_seed,
    )
    sampling_missing = sum(row["missing"] for row in value_sampling["tables"].values())
    if sampling_missing:
        material.append({"kind": "sample_value_mismatch", "missing": sampling_missing})

    invalid_pk = [check for check in pk_checks if not check["ok"]]
    if invalid_pk:
        material.append({"kind": "primary_key_violation", "checks": invalid_pk})

    expected_graph_fingerprint = spec.graph_fingerprint()
    actual_graph_payload = {
        "nodes": [actual_nodes[key] for key in sorted(actual_nodes)],
        "relationships": [actual_relationships[key] for key in sorted(actual_relationships)],
    }
    actual_graph_fingerprint = sha256_text(canonical_json(actual_graph_payload))
    if expected_graph_fingerprint != actual_graph_fingerprint:
        material.append(
            {
                "kind": "graph_fingerprint_mismatch",
                "expected": expected_graph_fingerprint,
                "actual": actual_graph_fingerprint,
            }
        )

    layers = [
        {
            "name": "计数",
            "ok": expected_counts == actual_counts,
            "summary": f"expected={expected_counts}; actual={actual_counts}",
        },
        {
            "name": "字段覆盖与逐值比较",
            "ok": expected_coverage == actual_coverage and not any(d["kind"] in {"node_field", "relationship_field"} for d in material),
            "summary": f"labels={len(expected_coverage)}; known_representation_diffs={len(known)}",
        },
        {
            "name": "主键唯一性",
            "ok": not invalid_pk,
            "summary": f"checked_labels={len(pk_checks)}; violations={len(invalid_pk)}",
        },
        {
            "name": "关系完整性与悬空外键",
            "ok": expected_dangling == manifest_dangling,
            "summary": f"materialized={len(actual_relationships)}; explicitly_skipped={len(expected_dangling)}",
        },
        {
            "name": "确定性值级抽样",
            "ok": sampling_missing == 0,
            "summary": f"tables={len(value_sampling['tables'])}; sampled_missing={sampling_missing}",
        },
        {
            "name": "CSV 往返全量 diff",
            "ok": not roundtrip_diffs,
            "summary": f"tables={len(spec.roundtrip_expected)}; differing_tables={len(roundtrip_diffs)}",
        },
    ]
    report: Dict[str, Any] = {
        "schema_version": "datagraph-verification/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.perf_counter() - started, 6),
        "target": {"uri": args.uri, "database": args.database, **target},
        "scope": args.scope,
        "snapshot_id": spec.snapshot_id,
        "manifest": str(Path(args.manifest).resolve()),
        "allowlist": str(Path(args.allowlist).resolve()),
        "summary": {
            "ok": not material,
            "material_difference_count": len(material),
            "known_representation_difference_count": len(known),
        },
        "layers": layers,
        "counts": {"expected": expected_counts, "actual": actual_counts},
        "field_coverage": {"expected": expected_coverage, "actual": actual_coverage},
        "primary_keys": pk_checks,
        "dangling_fk": {
            "count": len(expected_dangling),
            "summary": aggregate_dangling(expected_dangling),
        },
        "value_sampling": value_sampling,
        "roundtrip": {
            "source_tables": {table: len(rows) for table, rows in sorted(spec.roundtrip_expected.items())},
            "differences": roundtrip_diffs,
        },
        "graph_fingerprint": {
            "expected": expected_graph_fingerprint,
            "actual": actual_graph_fingerprint,
        },
        "material_differences": material,
        "known_representation_differences": known,
    }
    output_json = Path(args.output_json).resolve()
    output_markdown = Path(args.output_markdown).resolve()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_markdown.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    for layer in layers:
        print(("PASS" if layer["ok"] else "FAIL") + f" {layer['name']}: {layer['summary']}")
    print(f"JSON report: {output_json}")
    print(f"Markdown report: {output_markdown}")
    return report


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", required=True)
    parser.add_argument("--scope", choices=["t1", "t1_plus_t11", "custom"], default="t1")
    parser.add_argument("--custom-t1-file")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--allowlist", required=True)
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password-env", required=True)
    parser.add_argument("--expected-database-id", required=True)
    parser.add_argument("--forbid-database-id", action="append", required=True)
    parser.add_argument(
        "--allow-tool-catalog",
        action="store_true",
        help="allow a co-located tool catalog while verifying only datagraph_managed entities",
    )
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--random-seed", type=int, default=20260724)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        report = verify(parse_args(argv if argv is not None else sys.argv[1:]))
        return 0 if report["summary"]["ok"] else 2
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
