#!/usr/bin/env python3
"""Run repeatable live Top-3 planner probes without recording credentials."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime_config import initialize_runtime

initialize_runtime(ROOT / ".env.local")

from workflow_composer import WorkflowComposer


def percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    composer = WorkflowComposer()
    runs = []
    for run_number in range(1, max(1, args.runs) + 1):
        started = time.perf_counter()
        result = composer.plan(args.query, top_k=3)
        elapsed = round(time.perf_counter() - started, 3)
        runs.append({
            "run": run_number,
            "elapsed_s": elapsed,
            "selection_status": result.get("selection_status"),
            "candidate_count": result.get("candidate_count"),
            "candidate_tool_ids": [
                [step.get("tool_id") for step in candidate.get("tool_chain") or []]
                for candidate in result.get("candidates") or []
            ],
            "result": result,
        })

    elapsed_values = [item["elapsed_s"] for item in runs]
    payload = {
        "schema_version": "top3-live-probe/v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "name": args.name,
        "query": args.query,
        "run_count": len(runs),
        "latency_s": {
            "min": min(elapsed_values),
            "max": max(elapsed_values),
            "mean": round(statistics.mean(elapsed_values), 3),
            "p50": percentile(elapsed_values, 0.50),
            "p95": percentile(elapsed_values, 0.95),
        },
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "name": args.name,
        "output": str(args.output),
        "latency_s": payload["latency_s"],
        "runs": [
            {
                "run": item["run"],
                "status": item["selection_status"],
                "count": item["candidate_count"],
                "tools": item["candidate_tool_ids"],
            }
            for item in runs
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
