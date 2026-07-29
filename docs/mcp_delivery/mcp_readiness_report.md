# MCP Readiness Report

## Contract

`route_pipeline_request` now returns `tool-chain/v2`. The former standard/custom switch, `force_custom`, `expand_standard_steps`, top-level `agent_input`, and single selected chain have been removed.

The seven MCP tools remain available. Only route planning uses the LLM, exactly once per ordinary analysis request. Catalog browsing, validation, data availability, health and rendering remain deterministic.

## Top-3 gates

- LLM proposes 1-5 complete atomic chains in one response.
- Only the 12 Neo4j atomic tools can be recommended.
- Each candidate independently passes `_validate_custom_steps`.
- Each candidate independently matches a complete `data_combinations` bundle.
- Assets, bindings, internal validation and Knowledge Card validation are isolated per candidate.
- Invalid or data-incomplete candidates are removed, not returned with a warning.
- The remaining candidates are ordered by rank and capped at three.
- Unatomized requests return `unsupported`; exhausted candidates return `no_candidate`.

## Pairing

Tumor-normal candidates continue to use the dedicated matcher only when the chain has both sample branches and GATK's four BAM/BAI slots. Five shuffled FASTQ permutations and a mixed-candidate test verify that `sample_role`, `mate` and GATK bindings are stable and not contaminated by another candidate.

## Compatibility

This is intentionally a breaking release. Consumers must iterate `candidates[]` and select one candidate before execution. The formal migration is in `MCP_AGENT_INTEGRATION_ZH.md` and `mcp_integration_guide.md`; the JSON Schema is `schemas/tool_chain_output.schema.json`.

Pipeline-level tools remain visible to catalog tools and the independent `query_data_availability(pipeline_ids)` interface. They are not a recommendation fallback.

## Known backend gap

The current GATK Knowledge Card exposes the paired tumor/normal contract but lacks a mapping for internal single-sample `sorted_dedup_bam`. It also lacks the index required for a complete `GATK -> BCFtools` transition. Those chains fail closed until the backend contract is updated. No validator was relaxed and no artifact was synthesized.
