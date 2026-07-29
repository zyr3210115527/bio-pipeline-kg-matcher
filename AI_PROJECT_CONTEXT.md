# bio-pipeline-kg-matcher AI Context

Updated: 2026-07-28. Read sections 1, 4, 5, and 8 before changing runtime behavior.

## 1. Product contract

This project converts a natural-language bioinformatics request into up to three validated, data-complete atomic tool chains. It plans only; it does not execute tools or collect runtime parameters.

Hard constraints:

1. Neo4j is the only runtime source for tools, slots, artifacts, formats and NEXT/HAS_STEP relations. WDL is historical review material only.
2. Public recommendations use only the 12 Neo4j `atomic` tools. Pipeline/task_pipeline nodes may be listed as capabilities but never appear in a recommended `tool_chain`.
3. Standard/prebuilt routing has been removed. One LLM call proposes 1-5 ranked atomic chains; the service independently validates and data-matches each, then returns at most three.
4. `_validate_custom_steps` is strict and must not be weakened. Unknown tools, slots, outputs, artifacts, NEXT edges, disconnected steps and invalid input variants fail closed.
5. Only user sample data affects candidate data readiness. Reference genomes, annotations, indexes, interval lists, CPU and memory are execution-managed.
6. Tumor-normal WES must preserve four FASTQ assets, sample_role/mate identity, two independent branches and GATK's tumor/normal BAM+BAI slots.
7. Never write production Neo4j on `7687` during tests. Use isolated `7688/datagraph-staging`.

Public route schema is `tool-chain/v2`. There is no top-level `agent_input`; consumers read `candidates[i].assets` and `candidates[i].tool_chain`.

## 2. Main files

| File | Responsibility |
|---|---|
| `workflow_composer.py` | Neo4j atomic catalog, one-call Top-3 prompt, strict validation, per-candidate matching/binding/contracts |
| `pipeline_router.py` | Intent rules and CSV/Neo4j data matching primitives |
| `knowledge_card_execution.py` | Internal tool-to-Knowledge Card translation and final contract validation |
| `intent.py` | OpenAI-compatible LLM client, complete-JSON extraction and metadata |
| `runtime_config.py` | `.env.local`, defaults and sanitized health metadata |
| `neo4j_observability.py` | Read-only Neo4j health, tool catalog and evidence |
| `server.py` | Seven-tool MCP stdio server and v2 output schema |
| `app.py` | HTTP demo adapter for `candidates[]` |
| `data_matcher/` | CSV, Neo4j and dual-read data backends |
| `config/knowledge_card_execution_contracts.json` | Execution IDs and input/output mappings |
| `docs/mcp_delivery/` | Self-contained MCP delivery package |

## 3. Request lifecycle

`WorkflowComposer.plan(nl_text, top_k=3)`:

1. `_capability_intent` detects pure catalog browsing. Those requests return `information` without LLM or data matching.
2. `_top3_llm_decision` makes exactly one LLM call. The prompt includes the 12 atomic contracts and requires 1-5 complete ranked chains or an explicit unsupported reason.
3. `_normalize_ranked_candidates` caps at five, de-duplicates identical chains, sorts rank and resolves duplicate ranks.
4. `_top3_plan` calls the unchanged `_validate_custom_steps` for each candidate.
5. `_build_top3_candidate` uses the dedicated paired matcher only for tumor/normal + GATK four-slot chains; all other candidates use custom-role matching.
6. Only complete `data_combinations` are accepted. Partial file candidates never enter Top-3.
7. Assets and bindings are built independently, validated internally, translated to Knowledge Card IDs, and validated again.
8. Valid candidates are sorted and capped at `min(top_k, 3)`.

Statuses:

- `ready`: one or more candidates survived all gates;
- `unsupported`: required capability is not atomized;
- `no_candidate`: no chain survived validation and complete data matching, or LLM returned no usable object;
- `information`: catalog browse.

## 4. Catalog and approved baseline

Approved isolated graph:

- database: `bolt://127.0.0.1:7688`, `datagraph-staging`;
- data graph: 32,744 nodes / 73,001 relationships;
- tool catalog: 233 nodes / 601 relationships;
- unified total: 32,977 nodes / 73,602 relationships;
- catalog: 24 tools, 12 atomic + 12 pipeline/task_pipeline;
- fingerprint: `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`;
- data snapshot: `dg-b23135d49c950d0846a563bc`.

The delivery dump and config-only rebuild are semantically equivalent when this catalog fingerprint matches. Byte identity is not required.

The 12 internal atomic IDs are `fastqc`, `fastp`, `trim_galore`, `bwa`, `star`, `samtools`, `rsem`, `featurecounts`, `gatk`, `bcftools`, `snpeff`, and `multiqc`. Public `tool_chain[].tool_id` uses Knowledge Card execution IDs after translation.

The pipeline catalog remains available to `list_pipeline_capabilities` and `query_data_availability(pipeline_ids)` only. HAS_STEP coverage does not authorize route expansion.

## 5. Validation and biological boundaries

`_validate_custom_steps` checks atomic membership, exact registered input/output names, input variants, previous-step references, artifact compatibility, NEXT edges and connectedness.

Important data distinctions:

- raw count is not TPM/FPKM;
- uBAM is not aligned BAM;
- STAR `transcriptome_bam` feeds RSEM, while `aligned_bam` feeds SAMtools;
- MultiQC consumes QC/log outputs or order dependencies, not expression, VCF or enrichment results;
- GATK single-sample variant uses `sorted_dedup_bam` only;
- GATK tumor-normal variant uses exactly tumor BAM+BAI and normal BAM+BAI.

The Knowledge Card currently maps only GATK's paired tumor/normal inputs, so an internal single-sample `sorted_dedup_bam` chain fails at external contract translation. It also blocks a complete `GATK -> BCFtools -> SnpEff` chain because the required VCF index is absent. Do not invent mappings/indexes or weaken validation; paired chains ending at GATK can pass.

Unatomized requests such as differential expression, GO/KEGG enrichment, WGCNA and survival analysis must return `unsupported`. Pipeline-level nodes are not a fallback.

## 6. MCP interfaces

Seven tools are exposed:

1. `route_pipeline_request(query, top_k=1..3, data_matcher_mode, include_internal)` -> `tool-chain/v2`.
2. `list_pipeline_capabilities(detail, data_matcher_mode)`.
3. `list_workflow_methods(detail, data_matcher_mode)`.
4. `validate_tool_chain(steps, data_matcher_mode)`.
5. `query_data_availability(intent, exactly one of pipeline_ids or steps, limit, ...)`.
6. `health_check()`.
7. `render_pipeline_answer(result)`.

`force_custom` and `expand_standard_steps` no longer exist. Do not add a compatibility copy of Top1 under `agent_input`.

## 7. Runtime configuration

Process environment overrides `.env.local`. Important defaults:

- DeepSeek endpoint, `deepseek-v4-pro`, thinking enabled, reasoning effort high;
- `LLM_TIMEOUT=180`, `LLM_MAX_TOKENS=16000`;
- Neo4j production defaults to `7687/neo4j` and is read-only;
- isolated tests explicitly override to `7688/datagraph-staging`;
- `DATA_MATCHER_MODE` can be `neo4j`, `compare`, or `csv`; production uses `neo4j`.

Never log or package API keys, passwords, `.env.local`, endpoint paths with credentials, or raw exception stacks.

## 8. Gates

Run against isolated staging:

```bash
NEO4J_URI=bolt://127.0.0.1:7688 \
NEO4J_DATABASE=datagraph-staging \
NEO4J_PASSWORD=x \
.venv/bin/python -m unittest discover -s tests -v
```

Required baselines:

- 84 discovered: 81 pass + 3 opt-in real integrations skipped;
- unified graph 9/9;
- CSV/Neo4j dual-read 191/191, zero material differences;
- MCP online and offline smoke 12/12;
- catalog fingerprint unchanged;
- paired five-permutation shuffle test passes;
- Python syntax and MCP stdout JSON checks pass.

Real LLM quality probes live in `docs/top3_live_*.json` and are generated by `scripts/top3_live_probe.py`. Each important prompt is run three times and records full results, latency and token metadata without secrets.

## 9. Delivery migration

Current integration docs and schema are under `docs/mcp_delivery/`. v1 examples and old smoke artifacts outside that package are historical evidence only.

Consumer migration:

- `agent_input.tool_chain` -> `candidates[i].tool_chain`;
- `agent_input.assets` -> `candidates[i].assets`;
- `agent_input.study_accession` -> `candidates[i].study_accession`;
- one workflow -> 0-3 ranked choices.

Steps and `match_id` are not stable across LLM calls. Compare contract validity and requested output coverage, not literal list equality.
