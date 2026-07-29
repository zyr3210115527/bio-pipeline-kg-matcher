#!/usr/bin/env python3
"""Exercise every MCP tool and five failure classes, with offline replay support."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "app/server.py" if (ROOT / "app/server.py").is_file() else ROOT / "server.py"


VALID_STEPS = [
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


def call_message(request_id: int, name: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": dict(arguments)},
    }


def value(response: Mapping[str, Any]) -> Any:
    return (response.get("result") or {}).get("structuredContent")


def live_exchange(
    request: Mapping[str, Any],
    env_updates: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    env = os.environ.copy()
    env.update({str(key): str(item) for key, item in (env_updates or {}).items()})
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, str(SERVER)],
        cwd=ROOT,
        env=env,
        input=json.dumps(request, ensure_ascii=False) + "\n",
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    messages = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    responses = [item for item in messages if item.get("id") == request.get("id")]
    response = responses[-1] if responses else {}
    return {
        "request": request,
        "response": response,
        "notifications": [item for item in messages if item.get("method") == "notifications/progress"],
        "elapsed_ms": round(elapsed_ms, 1),
        "response_chars": len(json.dumps(response, ensure_ascii=False, separators=(",", ":"))),
        "stderr": completed.stderr,
        "exit_code": completed.returncode,
    }


def checks() -> List[Dict[str, Any]]:
    route_request = call_message(
        6,
        "route_pipeline_request",
        {"query": "我有双端 FASTQ 想做 RNA-seq 上游分析"},
    )
    route_request["params"]["_meta"] = {"progressToken": "smoke-route"}
    return [
        {
            "id": "health_check",
            "request": call_message(1, "health_check", {}),
            "assert": lambda response: bool((value(response) or {}).get("ready")),
        },
        {
            "id": "list_pipeline_capabilities",
            "request": call_message(2, "list_pipeline_capabilities", {}),
            "assert": lambda response: (value(response) or {}).get("pipeline_count") == 12,
        },
        {
            "id": "list_workflow_methods",
            "request": call_message(3, "list_workflow_methods", {}),
            "assert": lambda response: (value(response) or {}).get("atomic_tool_count") == 12,
        },
        {
            "id": "validate_tool_chain",
            "request": call_message(4, "validate_tool_chain", {"steps": VALID_STEPS}),
            "assert": lambda response: (value(response) or {}).get("valid") is True,
        },
        {
            "id": "query_data_availability",
            "request": call_message(
                5,
                "query_data_availability",
                {
                    "intent": {
                        "query_text": "paired RNA-seq FASTQ",
                        "omics_type": "bulk RNA-seq",
                        "input_hint": "FASTQ",
                    },
                    "pipeline_ids": ["rnaseq_singletask"],
                },
            ),
            "assert": lambda response: (value(response) or {}).get("status") == "available",
        },
        {
            "id": "route_pipeline_request",
            "request": route_request,
            "env": {"FORCE_RULE": "1", "LLM_API_KEY": ""},
            "assert": lambda response: (
                (value(response) or {}).get("schema_version") == "tool-chain/v2"
                and (value(response) or {}).get("selection_status") == "ready"
                and (value(response) or {}).get("candidate_count") >= 1
            ),
        },
        {
            "id": "render_pipeline_answer",
            "request": call_message(7, "render_pipeline_answer", {"result": {}}),
            "assert": lambda response: isinstance(value(response), str),
        },
        {
            "id": "failure_neo4j_disconnected",
            "request": call_message(8, "health_check", {}),
            "env": {"NEO4J_URI": "bolt://127.0.0.1:1", "NEO4J_CONNECT_TIMEOUT": "0.2"},
            "assert": lambda response: (value(response) or {}).get("ready") is False,
        },
        {
            "id": "failure_llm_unavailable",
            "request": call_message(
                9,
                "route_pipeline_request",
                {"query": "请规划一个没有规则兜底的全新蛋白质组流程"},
            ),
            "env": {"FORCE_RULE": "0", "LLM_REQUIRED": "1", "LLM_API_KEY": "", "DEEPSEEK_API_KEY": ""},
            "assert": lambda response: (
                (value(response) or {}).get("selection_status") == "no_candidate"
                or (response.get("error") or {}).get("code") == -32001
            ),
        },
        {
            "id": "failure_invalid_parameters",
            "request": call_message(10, "route_pipeline_request", {"query": ""}),
            "assert": lambda response: (response.get("error") or {}).get("code") == -32602,
        },
        {
            "id": "failure_capability_gap",
            "request": call_message(
                11,
                "query_data_availability",
                {"intent": {"query_text": "unknown"}, "pipeline_ids": ["not_registered"]},
            ),
            "assert": lambda response: (value(response) or {}).get("status") == "capability_gap",
        },
        {
            "id": "failure_data_not_satisfied",
            "request": call_message(
                12,
                "query_data_availability",
                {
                    "intent": {"query_text": "unavailable cohort", "disease": "definitely-not-a-real-disease"},
                    "pipeline_ids": ["wgcna"],
                },
            ),
            "env": {"NEO4J_QUERY_TIMEOUT": "10"},
            "assert": lambda response: (value(response) or {}).get("status") == "not_available",
        },
    ]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Replay an existing cassette without starting the MCP server")
    parser.add_argument("--cassette", default=str(ROOT / "docs/mcp_smoke_cassette.json"))
    parser.add_argument("--output", default=str(ROOT / "docs/mcp_smoke_result.json"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    definitions = checks()
    if args.offline:
        cassette = json.loads(Path(args.cassette).read_text(encoding="utf-8"))
        exchanges = {item["id"]: item for item in cassette.get("checks") or []}
    else:
        exchanges = {}
        for definition in definitions:
            exchange = live_exchange(definition["request"], definition.get("env"))
            exchanges[definition["id"]] = {"id": definition["id"], **exchange}

    results = []
    for definition in definitions:
        exchange = exchanges.get(definition["id"], {})
        response = exchange.get("response") or {}
        try:
            ok = bool(definition["assert"](response))
        except Exception:
            ok = False
        result = {
            key: item
            for key, item in exchange.items()
            if key != "stderr" or item
        }
        result.update({"id": definition["id"], "ok": ok})
        results.append(result)
        print(f"{'✅' if ok else '❌'} {definition['id']}: {result.get('elapsed_ms', 0)} ms")

    report = {
        "schema_version": "mcp-smoke/v1",
        "mode": "offline" if args.offline else "live",
        "ok": all(item["ok"] for item in results),
        "passed": sum(1 for item in results if item["ok"]),
        "failed": sum(1 for item in results if not item["ok"]),
        "checks": results,
    }
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not args.offline:
        cassette_path = Path(args.cassette).resolve()
        cassette_path.parent.mkdir(parents=True, exist_ok=True)
        cassette_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"report={output_path}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
