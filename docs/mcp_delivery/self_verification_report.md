# MCP Delivery Self-Verification

## Delivery contract

`route_pipeline_request` returns `tool-chain/v2`. One LLM call proposes business-pipeline recommendations and atomic chains. `recommendations[]` carries Neo4j tool/data evidence; `candidates[]` remains the strictly validated atomic execution layer.

There is no standard/custom mode switch, locked-recipe expansion, top-level `agent_input`, or v1 compatibility payload. `force_custom` and `expand_standard_steps` are not accepted. The seven MCP tool names remain unchanged.

## Final gates

All graph-dependent checks used the isolated `bolt://127.0.0.1:7688/datagraph-staging` database. No command in this verification wrote to production `7687`.

| Gate | Result |
|---|---|
| Python unit tests | 89 discovered; 86 passed; 3 opt-in real integrations skipped |
| 96-question tool/data benchmark | 96/96 pipeline IDs; 96/96 referenced data-name sets |
| Unified graph | 9/9 passed |
| CSV/Neo4j dual read | 191/191; 0 material differences; 0 representation differences |
| MCP live smoke | 12/12 passed |
| MCP offline replay | 12/12 passed |
| Consumer acceptance | 5/5 passed |
| Python syntax | Passed for runtime, tests, and delivery Python files |
| JSON schemas/evidence | Parsed successfully |
| MCP stdout | JSON-only response contract passed |
| Secret scan | No API key, Neo4j password, or `.env.local` in the delivery tree |

## Immutable graph baseline

The approved data graph contains 32,744 nodes and 73,001 relationships. The tool catalog contains 233 nodes, 601 relationships, 24 tools (12 atomic and 12 pipeline-level), 58 input slots, 53 output slots, 28 NEXT edges, and 7 HAS_STEP edges.

Catalog fingerprint:

`2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`

The package dump and config-only catalog reconstruction are semantically equivalent by this fingerprint. Top-3 changed orchestration code and contracts only; it did not change the graph, canonical CSV, slots, NEXT edges, or `_validate_custom_steps` rules.

## Pairing and isolation

Paired tumor/normal candidates retain the dedicated four-FASTQ matcher. Five shuffled input permutations passed with stable `sample_role`, mate, individual accession, and GATK four-slot bindings. A separate mixed-candidate test confirmed that one candidate's matching and asset state cannot contaminate another candidate.

## Fail-closed boundaries

The current Knowledge Card contract lacks a single-sample GATK `sorted_dedup_bam` mapping, so otherwise valid single-sample GATK chains are rejected. BCFtools also lacks a satisfiable upstream VCF-index contract. Neither gap is patched or inferred in the composer.

Unatomized terminal analyses return `unsupported`. Valid candidates with no complete user sample-data combination are removed and result in `no_candidate`; execution-managed reference files and runtime parameters do not count as missing user assets.

## Evidence files

- `unified_graph_verification.json`
- `data_matcher_diff_results.json`
- `mcp_smoke_result.json`
- `mcp_smoke_offline_result.json`
- `consumer_acceptance_result.json`
- `question_tool_data_evaluation.json`
- `schemas/tool_chain_output.schema.json`
- `schemas/agent_tool_chain_schema.example.json`

See the repository-level `docs/top3_implementation.md` and `docs/top3_verification.md` for the prompt, live LLM quality, latency, migration details, and known backend gaps.
