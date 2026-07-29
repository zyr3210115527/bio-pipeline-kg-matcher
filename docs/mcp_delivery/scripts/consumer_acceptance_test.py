#!/usr/bin/env python3
"""Black-box acceptance checks for the documented MCP v2 contract."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self) -> None:
        env = os.environ.copy()
        env.setdefault("FORCE_RULE", "1")
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "app/server.py")],
            cwd=ROOT,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.next_id = 1

    def call(self, name: str, arguments: dict) -> tuple[dict, float]:
        request_id = self.next_id
        self.next_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        started = time.perf_counter()
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise RuntimeError("MCP server ended before responding")
            response = json.loads(line)
            if response.get("id") == request_id:
                return response, round((time.perf_counter() - started) * 1000, 1)

    def close(self) -> None:
        self.process.terminate()
        self.process.wait(timeout=5)


def structured(response: dict) -> dict:
    return (response.get("result") or {}).get("structuredContent") or {}


def main() -> int:
    client = Client()
    cases = []
    try:
        response, elapsed = client.call(
            "route_pipeline_request",
            {
                "query": "双端 RNA-seq FASTQ 生成表达丰度和 count 矩阵",
                "top_k": 3,
                "data_matcher_mode": "neo4j",
            },
        )
        value = structured(response)
        cases.append({
            "task": "route_v2_shape",
            "ok": (
                value.get("schema_version") == "tool-chain/v2"
                and value.get("selection_status") == "no_candidate"
                and value.get("candidate_count") == 0
                and value.get("candidates") == []
                and "agent_input" not in value
            ),
            "elapsed_ms": elapsed,
            "status": value.get("selection_status"),
        })

        response, elapsed = client.call(
            "route_pipeline_request",
            {
                "query": "胶质瘤病例组和对照组的表达矩阵，怎么做差异表达和 GO 富集？",
                "data_matcher_mode": "neo4j",
            },
        )
        recommendation_value = structured(response)
        recommendations = recommendation_value.get("recommendations") or []
        recommendation = recommendations[0] if recommendations else {}
        recommendation_data = recommendation.get("data") or {}
        cases.append({
            "task": "reviewed_pipeline_and_data_recommendation",
            "ok": (
                recommendation_value.get("schema_version") == "tool-chain/v2"
                and recommendation.get("pipeline_id") == "diff_expr_go"
                and (recommendation.get("tool") or {}).get("catalog_status") == "registered"
                and recommendation_data.get("status") == "available"
                and [
                    item.get("name") for item in recommendation_data.get("assets") or []
                ] == ["HRA000074-Genes-FPKM-1.0.tsv"]
            ),
            "elapsed_ms": elapsed,
            "pipeline_id": recommendation.get("pipeline_id"),
            "data_status": recommendation_data.get("status"),
        })

        steps = [
            {
                "step_id": "trim",
                "tool_id": "fastp",
                "inputs": {"raw_fastq_read": {"asset_role": "fastq_file"}},
            },
            {
                "step_id": "align",
                "tool_id": "bwa",
                "inputs": {
                    "clean_fastq_read": {
                        "from": {"step_id": "trim", "output": "clean_fastq_read"}
                    },
                    "genome_annotation": {"asset_role": "reference_file"},
                },
            },
        ]
        response, elapsed = client.call("validate_tool_chain", {"steps": steps})
        validation = structured(response)
        cases.append({
            "task": "validate_atomic_chain",
            "ok": validation.get("valid") is True,
            "elapsed_ms": elapsed,
            "errors": (validation.get("validation") or {}).get("errors"),
        })

        response, elapsed = client.call(
            "query_data_availability",
            {
                "intent": {
                    "query_text": "WES FASTQ",
                    "omics_type": "WES/MAF",
                    "input_hint": "fq.gz",
                },
                "steps": steps,
                "data_matcher_mode": "neo4j",
            },
        )
        availability = structured(response)
        cases.append({
            "task": "custom_data_availability",
            "ok": (
                availability.get("request_mode") == "custom_steps"
                and availability.get("status") in {"available", "not_available"}
            ),
            "elapsed_ms": elapsed,
            "status": availability.get("status"),
        })

        response, elapsed = client.call(
            "route_pipeline_request",
            {"query": "有哪些原子工具", "data_matcher_mode": "neo4j"},
        )
        information = structured(response)
        cases.append({
            "task": "capability_information",
            "ok": (
                information.get("schema_version") == "tool-chain/v2"
                and information.get("selection_status") == "information"
                and information.get("candidate_count") == 0
            ),
            "elapsed_ms": elapsed,
            "status": information.get("selection_status"),
        })
    finally:
        client.close()

    report = {
        "schema_version": "consumer-acceptance/v2",
        "ok": all(case["ok"] for case in cases),
        "cases": cases,
    }
    output = ROOT / "consumer_acceptance_result.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
