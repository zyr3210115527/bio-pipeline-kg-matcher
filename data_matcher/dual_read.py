"""CSV-primary dual reader with a non-blocking Neo4j comparison side channel."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from .comparison import SCHEMA_VERSION, compare_results


class DualReadDataMatcher:
    def __init__(self, csv_matcher: Any, neo4j_matcher: Any, output_path: str | Path | None = None):
        self.csv_matcher = csv_matcher
        self.neo4j_matcher = neo4j_matcher
        self.output_path = Path(
            output_path or os.environ.get("DATA_MATCHER_DIFF_PATH", "docs/data_matcher_compare_runtime.jsonl")
        )

    def _write(self, report: Mapping[str, Any]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n")

    def match(
        self,
        intent: Dict[str, Any],
        pipelines: Sequence[Dict[str, Any]],
        limit: int = 10,
    ) -> Dict[str, Any]:
        pipeline_ids = [str(item.get("pipeline_id") or "") for item in pipelines]
        started = time.perf_counter()
        csv_result = self.csv_matcher.match(intent, pipelines, limit=limit)
        csv_ms = (time.perf_counter() - started) * 1000
        case_id = "runtime-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        try:
            started = time.perf_counter()
            neo4j_result = self.neo4j_matcher.match(intent, pipelines, limit=limit)
            neo4j_ms = (time.perf_counter() - started) * 1000
            report = compare_results(
                case_id,
                intent,
                pipeline_ids,
                csv_result,
                neo4j_result,
                {"csv": csv_ms, "neo4j": neo4j_ms},
            )
        except Exception as exc:
            report = {
                "schema_version": SCHEMA_VERSION,
                "case_id": case_id,
                "intent": dict(intent),
                "pipeline_ids": pipeline_ids,
                "timing_ms": {"csv": round(csv_ms, 3)},
                "neo4j_error": {"type": type(exc).__name__, "message": str(exc)},
                "material_diff_count": 1,
                "known_representation_diff_count": 0,
            }
            print(f"data matcher compare neo4j_error: {type(exc).__name__}", file=sys.stderr)
        self._write(report)
        return csv_result

    def match_custom_roles(
        self,
        intent: Dict[str, Any],
        required_roles: Sequence[str],
        limit: int = 10,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        csv_result = self.csv_matcher.match_custom_roles(
            intent, required_roles, limit=limit
        )
        csv_ms = (time.perf_counter() - started) * 1000
        case_id = "runtime-custom-" + datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S.%fZ"
        )
        comparison_ids = ["custom-role:" + role for role in required_roles]
        try:
            started = time.perf_counter()
            neo4j_result = self.neo4j_matcher.match_custom_roles(
                intent, required_roles, limit=limit
            )
            neo4j_ms = (time.perf_counter() - started) * 1000
            report = compare_results(
                case_id,
                intent,
                comparison_ids,
                csv_result,
                neo4j_result,
                {"csv": csv_ms, "neo4j": neo4j_ms},
            )
        except Exception as exc:
            report = {
                "schema_version": SCHEMA_VERSION,
                "case_id": case_id,
                "intent": dict(intent),
                "pipeline_ids": comparison_ids,
                "timing_ms": {"csv": round(csv_ms, 3)},
                "neo4j_error": {"type": type(exc).__name__, "message": str(exc)},
                "material_diff_count": 1,
                "known_representation_diff_count": 0,
            }
            print(
                f"data matcher compare neo4j_error: {type(exc).__name__}",
                file=sys.stderr,
            )
        self._write(report)
        return csv_result

    def lookup_files(self, file_names: Sequence[str]) -> Dict[str, Any]:
        """Recommendation evidence is authoritative only when Neo4j confirms it."""
        return self.neo4j_matcher.lookup_files(file_names)

    def close(self) -> None:
        for matcher in (self.csv_matcher, self.neo4j_matcher):
            close = getattr(matcher, "close", None)
            if close:
                close()
