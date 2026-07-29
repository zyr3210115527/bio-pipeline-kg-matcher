# Top-3 Verification

## Scope

The standard/recipe route is no longer part of `route_pipeline_request`. One LLM call proposes 1-5 ranked atomic chains; each chain is independently validated, matched to data, bound to assets, translated to Knowledge Cards, and validated again. Only valid, data-complete candidates enter the first three positions of `tool-chain/v2`.

All Neo4j acceptance commands in this report explicitly used the isolated `bolt://127.0.0.1:7688/datagraph-staging` database. Production `7687` was read only and received no bootstrap, apply, import, cleanup, or mutation command.

## Baseline and graph gates

| Gate | Result |
|---|---|
| Unit suite | 84 discovered; 81 passed; 3 opt-in real integrations skipped |
| Unified graph | 9/9 checks passed |
| Data matcher dual read | 191/191 cases; 0 material differences; 0 representation differences |
| MCP package live smoke | 12/12 passed |
| MCP package offline replay | 12/12 passed |
| Consumer acceptance | 4/4 passed |
| Catalog | 233 nodes; 601 relationships; 24 tools; 12 atomic tools; 28 NEXT; 7 HAS_STEP |
| Catalog fingerprint | `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903` |

The config-only catalog reconstruction and packaged Neo4j dump have the same catalog fingerprint. This proves semantic equivalence for the delivery contract; byte-for-byte dump identity is not required.

The final dual-read run measured Neo4j matcher median `174.142 ms`, p95 `251.691 ms`, and maximum `371.384 ms`. Five candidates would therefore add roughly `0.87 s` at the median or `1.26 s` at p95 before LLM time; the implementation normally generates 1-3 genuinely distinct candidates and never creates candidates merely to fill the quota.

## Live LLM quality

The live probes used DeepSeek `deepseek-v4-pro`, reasoning enabled, one LLM call per request, and three repetitions per query. Credentials are not stored in the evidence files.

| Query | Repeated outcome | Observed latency |
|---|---|---|
| Paired tumor/normal WES through unfiltered VCF | 3/3 `ready`; each returned `fastp x2 -> BWA x2 -> SAMtools x2 -> GATK` | p50 `65.786 s`, p95 `66.910 s` |
| Paired-end RNA-seq to abundance and count matrices | 3/3 `ready`; Top1 consistently mapped to `fastp -> STAR -> SAMtools -> featureCounts -> RSEM -> MultiQC` | p50 `51.890 s`, p95 `105.055 s` |
| Differential expression plus GO/KEGG | 3/3 `unsupported`; no fabricated chain | p50 `5.331 s`, p95 `5.616 s` |
| Valid RNA-seq request for absent `HRA999999` | 3/3 `no_candidate`; no data from another study leaked in | p50 `112.089 s`, p95 `217.145 s` |
| Single-sample WES through GATK | 3/3 model plans were biologically correct, but 3/3 were rejected by the Knowledge Card gate | p50 `60.037 s`, p95 `65.122 s` |

The paired and RNA-seq Top1 chains were precise and complete. The model did not reliably produce useful alternative chains because the current 12-tool closed catalog has little genuine tool substitution; returning one good chain is preferable to padding Top-3 with truncated or duplicated chains.

There is no like-for-like pre-Top-3 live latency corpus for these exact prompts, so a numerical before/after claim would be misleading. In current measurements, LLM reasoning time dominates data matching. The worst observed no-data p95 is too high for short synchronous client timeouts; the runtime timeout is 180 seconds and MCP progress notifications remain necessary.

## Paired-data invariant

`tests.test_slot_model.SlotModelTests.test_paired_wes_binds_by_role_and_mate_for_five_permutations` passed five different permutations of the four FASTQ assets. Every run bound tumor R1/R2 and normal R1/R2 to the matching fastp inputs, preserved the individual accession, and populated GATK's `tumor_bam`, `tumor_bai`, `normal_bam`, and `normal_bai` from the correct branch.

The multi-candidate contamination test also passed. A paired candidate always uses the dedicated `wes_somatic_pair` matcher; each candidate owns its matched data, assets, bindings, validation state, and usage tracking.

## Known backend gaps

The atomic catalog supports a single-sample GATK slot (`sorted_dedup_bam`), but the current Knowledge Card execution contract maps only the tumor/normal four-slot form. Therefore a biologically valid single-sample chain is rejected at `contract_validation`. This is a backend contract gap, not an LLM planning error; the composer deliberately does not invent a mapping.

The full `GATK -> BCFtools -> SnpEff` chain remains blocked because the registered BCFtools execution contract requires a VCF index that the upstream contract does not publish. This also fails closed.

Requests for differential expression, enrichment, WGCNA, survival analysis, immune infiltration, uBAM creation, and other capabilities without a faithful atomic decomposition are explicitly `unsupported`. The ambiguity boundary is a partially representable request: if its requested terminal product needs an unregistered method, the entire request is rejected rather than returning a misleading upstream fragment.

## Contract and cleanup

The public contract is now `tool-chain/v2`. The top-level single-chain `agent_input`, `tool_chain`, and `assets` fields are gone; consumers iterate `candidates[]` and read those fields from each candidate. `force_custom` and `expand_standard_steps` are removed. This is a small mechanical consumer change but intentionally breaking, so no v1 compatibility copy is emitted.

The standard selector, coverage-gap promotion, locked-recipe expansion, first-stage pipeline chooser, `PipelineRouter.route()`, v1 `build_agent_input`, and v1 renderer were removed. `PipelineRouter` now remains only as the internal rule-intent and data-matcher container used by Top-3 and data-availability tools.

## Answers to the six acceptance questions

1. One-call candidate quality is good for the two fully representable domains: paired WES and RNA-seq Top1 were correct in 3/3 runs each. The catalog currently offers too few honest alternatives, so returning one candidate is common and preferable to contrived alternatives.
2. Paired binding was not polluted. Five shuffled FASTQ permutations and the mixed-candidate isolation test passed, with role, mate, individual, and four GATK slots stable.
3. End-to-end p50/p95 were `65.786/66.910 s` for paired WES and `51.890/105.055 s` for RNA-seq. This is acceptable only for clients that honor the 180-second timeout and progress notifications; data matching itself remains sub-second per candidate.
4. No old standard branch, v1 renderer, `PipelineRouter.route()`, or v1 `build_agent_input` remains. Repository diagnostics that asserted standard behavior were removed instead of being left as dead scripts.
5. The contract was raised to `tool-chain/v2`. Consumers replace one top-level read with iteration over `candidates[i]`; the seven MCP tool names are unchanged.
6. Partially representable terminal goals are the main fuzzy area. The policy is fail closed: if the requested final analysis cannot be expressed by registered atomic tools and contracts, return `unsupported`, not an incomplete upstream chain.

## Evidence

- `top3_live_paired_wes.json`
- `top3_live_rnaseq_final.json`
- `top3_live_unsupported.json`
- `top3_live_no_data_after_fix.json`
- `top3_live_single_wes_after_prompt.json`
- `top3_unified_graph_verification.json`
- `top3_data_matcher_diff_results.json`
- `mcp_delivery/mcp_smoke_result.json`
- `mcp_delivery/mcp_smoke_offline_result.json`
- `mcp_delivery/consumer_acceptance_result.json`
