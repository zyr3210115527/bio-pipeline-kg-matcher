#!/usr/bin/env python3
"""Acceptance test written only against mcp_integration_guide.md contracts."""

import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self):
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "app/server.py")],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.next_id = 1

    def call(self, name, arguments):
        request_id = self.next_id
        self.next_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        started = time.perf_counter()
        self.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        while True:
            response = json.loads(self.process.stdout.readline())
            if response.get("id") == request_id:
                return response, round((time.perf_counter() - started) * 1000, 1)

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=5)


def structured(response):
    return (response.get("result") or {}).get("structuredContent") or {}


def main():
    client = Client()
    cases = []
    try:
        response, elapsed = client.call(
            "route_pipeline_request",
            {"query": "我有双端 FASTQ 想做 RNA-seq 上游分析", "data_matcher_mode": "neo4j"},
        )
        value = structured(response)
        chain = ((value.get("agent_input") or {}).get("tool_chain") or [])
        expanded_tools = [step.get("tool_id") for step in chain]
        legacy_response, legacy_elapsed = client.call(
            "route_pipeline_request",
            {
                "query": "我有双端 FASTQ 想做 RNA-seq 上游分析",
                "data_matcher_mode": "neo4j",
                "expand_standard_steps": False,
            },
        )
        legacy_value = structured(legacy_response)
        legacy_chain = ((legacy_value.get("agent_input") or {}).get("tool_chain") or [])
        cases.append({
            "task": "plan_rnaseq_upstream",
            "ok": (
                value.get("selection_status") == "ready"
                and expanded_tools == [
                    "fastqc", "trim_galore", "star", "rsem",
                    "samtools", "featurecounts", "multiqc",
                ]
                and all(
                    step.get("decomposition_status") == "expanded_locked_recipe"
                    for step in chain
                )
                and [step.get("tool_id") for step in legacy_chain]
                == ["rnaseq_singletask"]
            ),
            "elapsed_ms": elapsed,
            "legacy_elapsed_ms": legacy_elapsed,
            "status": value.get("selection_status"),
            "pipeline_ids": (value.get("workflow_plan") or {}).get("pipeline_ids"),
            "expanded_tools": expanded_tools,
            "legacy_tools": [step.get("tool_id") for step in legacy_chain],
        })

        steps = [
            {"step_id": "trim", "tool_id": "fastp", "inputs": {"raw_fastq_read": {"asset_role": "fastq_file"}}},
            {"step_id": "align", "tool_id": "bwa", "inputs": {"clean_fastq_read": {"from": {"step_id": "trim", "output": "clean_fastq_read"}}, "genome_annotation": {"asset_role": "reference_file"}}},
            {"step_id": "bam", "tool_id": "samtools", "inputs": {"aligned_bam": {"from": {"step_id": "align", "output": "aligned_bam"}}}},
            {"step_id": "call", "tool_id": "gatk", "inputs": {"sorted_dedup_bam": {"from": {"step_id": "bam", "output": "sorted_dedup_bam"}}, "genome_annotation": {"asset_role": "reference_file"}}},
            {"step_id": "filter", "tool_id": "bcftools", "inputs": {"unfiltered_vcf": {"from": {"step_id": "call", "output": "unfiltered_vcf"}}}},
            {"step_id": "annotate", "tool_id": "snpeff", "inputs": {"filtered_vcf": {"from": {"step_id": "filter", "output": "filtered_vcf"}}, "genome_annotation": {"asset_role": "reference_file"}}},
        ]
        response, elapsed = client.call("validate_tool_chain", {"steps": steps})
        value = structured(response)
        availability_response, availability_elapsed = client.call(
            "query_data_availability",
            {
                "intent": {
                    "query_text": "WES FASTQ 做体细胞变异检测并注释",
                    "omics_type": "WES/MAF",
                    "input_hint": "fq.gz",
                },
                "steps": steps,
                "data_matcher_mode": "neo4j",
            },
        )
        availability = structured(availability_response)
        cases.append({
            "task": "validate_single_sample_wes_chain",
            "ok": (
                value.get("valid") is True
                and availability.get("status") == "available"
                and availability.get("request_mode") == "custom_steps"
                and availability.get("required_asset_roles") == ["fastq_file"]
            ),
            "elapsed_ms": elapsed,
            "availability_elapsed_ms": availability_elapsed,
            "valid": value.get("valid"),
            "errors": (value.get("validation") or {}).get("errors"),
            "availability_status": availability.get("status"),
            "required_asset_roles": availability.get("required_asset_roles"),
        })

        response, elapsed = client.call(
            "route_pipeline_request",
            {"query": "有哪些流程可以处理 MAF 文件", "data_matcher_mode": "neo4j"},
        )
        value = structured(response)
        pipelines = ((value.get("agent_input") or {}).get("extensions") or {}).get("capability_answer", {}).get("pipelines", [])
        cases.append({
            "task": "query_maf_capabilities",
            "ok": value.get("selection_status") == "information",
            "elapsed_ms": elapsed,
            "status": value.get("selection_status"),
            "pipeline_count": len(pipelines),
        })
    finally:
        client.close()

    report = {
        "schema_version": "consumer-acceptance/v1",
        "ok": all(case["ok"] for case in cases),
        "cases": cases,
    }
    output = ROOT / "consumer_acceptance_result.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
