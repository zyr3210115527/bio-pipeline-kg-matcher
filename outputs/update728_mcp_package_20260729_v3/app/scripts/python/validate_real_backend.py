#!/usr/bin/env python3
"""Read-only validation against the delivered update728 Neo4j backend."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

from neo4j import GraphDatabase, READ_ACCESS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data_matcher.neo4j_matcher import Neo4jKGDataMatcher  # noqa: E402
import server  # noqa: E402


EXPECTED_LABELS = {
    "Project": 17,
    "Study": 19,
    "Individual": 5335,
    "Sample": 8640,
    "T1": 24518,
    "T2": 38011,
}


def call_tool(name: str, arguments: Dict[str, Any], request_id: int) -> Dict[str, Any]:
    response = server.handle({
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    if not response:
        return {"ok": False, "error": "empty_response"}
    if "error" in response:
        return {"ok": False, "error": response["error"]}
    value = ((response.get("result") or {}).get("structuredContent"))
    return {"ok": True, "value": value}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7688"))
    parser.add_argument("--user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD", "disabled-auth"))
    parser.add_argument("--database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "real_backend_validation.json")
    args = parser.parse_args()

    os.environ.update({
        "NEO4J_URI": args.uri,
        "NEO4J_USER": args.user,
        "NEO4J_PASSWORD": args.password,
        "NEO4J_DATABASE": args.database,
        "DATA_MATCHER_MODE": "neo4j",
        "DATAGRAPH_SCHEMA_MODE": "legacy-update728",
        "MCP_DATA_MATCHER_MODE": "neo4j",
    })
    report: Dict[str, Any] = {
        "schema_version": "real-backend-validation/v1",
        "target": {"uri": args.uri, "database": args.database},
        "started_at_unix": time.time(),
        "checks": [],
    }

    def check(name: str, ok: bool, details: Any) -> None:
        report["checks"].append({"name": name, "ok": bool(ok), "details": details})

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password), connection_timeout=5)
    try:
        driver.verify_connectivity()
        check("bolt_connectivity", True, {"uri": args.uri})
        with driver.session(database=args.database, default_access_mode=READ_ACCESS) as session:
            label_records = list(session.run(
                "MATCH (n) UNWIND labels(n) AS label "
                "RETURN label, count(*) AS count ORDER BY label"
            ))
            labels = {str(row["label"]): int(row["count"]) for row in label_records}
            check("legacy_label_counts", all(labels.get(k) == v for k, v in EXPECTED_LABELS.items()), {
                "expected": EXPECTED_LABELS,
                "actual": {k: labels.get(k, 0) for k in EXPECTED_LABELS},
            })
            relationship_records = list(session.run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY type"
            ))
            relationship_counts = {str(row["type"]): int(row["count"]) for row in relationship_records}
            check("legacy_relationship_types", all(
                relationship_counts.get(name, 0) > 0
                for name in ("IN_STUDY", "IN_SAMPLE", "GENERATED_FROM", "NEXT_TOOL")
            ), relationship_counts)
            samples = session.run(
                "MATCH (t:T1) RETURN t.T1_id AS id ORDER BY t.T1_id LIMIT 1"
            ).single()
            t1_id = samples["id"] if samples else None
            t2 = session.run(
                "MATCH (t:T2) RETURN coalesce(t.T2_id,t.t2_id) AS id ORDER BY id LIMIT 1"
            ).single()
            t2_id = t2["id"] if t2 else None
            check("representative_t1", bool(t1_id), {"T1_id": t1_id})
            check("representative_t2", bool(t2_id), {"T2_id": t2_id})
    finally:
        driver.close()

    matcher_details: Dict[str, Any] = {}
    matcher = None
    try:
        matcher = Neo4jKGDataMatcher(
            uri=args.uri, user=args.user, password=args.password, database=args.database
        )
        matcher_details = {
            "backend_schema": matcher.backend_schema,
            "data_schema": matcher.data_schema,
            "project": len(matcher.project),
            "study": len(matcher.study),
            "individual": len(matcher.individual),
            "sample": len(matcher.sample),
            "t1": len(matcher.t1),
            "t2": len(matcher.t2),
            "t1_first": matcher.t1[0] if matcher.t1 else None,
            "t2_first": matcher.t2[0] if matcher.t2 else None,
        }
        check("neo4j_matcher_legacy_adapter", matcher.backend_schema == "legacy-update728", matcher_details)
    except Exception as exc:
        check("neo4j_matcher_legacy_adapter", False, {"error": f"{type(exc).__name__}: {exc}"})
    finally:
        if matcher:
            matcher.close()

    tools_list = server.handle({"jsonrpc": "2.0", "id": 100, "method": "tools/list", "params": {}})
    tool_names = [item["name"] for item in ((tools_list or {}).get("result") or {}).get("tools", [])]
    check("mcp_tools_list", set(tool_names) == {
        "route_pipeline_request", "list_pipeline_capabilities", "list_workflow_methods",
        "validate_tool_chain", "query_data_availability", "health_check", "render_pipeline_answer",
    }, {"count": len(tool_names), "names": tool_names})

    checks = {
        "mcp_health_check": call_tool("health_check", {}, 101),
        "mcp_workflow_catalog": call_tool("list_workflow_methods", {"data_matcher_mode": "neo4j"}, 102),
        "mcp_pipeline_catalog": call_tool("list_pipeline_capabilities", {"data_matcher_mode": "neo4j"}, 103),
        "mcp_availability": call_tool("query_data_availability", {
            "intent": {"analysis_goal": "RNA-seq quality control", "omics_type": "RNA-seq"},
            "pipeline_ids": ["rnaseq_singletask"],
            "limit": 3,
            "data_matcher_mode": "neo4j",
        }, 104),
        "mcp_route": call_tool("route_pipeline_request", {
            "query": "请给出 RNA-seq 上游质控和表达定量流程",
            "top_k": 1,
            "data_matcher_mode": "neo4j",
        }, 105),
        "mcp_render": call_tool("render_pipeline_answer", {"result": {
            "schema_version": "tool-chain/v2", "selection_status": "information",
            "candidate_count": 0, "recommendation_count": 0, "candidates": [], "recommendations": [],
            "unsupported_reason": None, "intent": {"query_text": "validation"},
        }}, 106),
        "mcp_invalid_parameter": call_tool("validate_tool_chain", {"steps": "not-an-array", "data_matcher_mode": "neo4j"}, 107),
        "mcp_capability_spacing": call_tool("route_pipeline_request", {
            "query": "当前有哪些 RNA-seq pipeline？",
            "top_k": 3,
            "data_matcher_mode": "neo4j",
        }, 108),
        "mcp_empty_fastqc": call_tool("validate_tool_chain", {
            "steps": [{"step_id": "qc", "tool_id": "fastqc", "inputs": {}}],
            "data_matcher_mode": "neo4j",
        }, 109),
        "mcp_empty_multiqc": call_tool("validate_tool_chain", {
            "steps": [{"step_id": "mq", "tool_id": "multiqc", "inputs": {}}],
            "data_matcher_mode": "neo4j",
        }, 110),
    }
    invalid = checks["mcp_invalid_parameter"]
    checks["mcp_invalid_parameter"] = {
        **invalid,
        "expected_error": True,
        "ok": bool(
            not invalid.get("ok")
            and (invalid.get("error") or {}).get("code") == -32602
        ),
    }
    capability = checks["mcp_capability_spacing"]
    capability_value = capability.get("value") or {}
    checks["mcp_capability_spacing"] = {
        **capability,
        "ok": bool(
            capability.get("ok")
            and capability_value.get("selection_status") == "information"
            and (capability_value.get("planner_metadata") or {}).get("status")
            == "deterministic_capability_rule"
        ),
    }
    for key in ("mcp_empty_fastqc", "mcp_empty_multiqc"):
        item = checks[key]
        item_value = item.get("value") or {}
        checks[key] = {
            **item,
            "ok": bool(item.get("ok") and item_value.get("valid") is False),
        }

    route_value = checks["mcp_route"].get("value") or {}
    candidates = route_value.get("candidates") or []
    route_candidate = candidates[0] if candidates else {}
    route_steps = route_candidate.get("tool_chain") or []
    route_assets = route_candidate.get("assets") or []
    checks["mcp_route_public_chain_validation"] = call_tool(
        "validate_tool_chain",
        {"steps": route_steps, "assets": route_assets, "data_matcher_mode": "neo4j"},
        111,
    ) if route_steps else {"ok": False, "error": "route_returned_no_candidate"}
    checks["mcp_route_public_chain_validation_without_assets"] = call_tool(
        "validate_tool_chain",
        {"steps": route_steps, "data_matcher_mode": "neo4j"},
        112,
    ) if route_steps else {"ok": False, "error": "route_returned_no_candidate"}
    checks["mcp_route_public_chain_availability"] = call_tool(
        "query_data_availability",
        {
            "intent": route_value.get("intent") or {
                "query_text": "RNA-seq 上游质控和表达定量",
                "omics_type": "bulk RNA-seq",
            },
            "steps": route_steps,
            "assets": route_assets,
            "limit": 3,
            "data_matcher_mode": "neo4j",
        },
        113,
    ) if route_steps else {"ok": False, "error": "route_returned_no_candidate"}
    for key in (
        "mcp_route_public_chain_validation",
        "mcp_route_public_chain_validation_without_assets",
    ):
        item = checks[key]
        checks[key] = {
            **item,
            "ok": bool(item.get("ok") and (item.get("value") or {}).get("valid") is True),
        }
    availability = checks["mcp_route_public_chain_availability"]
    checks["mcp_route_public_chain_availability"] = {
        **availability,
        "ok": bool(
            availability.get("ok")
            and (availability.get("value") or {}).get("status") == "available"
        ),
    }
    report["mcp_checks"] = checks
    report["finished_at_unix"] = time.time()
    report["ready"] = (
        all(item.get("ok") for item in report["checks"])
        and all(item.get("ok") for item in checks.values())
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "ready": report["ready"], "checks": len(report["checks"])}, ensure_ascii=False))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
