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
from data_matcher.expectations import load_expectations  # noqa: E402
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
    "required": [
        "schema_version", "selection_status", "candidate_count", "candidates",
        "recommendation_count", "recommendations",
        "unsupported_reason", "intent", "planner_metadata",
    ],
    "properties": {
        "schema_version": {"const": "tool-chain/v2"},
        "selection_status": {
            "enum": ["ready", "no_candidate", "unsupported", "information"]
        },
        "candidate_count": {"type": "integer", "minimum": 0, "maximum": 3},
        "recommendation_count": {"type": "integer", "minimum": 0, "maximum": 3},
        "unsupported_reason": {"type": ["string", "null"]},
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
        "planner_metadata": {"type": "object", "additionalProperties": True},
        "candidates": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
            "required": [
                    "rank", "match_note", "workflow_mode", "match_id",
                    "validation_ok", "feasibility_status", "study_accession",
                    "assets", "tool_chain",
            ],
            "properties": {
                    "rank": {"type": "integer", "minimum": 1},
                    "match_note": {"type": "string"},
                    "workflow_mode": {"const": "custom"},
                "match_id": {"type": "string"},
                "study_accession": {"type": ["string", "null"]},
                    "validation_ok": {"const": True},
                    "feasibility_status": {"const": "ready"},
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
                "selection_reason": {"type": "string"},
            },
            "additionalProperties": True,
            },
        },
        "recommendations": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": [
                    "rank", "match_id", "pipeline_id", "tool", "data", "source"
                ],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1},
                    "match_id": {"type": "string"},
                    "pipeline_id": {"type": "string"},
                    "match_note": {"type": "string"},
                    "source": {"enum": ["reviewed_reference+neo4j", "llm+neo4j", "deterministic_rule+neo4j"]},
                    "reference_case_id": {"type": ["string", "null"]},
                    "tool": {
                        "type": "object",
                        "required": ["tool_id", "catalog_status", "source"],
                        "properties": {
                            "tool_id": {"type": "string"},
                            "catalog_status": {
                                "enum": ["registered", "missing_from_neo4j"]
                            },
                            "source": {"const": "neo4j"},
                        },
                        "additionalProperties": True,
                    },
                    "data": {
                        "type": "object",
                        "required": [
                            "status", "source", "assets", "matched_count",
                            "expected_count", "missing_asset_names", "study_accessions"
                        ],
                        "properties": {
                            "status": {"enum": ["available", "missing_from_graph"]},
                            "source": {"const": "neo4j"},
                            "assets": {"type": "array", "items": {"type": "object"}},
                            "matched_count": {"type": "integer", "minimum": 0},
                            "expected_count": {"type": "integer", "minimum": 0},
                            "missing_asset_names": {
                                "type": "array", "items": {"type": "string"}
                            },
                            "study_accessions": {
                                "type": "array", "items": {"type": "string"}
                            },
                        },
                        "additionalProperties": True,
                    },
                },
                "additionalProperties": True,
            },
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


def _execution_asset_ids(steps: Any) -> list[str]:
    """Collect asset IDs from an execution-facing chain for structural validation."""
    found: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            asset_id = value.get("asset_id")
            if asset_id and str(asset_id) not in found:
                found.append(str(asset_id))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(steps)
    return found


def _execution_input_role(composer: WorkflowComposer, internal_name: str, external_name: str) -> str:
    """Map a Knowledge Card managed input to the matcher asset-role vocabulary."""
    name = str(internal_name or external_name or "").lower()
    if name in {"raw_fastq_read_r1", "clean_fastq_read_r1"} or external_name == "read1":
        return "fastq_r1"
    if name in {"raw_fastq_read_r2", "clean_fastq_read_r2"} or external_name == "read2":
        return "fastq_r2"
    if name in {"raw_fastq_read", "clean_fastq_read"} or external_name == "fastqs":
        return "fastq_file"
    role = composer._role_for_input(name)
    if role == "data_file" and ("fastq" in name or "read" in name):
        return "fastq_file"
    return role


def _execution_required_asset_roles(
    composer: WorkflowComposer,
    steps: list[Dict[str, Any]],
) -> list[str]:
    """Return managed input roles needed to satisfy an execution-facing chain."""
    roles: list[str] = []
    registry = composer.execution_registry
    for step in steps:
        execution_id = str(step.get("tool_id") or "")
        resolved = registry.by_execution_id.get(execution_id)
        if not resolved:
            continue
        _internal_id, contract = resolved
        input_map = contract.get("input_map") or {}
        bindings = step.get("inputs") or {}
        for external_name, spec in (contract.get("inputs") or {}).items():
            if spec.get("managed_by") != "mcp":
                continue
            internal_name = next(
                (key for key, value in input_map.items() if value == external_name),
                external_name,
            )
            binding = bindings.get(external_name)
            sources = binding.get("sources") if isinstance(binding, dict) else None
            candidates = sources if isinstance(sources, list) else [binding]
            # An upstream binding is already supplied by the chain; only asset
            # bindings and absent required inputs need external data matching.
            needs_external = binding is None or any(
                isinstance(item, dict) and item.get("asset_id") for item in candidates
            )
            if needs_external:
                role = _execution_input_role(composer, internal_name, external_name)
                if role != "reference_file" and role not in roles:
                    roles.append(role)
    return roles


def _chain_id_mode(composer: WorkflowComposer, steps: list[Dict[str, Any]]) -> str:
    """Classify a chain while handling IDs shared by internal and public contracts."""
    execution_ids = set(composer.execution_registry.by_execution_id)
    internal_ids = set(composer.registered_methods.all_methods)
    modes: list[str] = []
    for step in steps:
        tool_id = str(step.get("tool_id") or "")
        in_execution = tool_id in execution_ids
        in_internal = tool_id in internal_ids
        if in_execution and not in_internal:
            modes.append("execution_contract")
            continue
        if in_internal and not in_execution:
            modes.append("neo4j_internal")
            continue
        if not in_execution and not in_internal:
            modes.append("unknown")
            continue
        # fastqc, multiqc and trim_galore use the same public/internal ID.
        # Their I/O namespaces are distinct, so classify from declared keys.
        external_inputs = set(
            (composer.execution_registry.by_execution_id[tool_id][1].get("inputs") or {})
        )
        internal_method = composer.registered_methods.all_methods[tool_id]
        internal_inputs = {item.get("name") for item in internal_method.inputs}
        provided = set((step.get("inputs") or {}).keys())
        if provided & external_inputs and not provided & internal_inputs:
            modes.append("execution_contract")
        elif provided & internal_inputs and not provided & external_inputs:
            modes.append("neo4j_internal")
        else:
            # Empty/ambiguous shared IDs are interpreted as public because the
            # public execution contract is the MCP-facing default.
            modes.append("execution_contract")
    unique = set(modes)
    if "unknown" in unique:
        return "unknown"
    if len(unique) > 1:
        return "mixed"
    return next(iter(unique), "neo4j_internal")


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
    return {
        key: item
        for key, item in {
            "schema_version": value.get("schema_version"),
            "selection_status": value.get("selection_status"),
            "candidate_count": value.get("candidate_count"),
            "candidates": value.get("candidates"),
            "recommendation_count": value.get("recommendation_count"),
            "recommendations": value.get("recommendations"),
            "unsupported_reason": value.get("unsupported_reason"),
            "intent": value.get("intent"),
            "planner_metadata": value.get("planner_metadata"),
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
    expectations = load_expectations()
    legacy_expected = expectations["legacy_backend"]
    health = client.health(force=True)
    health.update({
        "schema_version": "mcp-health/v1",
        "data_matcher_mode": os.environ.get("DATA_MATCHER_MODE", "csv"),
        "expected_snapshot_id": os.environ.get("DATAGRAPH_SNAPSHOT_ID") or expectations["snapshot_id"],
        "snapshot_id": None,
        "datagraph_node_count": None,
        "expected_datagraph_node_count": expectations["node_count"],
        "tool_count": None,
        "expected_tool_count": expectations["tool_count"],
        "backend_schema": None,
        "verification_level": None,
        "legacy_label_counts": {},
        "expected_legacy_label_counts": legacy_expected["label_counts"],
        "backend_snapshot": None,
        "warnings": [],
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
        if snapshots:
            health["backend_schema"] = "managed-v1"
            health["verification_level"] = "snapshot"
            health["ready"] = (
                snapshots == [health["expected_snapshot_id"]]
                and health["datagraph_node_count"] == health["expected_datagraph_node_count"]
                and health["tool_count"] == health["expected_tool_count"]
            )
        else:
            with driver.session(database=client.database, default_access_mode=client._read_access) as session:
                legacy_rows = list(session.run(
                    "MATCH (n) WHERE any(label IN labels(n) WHERE label IN $labels) "
                    "UNWIND labels(n) AS label WITH label,count(n) AS count "
                    "WHERE label IN $labels RETURN label,count ORDER BY label",
                    labels=list(legacy_expected["label_counts"]),
                ))
                snapshot_row = session.run(
                    "MATCH (s:BackendSnapshot) RETURN properties(s) AS snapshot "
                    "ORDER BY s.imported_at DESC LIMIT 1"
                ).single()
            legacy_counts = {
                str(item["label"]): int(item["count"])
                for item in legacy_rows
            }
            for label in legacy_expected["label_counts"]:
                legacy_counts.setdefault(label, 0)
            backend_snapshot = dict(snapshot_row["snapshot"]) if snapshot_row else None
            health["backend_schema"] = "legacy-update728"
            health["legacy_label_counts"] = legacy_counts
            health["datagraph_node_count"] = sum(legacy_counts.values())
            health["backend_snapshot"] = backend_snapshot
            health["snapshot_id"] = (
                str(backend_snapshot.get("snapshot_id") or "")
                if backend_snapshot else None
            )
            snapshot_ok = True
            if backend_snapshot:
                snapshot_ok = (
                    str(backend_snapshot.get("schema_version") or "")
                    == legacy_expected["schema_version"]
                    and str(backend_snapshot.get("source_sha256") or "")
                    == legacy_expected["source_sha256"]
                )
                health["verification_level"] = "snapshot+count_signature"
            else:
                health["verification_level"] = "count_signature"
                health["warnings"].append("backend_snapshot_missing")
            health["ready"] = (
                legacy_counts == legacy_expected["label_counts"]
                and snapshot_ok
                and health["tool_count"] == health["expected_tool_count"]
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
                "description": "Plan but do not execute. One LLM call proposes business-pipeline recommendations and atomic chains; returns up to three Neo4j-backed recommendations plus any validated atomic candidates as tool-chain/v2.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 3, "default": 3},
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
                "description": "Validate either Neo4j-internal tool chains or the execution-facing chain returned by route_pipeline_request against the closed tool and Knowledge Card contracts. No LLM call and no execution.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "steps": {"type": "array", "items": {"type": "object"}},
                        "assets": {"type": "array", "items": {"type": "object"}, "description": "Optional assets used to verify execution-facing asset_id references."},
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
                top_k = int(args.get("top_k", 3))
                if not 1 <= top_k <= 3:
                    raise ValueError("top_k must be between 1 and 3")
                mode = _matcher_mode(args)
                value = _composer(mode).plan(query, top_k=top_k)
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
                composer = _composer(_matcher_mode(args))
                execution_ids = set(composer.execution_registry.by_execution_id)
                internal_ids = set(composer.registered_methods.all_methods)
                step_ids = [str(step.get("tool_id") or "") for step in steps]
                chain_mode = _chain_id_mode(composer, steps)
                unknown_steps = [tool_id for tool_id in step_ids if tool_id not in execution_ids and tool_id not in internal_ids]
                if chain_mode == "mixed":
                    validation = {"ok": False, "errors": ["不能混用执行端 tool_id 和 Neo4j 内部 tool_id"], "warnings": []}
                    value = {
                        "schema_version": "tool-chain-validation/v1",
                        "mode": "execution_contract",
                        "valid": False,
                        "validation": validation,
                        "normalized_steps": steps,
                    }
                elif chain_mode == "execution_contract":
                    if unknown_steps:
                        validation = {"ok": False, "errors": [f"未知执行端 tool_id: {tool_id}" for tool_id in unknown_steps], "warnings": []}
                        value = {
                            "schema_version": "tool-chain-validation/v1",
                            "mode": "execution_contract",
                            "valid": False,
                            "validation": validation,
                            "normalized_steps": steps,
                        }
                    else:
                        assets = args.get("assets")
                        asset_context = "provided"
                        if not isinstance(assets, list):
                            assets = [{"asset_id": asset_id} for asset_id in _execution_asset_ids(steps)]
                            asset_context = "synthetic_asset_ids"
                        validation = composer.execution_registry.validate(steps, assets)
                        validation.setdefault("warnings", [])
                        if asset_context == "synthetic_asset_ids":
                            validation["warnings"].append("未提供 assets，仅验证 asset_id 结构存在；文件路径和角色需在数据可用性查询中确认")
                        value = {
                            "schema_version": "tool-chain-validation/v1",
                            "mode": "execution_contract",
                            "valid": validation["ok"],
                            "validation": validation,
                            "normalized_steps": steps,
                        }
                elif chain_mode == "unknown" or unknown_steps:
                    validation = {"ok": False, "errors": [f"未知 tool_id: {tool_id}" for tool_id in unknown_steps], "warnings": []}
                    value = {
                        "schema_version": "tool-chain-validation/v1",
                        "mode": "neo4j_internal",
                        "valid": False,
                        "validation": validation,
                        "normalized_steps": steps,
                    }
                else:
                    normalized, validation = composer._validate_custom_steps(steps)
                    value = {
                        "schema_version": "tool-chain-validation/v1",
                        "mode": "neo4j_internal",
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
                    execution_ids = set(composer.execution_registry.by_execution_id)
                    internal_ids = set(composer.registered_methods.all_methods)
                    custom_tool_ids = [str(step.get("tool_id") or "") for step in custom_steps]
                    chain_mode = _chain_id_mode(composer, custom_steps)
                    public_mode = chain_mode == "execution_contract"
                    internal_mode = chain_mode == "neo4j_internal"
                    unknown = [tool_id for tool_id in custom_tool_ids if tool_id not in execution_ids and tool_id not in internal_ids]
                    if chain_mode == "mixed":
                        raise ValueError("steps 不能混用执行端 tool_id 和 Neo4j 内部 tool_id")
                    if unknown:
                        raise ValueError("steps 包含未知 tool_id: " + ", ".join(unknown))
                    if public_mode:
                        assets = args.get("assets")
                        if not isinstance(assets, list):
                            assets = [{"asset_id": asset_id} for asset_id in _execution_asset_ids(custom_steps)]
                        validation = composer.execution_registry.validate(custom_steps, assets)
                        if not validation.get("ok"):
                            raise ValueError(
                                "steps failed execution contract validation: "
                                + "; ".join(validation.get("errors") or [])
                            )
                        normalized = custom_steps
                        required_asset_roles = _execution_required_asset_roles(composer, custom_steps)
                        validation.setdefault("required_external_inputs", [])
                    else:
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
