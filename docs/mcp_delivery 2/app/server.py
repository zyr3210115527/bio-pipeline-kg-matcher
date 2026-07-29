#!/usr/bin/env python3
"""Minimal dependency-free MCP stdio server for the pipeline matcher."""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable, Dict, Optional

from runtime_config import initialize_runtime

_PROCESS_DATA_MATCHER_MODE_EXPLICIT = "DATA_MATCHER_MODE" in os.environ
initialize_runtime()

from data_matcher.factory import build_data_matcher  # noqa: E402
from neo4j_observability import Neo4jClient  # noqa: E402
from pipeline_router import (  # noqa: E402
    PipelineRouter,
    assess_custom_role_feasibility,
    assess_feasibility,
    custom_data_roles,
    render_pipeline_answer,
)
from workflow_composer import (  # noqa: E402
    Neo4jPipelineCatalog,
    RegisteredMethodCatalog,
    WorkflowComposer,
)


TOOL_CHAIN_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "selection_status", "intent", "agent_input"],
    "properties": {
        "schema_version": {"const": "tool-chain/v1"},
        "selection_status": {
            "enum": [
                "ready", "missing_assets", "no_match", "draft", "requires_review",
                "information"
            ]
        },
        "intent": {
            "type": "object",
            "required": ["query_text", "analysis_goal", "requested_outputs"],
            "properties": {
                "query_text": {"type": "string"},
                "analysis_goal": {"type": ["string", "null"]},
                "requested_outputs": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": True,
        },
        "agent_input": {
            "type": "object",
            "required": [
                "execution_kind", "match_id", "study_accession", "assets",
                "tool_chain", "feasibility", "selection_reason",
            ],
            "properties": {
                "execution_kind": {"enum": ["tool_chain", "information"]},
                "workflow_mode": {"enum": ["standard", "custom", "capability"]},
                "match_id": {"type": "string"},
                "study_accession": {"type": ["string", "null"]},
                "assets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["asset_id", "role", "path"],
                        "properties": {
                            "asset_id": {"type": "string"},
                            "role": {"type": "string"},
                            "path": {"type": "string"},
                            "format": {"type": ["string", "null"]},
                        },
                        "additionalProperties": True,
                    },
                },
                "tool_chain": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["step_id", "tool_id", "inputs"],
                        "properties": {
                            "step_id": {"type": "string"},
                            "tool_id": {"type": "string"},
                            "inputs": {"type": "object"},
                        },
                        "additionalProperties": True,
                    },
                },
                "feasibility": {
                    "type": "object",
                    "required": ["status", "missing_assets"],
                    "properties": {
                        "status": {"type": "string"},
                        "missing_assets": {"type": "array"},
                    },
                    "additionalProperties": True,
                },
                "selection_reason": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


def _result(request_id: Any, value: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": value}


def _error(
    request_id: Any,
    code: int,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _tool_result(value: Any) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, indent=2)}],
        "structuredContent": value,
    }


_COMPOSERS: Dict[str, WorkflowComposer] = {}


def _matcher_mode(args: Dict[str, Any]) -> str:
    mode = str(args.get("data_matcher_mode") or os.environ.get("DATA_MATCHER_MODE", "csv")).lower()
    if mode not in {"csv", "compare", "neo4j"}:
        raise ValueError("data_matcher_mode must be csv, compare, or neo4j")
    return mode


def _composer(mode: str) -> WorkflowComposer:
    if mode not in _COMPOSERS:
        method_catalog = RegisteredMethodCatalog()
        router = PipelineRouter(
            Neo4jPipelineCatalog(method_catalog),
            matcher=build_data_matcher(mode),
        )
        _COMPOSERS[mode] = WorkflowComposer(router=router, method_catalog=method_catalog)
    return _COMPOSERS[mode]


def _compact_route(value: Dict[str, Any], include_internal: bool) -> Dict[str, Any]:
    if include_internal:
        return value
    plan = value.get("workflow_plan") or {}
    compact_plan = {
        key: plan.get(key)
        for key in (
            "mode",
            "pipeline_ids",
            "reference_pipeline_ids",
            "execution_status",
            "validation",
            "decomposition_gaps",
        )
        if key in plan
    }
    return {
        key: item
        for key, item in {
            "schema_version": value.get("schema_version"),
            "selection_status": value.get("selection_status"),
            "orchestration_status": value.get("orchestration_status"),
            "orchestration_ready": value.get("orchestration_ready"),
            "orchestration_message": value.get("orchestration_message"),
            "workflow_mode": value.get("workflow_mode"),
            "intent": value.get("intent"),
            "workflow_plan": compact_plan,
            "agent_input": value.get("agent_input"),
            "force_custom": value.get("force_custom"),
            "data_matcher_mode": value.get("data_matcher_mode"),
        }.items()
        if item is not None
    }


def _catalog_capabilities(composer: WorkflowComposer) -> list[Dict[str, Any]]:
    return [
        {
            **method.as_dict(),
            "source": "neo4j",
            "internal_steps": composer._neo4j_pipeline_steps(method.tool_id),
            "internal_steps_locked": True,
        }
        for method in sorted(
            composer.registered_methods.pipeline_methods.values(),
            key=lambda item: item.tool_id,
        )
    ]


def _catalog_methods(composer: WorkflowComposer) -> Dict[str, Any]:
    decomposition = {}
    for method in composer.registered_methods.pipeline_methods.values():
        recipe = composer._neo4j_pipeline_steps(method.tool_id)
        has_recipe = bool(composer.registered_methods.pipeline_steps.get(method.tool_id))
        decomposition[method.tool_id] = {
            "status": "neo4j_locked_recipe" if has_recipe else "neo4j_pipeline_level_tool",
            "registered_units": [step["tool_id"] for step in recipe],
            "source": "neo4j",
        }
    return {
        "source": "neo4j",
        "connected": composer.registered_methods.connected,
        "error": composer.registered_methods.error,
        "pipeline_decomposition_status": decomposition,
        "atomic_tools": composer.registered_methods.capabilities(),
        "neo4j_tools": composer.registered_methods.capabilities(include_pipelines=True),
    }


def _brief_tool(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tool_id": item.get("tool_id"),
        "tool_kind": item.get("tool_kind"),
        "name": item.get("name"),
        "inputs": [value.get("name") for value in item.get("inputs") or []],
        "outputs": [value.get("name") for value in item.get("outputs") or []],
        "allowed_next_tool_ids": item.get("allowed_next_tool_ids") or [],
    }


def _brief_availability(matched: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "data_schema": matched.get("data_schema"),
        "cohort_candidates": matched.get("cohort_candidates") or [],
        "file_candidates": matched.get("file_candidates") or [],
        "data_combinations": matched.get("data_combinations") or [],
        "query_constraints": matched.get("query_constraints") or {},
        "counts": {
            key: len(matched.get(key) or [])
            for key in (
                "cohort_candidates",
                "file_candidates",
                "backup_file_candidates",
                "data_combinations",
            )
        },
    }


def _custom_required_asset_roles(
    composer: WorkflowComposer,
    steps: list[Dict[str, Any]],
    validation: Dict[str, Any],
) -> list[str]:
    roles: list[str] = []
    for step in steps:
        for binding in (step.get("inputs") or {}).values():
            role = str(binding.get("asset_role") or "")
            if role and role not in {"reference_file"} and role not in roles:
                roles.append(role)
    for item in validation.get("required_external_inputs") or []:
        role = composer._role_for_input(str(item.get("input") or ""))
        if role not in {"reference_file"} and role not in roles:
            roles.append(role)
    return roles


def _health() -> Dict[str, Any]:
    client = Neo4jClient()
    health = client.health(force=True)
    health.update({
        "schema_version": "mcp-health/v1",
        "data_matcher_mode": os.environ.get("DATA_MATCHER_MODE", "csv"),
        "expected_snapshot_id": os.environ.get("DATAGRAPH_SNAPSHOT_ID"),
        "snapshot_id": None,
        "datagraph_node_count": None,
        "tool_count": None,
        "ready": False,
    })
    if not health.get("connected"):
        client.close()
        return health
    try:
        driver = client._get_driver()
        with driver.session(database=client.database, default_access_mode=client._read_access) as session:
            row = session.run(
                "MATCH (n) WHERE n.datagraph_managed = true "
                "WITH collect(DISTINCT n.snapshot_id) AS snapshots,count(n) AS data_count "
                "OPTIONAL MATCH (t:tool_id) "
                "RETURN snapshots,data_count,count(t) AS tool_count"
            ).single()
        snapshots = list(row["snapshots"] or [])
        health["snapshot_id"] = snapshots[0] if len(snapshots) == 1 else snapshots
        health["datagraph_node_count"] = int(row["data_count"])
        health["tool_count"] = int(row["tool_count"])
        health["ready"] = (
            snapshots == [health["expected_snapshot_id"]]
            and health["datagraph_node_count"] == 32744
            and health["tool_count"] == 24
        )
        if not health["ready"]:
            health["error"] = "unified_graph_contract_mismatch"
    except Exception:
        health["error"] = "unified_graph_query_failed"
    finally:
        client.close()
    return health


def handle(
    message: Dict[str, Any],
    notify: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None and method == "notifications/initialized":
        return None
    if method == "initialize":
        return _result(request_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "bio-pipeline-kg-matcher", "version": "1.0.0"},
        })
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": [
            {
                "name": "route_pipeline_request",
                "description": "Plan but do not execute a bioinformatics workflow. Returns tool-chain/v1 with execution status, Neo4j-backed assets, and registered tool bindings.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 14},
                        "force_custom": {
                            "type": "boolean",
                            "description": "跳过预制菜选择，直接使用 Neo4j atomic 工具闭集规划自助餐。"
                        },
                        "expand_standard_steps": {
                            "type": "boolean",
                            "default": True,
                            "description": "Expand registered HAS_STEP recipes into atomic steps. Set false for the legacy pipeline-node shape."
                        },
                        "data_matcher_mode": {"type": "string", "enum": ["csv", "compare", "neo4j"], "description": "Data backend for this call. neo4j fails closed; compare returns CSV and records a side-by-side diff."},
                        "include_internal": {"type": "boolean", "description": "Include planner analysis, nested debug result, and matcher internals. Default false."}
                    },
                    "required": ["query"],
                },
                "outputSchema": TOOL_CHAIN_OUTPUT_SCHEMA,
            },
            {
                "name": "list_pipeline_capabilities",
                "description": "List executable pipeline-level capabilities, registered I/O slots, and any locked HAS_STEP recipe from Neo4j. This does not inspect data availability.",
                "inputSchema": {"type": "object", "properties": {"data_matcher_mode": {"type": "string", "enum": ["csv", "compare", "neo4j"]}, "detail": {"type": "string", "enum": ["summary", "full"], "default": "summary"}}},
            },
            {
                "name": "list_workflow_methods",
                "description": "List the closed Neo4j registry of atomic tools and pipeline tools, including exact input/output names and decomposition status.",
                "inputSchema": {"type": "object", "properties": {"data_matcher_mode": {"type": "string", "enum": ["csv", "compare", "neo4j"]}, "detail": {"type": "string", "enum": ["summary", "full"], "default": "summary"}}},
            },
            {
                "name": "validate_tool_chain",
                "description": "Validate an agent-proposed atomic tool chain against the registered Neo4j tools, slot names, artifacts, outputs, and NEXT edges. No LLM call and no execution.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "steps": {"type": "array", "items": {"type": "object"}},
                        "data_matcher_mode": {"type": "string", "enum": ["csv", "compare", "neo4j"]}
                    },
                    "required": ["steps"]
                }
            },
            {
                "name": "query_data_availability",
                "description": "Match cohorts, files, and complete data combinations for either registered pipeline IDs or a validated custom atomic tool chain. No LLM call and no workflow execution.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "intent": {"type": "object"},
                        "pipeline_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 12},
                        "steps": {"type": "array", "items": {"type": "object"}},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "include_backup_candidates": {"type": "boolean", "description": "Include lower-ranked backup candidates. Default false."},
                        "data_matcher_mode": {"type": "string", "enum": ["csv", "compare", "neo4j"]}
                    },
                    "required": ["intent"],
                    "oneOf": [{"required": ["pipeline_ids"]}, {"required": ["steps"]}]
                }
            },
            {
                "name": "health_check",
                "description": "Check read-only Neo4j connectivity and verify the unified graph snapshot, data-node count, and 24-tool catalog contract.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "render_pipeline_answer",
                "description": "将一次路由结果渲染为适合组会或用户阅读的中文摘要。",
                "inputSchema": {"type": "object", "properties": {"result": {"type": "object"}}, "required": ["result"]},
            },
        ]})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        progress_token = (params.get("_meta") or {}).get("progressToken")
        started = time.perf_counter()
        try:
            if progress_token is not None and notify:
                notify({"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progressToken": progress_token, "progress": 0, "total": 1, "message": "started"}})
            if name == "route_pipeline_request":
                query = args.get("query")
                if not isinstance(query, str) or not query.strip():
                    raise ValueError("query must be a non-empty string")
                force_custom = bool(args.get("force_custom", False))
                top_k = int(args.get("top_k", 5))
                if not 1 <= top_k <= 14:
                    raise ValueError("top_k must be between 1 and 14")
                mode = _matcher_mode(args)
                value = _composer(mode).plan(
                    query,
                    top_k=top_k,
                    force_custom=force_custom,
                    expand_standard_steps=bool(args.get("expand_standard_steps", True)),
                )
                value["force_custom"] = force_custom
                value["data_matcher_mode"] = mode
                value = _compact_route(value, bool(args.get("include_internal", False)))
            elif name == "list_pipeline_capabilities":
                composer = _composer(_matcher_mode(args))
                capabilities = _catalog_capabilities(composer)
                if args.get("detail", "summary") == "full":
                    value = {"source": "neo4j", "pipelines": capabilities}
                else:
                    value = {
                        "source": "neo4j",
                        "pipeline_count": len(capabilities),
                        "pipelines": [
                            {
                                **_brief_tool(item),
                                "decomposition_status": (
                                    "neo4j_locked_recipe"
                                    if composer.registered_methods.pipeline_steps.get(item["tool_id"])
                                    else "neo4j_pipeline_level_tool"
                                ),
                                "internal_tool_ids": [
                                    step.get("tool_id") for step in item.get("internal_steps") or []
                                ],
                            }
                            for item in capabilities
                        ],
                    }
            elif name == "list_workflow_methods":
                catalog = _catalog_methods(_composer(_matcher_mode(args)))
                if args.get("detail", "summary") == "full":
                    value = catalog
                else:
                    atomic = catalog.get("atomic_tools") or []
                    all_tools = catalog.get("neo4j_tools") or []
                    value = {
                        "source": "neo4j",
                        "connected": catalog.get("connected"),
                        "error": catalog.get("error"),
                        "atomic_tool_count": len(atomic),
                        "pipeline_tool_count": len(all_tools) - len(atomic),
                        "atomic_tools": [_brief_tool(item) for item in atomic],
                        "pipeline_decomposition_status": catalog["pipeline_decomposition_status"],
                    }
            elif name == "validate_tool_chain":
                steps = args.get("steps")
                if not isinstance(steps, list):
                    raise ValueError("steps must be an array")
                normalized, validation = _composer(_matcher_mode(args))._validate_custom_steps(steps)
                value = {
                    "schema_version": "tool-chain-validation/v1",
                    "valid": validation["ok"],
                    "validation": validation,
                    "normalized_steps": [
                        {key: step.get(key) for key in ("order", "step_id", "tool_id", "inputs", "depends_on", "outputs")}
                        for step in normalized
                    ],
                }
            elif name == "query_data_availability":
                intent = args.get("intent")
                pipeline_ids = args.get("pipeline_ids")
                custom_steps = args.get("steps")
                if not isinstance(intent, dict):
                    raise ValueError("intent must be an object")
                if (pipeline_ids is None) == (custom_steps is None):
                    raise ValueError("provide exactly one of pipeline_ids or steps")
                if pipeline_ids is not None and not isinstance(pipeline_ids, list):
                    raise ValueError("pipeline_ids must be an array")
                if custom_steps is not None and not isinstance(custom_steps, list):
                    raise ValueError("steps must be an array")
                limit = int(args.get("limit", 10))
                if not 1 <= limit <= 100:
                    raise ValueError("limit must be between 1 and 100")
                mode = _matcher_mode(args)
                composer = _composer(mode)
                if custom_steps is not None:
                    normalized, validation = composer._validate_custom_steps(custom_steps)
                    if not validation["ok"]:
                        raise ValueError(
                            "steps failed validation: " + "; ".join(validation["errors"])
                        )
                    required_asset_roles = _custom_required_asset_roles(
                        composer, normalized, validation
                    )
                    matched = composer.router.matcher.match_custom_roles(
                        intent, required_asset_roles, limit=limit
                    )
                    files = []
                    if matched.get("data_combinations"):
                        files = matched["data_combinations"][0].get("files") or []
                    if not files:
                        files = matched.get("file_candidates") or []
                    feasibility = assess_custom_role_feasibility(
                        required_asset_roles, files
                    )
                    value = {
                        "schema_version": "data-availability/v1",
                        "status": "available" if feasibility["ok"] else "not_available",
                        "request_mode": "custom_steps",
                        "required_asset_roles": required_asset_roles,
                        "required_data_roles": custom_data_roles(required_asset_roles),
                        "data_matcher_mode": mode,
                        "matched_data": (
                            matched
                            if args.get("include_backup_candidates", False)
                            else _brief_availability(matched)
                        ),
                        "feasibility": feasibility,
                    }
                else:
                    assert pipeline_ids is not None
                    unknown = [pipeline_id for pipeline_id in pipeline_ids if pipeline_id not in composer.router.catalog.pipelines]
                    if unknown:
                        value = {
                            "schema_version": "data-availability/v1",
                            "status": "capability_gap",
                            "unknown_pipeline_ids": unknown,
                            "data_matcher_mode": mode,
                        }
                    else:
                        pipelines = [{"pipeline_id": pipeline_id} for pipeline_id in pipeline_ids]
                        matched = composer.router.matcher.match(intent, pipelines, limit=limit)
                        primary = pipeline_ids[0] if pipeline_ids else None
                        files = []
                        for combination in matched.get("data_combinations") or []:
                            if combination.get("pipeline_id") == primary:
                                files = combination.get("files") or []
                                break
                        if not files:
                            files = matched.get("file_candidates") or []
                        value = {
                            "schema_version": "data-availability/v1",
                            "status": "available" if files else "not_available",
                            "request_mode": "pipeline_ids",
                            "data_matcher_mode": mode,
                            "matched_data": (
                                matched
                                if args.get("include_backup_candidates", False)
                                else _brief_availability(matched)
                            ),
                            "feasibility": assess_feasibility(primary, files),
                        }
            elif name == "health_check":
                value = _health()
            elif name == "render_pipeline_answer":
                value = render_pipeline_answer(args.get("result") or {})
            else:
                return _error(request_id, -32601, f"Unknown tool: {name}")
            if isinstance(value, dict):
                value.setdefault("mcp_timing_ms", round((time.perf_counter() - started) * 1000, 1))
            if progress_token is not None and notify:
                notify({"jsonrpc": "2.0", "method": "notifications/progress", "params": {"progressToken": progress_token, "progress": 1, "total": 1, "message": "completed"}})
            return _result(request_id, _tool_result(value))
        except (TypeError, ValueError) as exc:
            return _error(request_id, -32602, str(exc), {"category": "invalid_parameters", "retryable": False})
        except Exception as exc:
            return _error(
                request_id,
                -32001,
                f"Dependency unavailable: {type(exc).__name__}",
                {"category": "dependency_unavailable", "retryable": True},
            )
    if method and request_id is not None:
        return _error(request_id, -32601, f"Unknown method: {method}")
    return None


def main() -> None:
    if not _PROCESS_DATA_MATCHER_MODE_EXPLICIT:
        os.environ["DATA_MATCHER_MODE"] = os.environ.get("MCP_DATA_MATCHER_MODE", "neo4j")

    def notify(value: Dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()

    for line in sys.stdin:
        try:
            message = json.loads(line)
            response = handle(message, notify=notify)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            sys.stdout.write(json.dumps(_error(None, -32700, f"Invalid request: {exc}"), ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
