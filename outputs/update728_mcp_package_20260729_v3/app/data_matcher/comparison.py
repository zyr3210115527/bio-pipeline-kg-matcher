"""Stable, field-level comparison for CSV and Neo4j matcher results."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple


SCHEMA_VERSION = "data-matcher-diff/v1"
LIST_SECTIONS = (
    "cohort_candidates",
    "file_candidates",
    "backup_file_candidates",
    "data_combinations",
)
_SIZE_SUFFIX = re.compile(r"\s*\(\d+\s+bytes\)\s*$")


def _scalar(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return _SIZE_SUFFIX.sub("", value).strip()
    return value


def normalize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): normalize(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return _scalar(value)


def file_identity(item: Mapping[str, Any]) -> Tuple[Any, ...]:
    source = _scalar(item.get("source"))
    if source == "T2":
        return ("T2", _scalar(item.get("t2_id")) or _scalar(item.get("file_path")))
    return (
        "T1",
        _scalar(item.get("study_accession")),
        _scalar(item.get("run_accession")),
        _scalar(item.get("read_pair")),
    )


def cohort_identity(item: Mapping[str, Any]) -> Tuple[Any, ...]:
    return (_scalar(item.get("study_accession")),)


def combination_identity(item: Mapping[str, Any]) -> Tuple[Any, ...]:
    files = tuple(file_identity(value) for value in item.get("files") or [])
    return (
        _scalar(item.get("pipeline_id")),
        _scalar(item.get("study_accession")),
        _scalar(item.get("individual_accession")),
        _scalar(item.get("kind")),
        files,
    )


def _identity_json(identity: Tuple[Any, ...]) -> List[Any]:
    return json.loads(json.dumps(identity, ensure_ascii=False))


def _index(
    values: Sequence[Mapping[str, Any]],
    identity_fn: Callable[[Mapping[str, Any]], Tuple[Any, ...]],
) -> Tuple[Dict[Tuple[Any, ...], Mapping[str, Any]], List[Tuple[Any, ...]]]:
    indexed: Dict[Tuple[Any, ...], Mapping[str, Any]] = {}
    order: List[Tuple[Any, ...]] = []
    for item in values:
        identity = identity_fn(item)
        if identity in indexed:
            raise ValueError(f"duplicate matcher identity: {identity!r}")
        indexed[identity] = item
        order.append(identity)
    return indexed, order


def _field_diffs(
    identity: Tuple[Any, ...],
    csv_value: Mapping[str, Any],
    neo4j_value: Mapping[str, Any],
) -> Iterable[Dict[str, Any]]:
    csv_norm = normalize(csv_value)
    neo_norm = normalize(neo4j_value)
    for field in sorted(set(csv_norm) | set(neo_norm)):
        if csv_norm.get(field) != neo_norm.get(field):
            yield {
                "identity": _identity_json(identity),
                "field": field,
                "csv": csv_norm.get(field),
                "neo4j": neo_norm.get(field),
            }


def compare_section(
    csv_values: Sequence[Mapping[str, Any]],
    neo4j_values: Sequence[Mapping[str, Any]],
    identity_fn: Callable[[Mapping[str, Any]], Tuple[Any, ...]],
) -> Dict[str, Any]:
    csv_index, csv_order = _index(csv_values, identity_fn)
    neo_index, neo_order = _index(neo4j_values, identity_fn)
    only_csv = [identity for identity in csv_order if identity not in neo_index]
    only_neo4j = [identity for identity in neo_order if identity not in csv_index]
    common = [identity for identity in csv_order if identity in neo_index]
    field_diffs = [
        diff
        for identity in common
        for diff in _field_diffs(identity, csv_index[identity], neo_index[identity])
    ]
    csv_common_order = [identity for identity in csv_order if identity in neo_index]
    neo_common_order = [identity for identity in neo_order if identity in csv_index]
    rank_diffs = []
    if csv_common_order != neo_common_order:
        neo_ranks = {identity: rank for rank, identity in enumerate(neo_common_order)}
        rank_diffs = [
            {
                "identity": _identity_json(identity),
                "csv_rank": rank,
                "neo4j_rank": neo_ranks[identity],
            }
            for rank, identity in enumerate(csv_common_order)
            if neo_ranks[identity] != rank
        ]
    return {
        "csv_count": len(csv_values),
        "neo4j_count": len(neo4j_values),
        "only_csv": [_identity_json(value) for value in only_csv],
        "only_neo4j": [_identity_json(value) for value in only_neo4j],
        "field_diffs": field_diffs,
        "rank_diffs": rank_diffs,
    }


def compare_results(
    case_id: str,
    intent: Mapping[str, Any],
    pipeline_ids: Sequence[str],
    csv_result: Mapping[str, Any],
    neo4j_result: Mapping[str, Any],
    timing_ms: Mapping[str, float] | None = None,
) -> Dict[str, Any]:
    identity_functions = {
        "cohort_candidates": cohort_identity,
        "file_candidates": file_identity,
        "backup_file_candidates": file_identity,
        "data_combinations": combination_identity,
    }
    sections = {
        section: compare_section(
            csv_result.get(section) or [],
            neo4j_result.get(section) or [],
            identity_functions[section],
        )
        for section in LIST_SECTIONS
    }
    scalar_diffs = []
    for field in ("data_schema", "query_constraints"):
        csv_value = normalize(csv_result.get(field))
        neo_value = normalize(neo4j_result.get(field))
        if csv_value != neo_value:
            scalar_diffs.append({"field": field, "csv": csv_value, "neo4j": neo_value})
    material_count = len(scalar_diffs) + sum(
        len(section[part])
        for section in sections.values()
        for part in ("only_csv", "only_neo4j", "field_diffs", "rank_diffs")
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "intent": dict(intent),
        "pipeline_ids": list(pipeline_ids),
        "timing_ms": {key: round(float(value), 3) for key, value in (timing_ms or {}).items()},
        "sections": sections,
        "scalar_diffs": scalar_diffs,
        "material_diff_count": material_count,
        "known_representation_diff_count": 0,
    }


def load_allowlist(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    for rule in value.get("rules") or []:
        if not rule.get("owner") or not rule.get("reason"):
            raise ValueError(f"allowlist rule lacks owner/reason: {rule.get('id')}")
    return value
