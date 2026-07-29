# MCP Integration Guide

## Runtime contract

The server is an MCP stdio process. Start `app/server.py` with Python 3.11+ and configure Neo4j and the LLM through environment variables. Production routing reads the Neo4j atomic catalog and data graph; it does not parse WDL files.

`route_pipeline_request` is a planning-only operation. One LLM call proposes ranked business-pipeline recommendations and 1-5 atomic chains. The service resolves recommendation tools and files against Neo4j, then independently validates and matches every atomic chain. It never executes bioinformatics tools.

## Tools

| Tool | Required input | Output contract | LLM |
|---|---|---|---|
| `route_pipeline_request` | `query` | `tool-chain/v2` | one call, except deterministic capability browsing |
| `list_pipeline_capabilities` | none | registered pipeline-level catalog | no |
| `list_workflow_methods` | none | atomic and pipeline catalog | no |
| `validate_tool_chain` | `steps[]` | `tool-chain-validation/v1` | no |
| `query_data_availability` | `intent` plus exactly one of `pipeline_ids` or `steps` | `data-availability/v1` | no |
| `health_check` | none | `mcp-health/v1` | no |
| `render_pipeline_answer` | `result` | Chinese text summary | no |

Common optional arguments are `data_matcher_mode=neo4j|compare|csv`. `route_pipeline_request` additionally accepts `top_k=1..3` and `include_internal`. The production setting is `neo4j`; this mode fails closed if the graph is unavailable. CSV and compare modes remain diagnostic interfaces and do not change the catalog source.

## Top-3 response

```json
{
  "schema_version": "tool-chain/v2",
  "selection_status": "ready",
  "recommendation_count": 1,
  "recommendations": [
    {
      "rank": 1,
      "pipeline_id": "rnaseq_singletask",
      "tool": {"catalog_status": "registered", "source": "neo4j"},
      "data": {"status": "available", "source": "neo4j", "assets": []}
    }
  ],
  "candidate_count": 2,
  "candidates": [
    {
      "rank": 1,
      "match_note": "Best complete match",
      "workflow_mode": "custom",
      "match_id": "match-...",
      "validation_ok": true,
      "feasibility_status": "ready",
      "study_accession": "HRA...",
      "assets": [],
      "tool_chain": []
    }
  ],
  "unsupported_reason": null,
  "intent": {},
  "planner_metadata": {"used": true, "status": "ok", "calls": 1}
}
```

`recommendations[]` is informational and reports business pipelines plus graph-verified tool and file evidence. `rank=1` in `candidates[]` is the LLM's closest complete atomic match. A candidate appears only when closed-catalog validation, slot/NEXT validation, complete user-data matching, internal binding validation, and Knowledge Card validation all pass.

Status semantics:

| `selection_status` | Meaning |
|---|---|
| `ready` | At least one validated, data-complete candidate is present |
| `unsupported` | The requested capability is not atomized in the current catalog |
| `no_candidate` | No proposed chain survived validation and complete data matching, or the LLM returned no usable chain |
| `information` | Capability browsing, or business recommendations exist but no executable atomic candidate is available |

`recommendations[].tool.catalog_status` distinguishes `registered` from `missing_from_neo4j`. `recommendations[].data.status` distinguishes `available` from `missing_from_graph`; missing assets never receive fabricated paths. `unsupported_reason` is null for `ready` and normally for `information`.

## Migration from v1

This is a breaking contract change. Remove use of `force_custom` and `expand_standard_steps`. Do not read top-level `agent_input`, `workflow_plan`, `workflow_mode`, `tool_chain`, or `assets`.

Use this mapping:

| v1 path | v2 path |
|---|---|
| `agent_input.tool_chain` | `candidates[i].tool_chain` |
| `agent_input.assets` | `candidates[i].assets` |
| `agent_input.study_accession` | `candidates[i].study_accession` |
| `agent_input.match_id` | `candidates[i].match_id` |
| one selected workflow | iterate `candidates[]`, ordered by `rank` |

Do not compare candidates by exact step list or `match_id`; the LLM may make a different valid choice. Validate the schema, `rank`, required outputs, and registered contracts.

## Pairing and data rules

Tumor-normal WES candidates use the dedicated matcher when both sample branches and GATK's `tumor_bam`, `tumor_bai`, `normal_bam`, and `normal_bai` slots are present. Each candidate has isolated matching state. Consumers must preserve `asset.sample_role` and `asset.mate`; list position is not identity.

Only missing user sample data removes a candidate. Reference genomes, annotations, indexes, interval lists, threads, memory, and other execution parameters are owned by the execution layer and are not returned as missing user assets.

The current Knowledge Card does not register the filtered VCF index needed for a complete `GATK -> BCFtools` handoff. Such a chain fails closed until the backend contract is completed; clients must not synthesize that index.

## Timeouts and security

The LLM request timeout is 180 seconds. Set the client timeout above 200 seconds for route calls and around 10 seconds for the other tools. Credentials belong in the process environment or `.env.local`; never put them in MCP requests, logs, cassettes, or this package.

Use `schemas/tool_chain_output.schema.json` for full response validation and `schemas/agent_tool_chain_schema.example.json` as a minimal v2 example.
