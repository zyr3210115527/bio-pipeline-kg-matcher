#!/usr/bin/env python3
"""Evaluate the reviewed 96 question/tool/data cases against the live matcher."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


HERE = Path(__file__).resolve()
PACKAGE_ROOT = HERE.parents[2]
ROOT = PACKAGE_ROOT / "app" if (PACKAGE_ROOT / "app").is_dir() else HERE.parents[1]
sys.path.insert(0, str(ROOT))

from question_benchmark import load_question_benchmark  # noqa: E402
from workflow_composer import WorkflowComposer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    os.environ["FORCE_RULE"] = "1"
    composer = WorkflowComposer()
    rows = []
    for case in load_question_benchmark().get("cases") or []:
        result = composer.plan(case["query"], top_k=3)
        recommendations = result.get("recommendations") or []
        recommendation = recommendations[0] if recommendations else {}
        data = recommendation.get("data") or {}
        expected_names = list(case.get("expected_data") or [])
        returned_names = [item.get("name") for item in data.get("assets") or []]
        rows.append({
            "case_id": case["case_id"],
            "pipeline_ok": recommendation.get("pipeline_id") == case["expected_pipeline_id"],
            "data_names_ok": returned_names == expected_names,
            "pipeline_id": recommendation.get("pipeline_id"),
            "tool_catalog_status": (recommendation.get("tool") or {}).get("catalog_status"),
            "data_status": data.get("status"),
            "matched_count": data.get("matched_count"),
            "expected_count": data.get("expected_count"),
            "missing_asset_names": data.get("missing_asset_names") or [],
        })

    summary = {
        "schema_version": "question-tool-data-evaluation/v1",
        "case_count": len(rows),
        "pipeline_correct": sum(item["pipeline_ok"] for item in rows),
        "data_name_correct": sum(item["data_names_ok"] for item in rows),
        "registered_tool_cases": sum(
            item["tool_catalog_status"] == "registered" for item in rows
        ),
        "missing_tool_cases": sum(
            item["tool_catalog_status"] == "missing_from_neo4j" for item in rows
        ),
        "fully_available_data_cases": sum(
            item["data_status"] == "available" for item in rows
        ),
        "missing_data_cases": sum(
            item["data_status"] == "missing_from_graph" for item in rows
        ),
        "results": rows,
    }
    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")

    if summary["case_count"] != 96 or summary["pipeline_correct"] != 96:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
