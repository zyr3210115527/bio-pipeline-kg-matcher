#!/usr/bin/env python3
"""Compare six deterministic full composer results under CSV and Neo4j matchers."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data_matcher.comparison import normalize  # noqa: E402
from data_matcher.factory import build_data_matcher  # noqa: E402
from pipeline_router import PipelineRouter  # noqa: E402
from runtime_config import initialize_runtime  # noqa: E402
from workflow_composer import (  # noqa: E402
    Neo4jPipelineCatalog,
    RegisteredMethodCatalog,
    WorkflowComposer,
)


def differences(csv: Any, neo4j: Any, path: str = "$") -> List[Dict[str, Any]]:
    csv = normalize(csv)
    neo4j = normalize(neo4j)
    if isinstance(csv, dict) and isinstance(neo4j, dict):
        return [
            diff
            for key in sorted(set(csv) | set(neo4j))
            for diff in differences(csv.get(key), neo4j.get(key), f"{path}.{key}")
        ]
    if isinstance(csv, list) and isinstance(neo4j, list):
        output: List[Dict[str, Any]] = []
        if len(csv) != len(neo4j):
            output.append({"path": path + ".length", "csv": len(csv), "neo4j": len(neo4j)})
        for index, (csv_item, neo4j_item) in enumerate(zip(csv, neo4j)):
            output.extend(differences(csv_item, neo4j_item, f"{path}[{index}]"))
        return output
    if csv != neo4j:
        return [{"path": path, "csv": csv, "neo4j": neo4j}]
    return []


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", default=str(ROOT / "docs/demo_queries_six_check.json"))
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def composer(mode: str, catalog: RegisteredMethodCatalog) -> WorkflowComposer:
    router = PipelineRouter(Neo4jPipelineCatalog(catalog), matcher=build_data_matcher(mode))
    return WorkflowComposer(router=router, method_catalog=catalog)


def main(argv: Sequence[str] | None = None) -> int:
    initialize_runtime()
    args = parse_args(argv if argv is not None else sys.argv[1:])
    os.environ["FORCE_RULE"] = "1"
    queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    catalog = RegisteredMethodCatalog()
    csv_composer = composer("csv", catalog)
    neo4j_composer = composer("neo4j", catalog)
    cases = []
    for index, item in enumerate(queries):
        query = str(item.get("query") or "")
        started = time.perf_counter()
        csv_result = csv_composer.plan(query, top_k=5)
        csv_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        neo4j_result = neo4j_composer.plan(query, top_k=5)
        neo4j_ms = (time.perf_counter() - started) * 1000
        field_diffs = differences(csv_result, neo4j_result)
        cases.append({
            "case_id": item.get("query_key") or f"query-{index + 1}",
            "query": query,
            "timing_ms": {"csv": round(csv_ms, 3), "neo4j": round(neo4j_ms, 3)},
            "field_diffs": field_diffs,
            "material_diff_count": len(field_diffs),
            "csv_status": csv_result.get("selection_status"),
            "neo4j_status": neo4j_result.get("selection_status"),
        })
    report = {
        "schema_version": "demo-mode-comparison/v1",
        "case_count": len(cases),
        "material_diff_count": sum(item["material_diff_count"] for item in cases),
        "cases": cases,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_count", "material_diff_count")}, ensure_ascii=False))
    print(f"report={output}")
    return 0 if report["material_diff_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
