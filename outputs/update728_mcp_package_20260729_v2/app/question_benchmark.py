"""Reviewed question-to-pipeline/data references used for recommendation QA."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


BENCHMARK_PATH = Path(__file__).resolve().parent / "config" / "question_tool_data_benchmark.json"


def normalize_question(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).rstrip("。！？?!")


@lru_cache(maxsize=1)
def load_question_benchmark() -> Dict[str, Any]:
    if not BENCHMARK_PATH.is_file():
        return {"schema_version": "question-tool-data-benchmark/v1", "cases": []}
    return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _case_index() -> Dict[str, Dict[str, Any]]:
    return {
        normalize_question(case.get("query")): case
        for case in load_question_benchmark().get("cases") or []
        if case.get("query")
    }


def exact_reference(query: Any) -> Optional[Dict[str, Any]]:
    case = _case_index().get(normalize_question(query))
    return dict(case) if case else None


def reference_pipeline_ids() -> List[str]:
    return sorted({
        str(case.get("expected_pipeline_id"))
        for case in load_question_benchmark().get("cases") or []
        if case.get("expected_pipeline_id")
    })


def prompt_examples() -> str:
    return "\n".join(
        f"- {case['query']} => {case['expected_pipeline_id']}"
        for case in load_question_benchmark().get("cases") or []
    )
