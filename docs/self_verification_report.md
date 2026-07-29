# Self-verification Report

## Final result

Stages A-E completed without lowering any validator, allowlist, or gate. Production Neo4j at `bolt://127.0.0.1:7687` remained read-only. Final delivery was exercised against isolated staging and against a dump restored into a fresh Neo4j home.

## 1. Static and unit gates

- CSV validation: PASS.
- Python syntax checks: PASS.
- Unit suite: 84 tests discovered; 81 passed and 3 opt-in real-integration tests skipped.
- The original 68-test baseline remains covered. New tests cover custom data availability, standard expansion, slot variants, role/mate binding, shuffle permutations, and atomic catalog rollback.

## 2. Unified graph

Source staging and fresh restore both passed 9/9 checks.

| Scope | Nodes | Relationships |
|---|---:|---:|
| Data graph | 32,744 | 73,001 |
| Tool catalog | 233 | 601 |
| Unified total | 32,977 | 73,602 |

Catalog details: 24 tools, 58 input slots, 53 output slots, 28 NEXT, 7 HAS_STEP. Catalog fingerprint is `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`; cross-domain relationships and mixed nodes are both 0.

## 3. Dual-read and demos

- CSV vs Neo4j matcher: 191/191 cases, 0 material differences.
- Fresh restore rerun: 191/191 cases, 0 material differences.
- Six complete composer comparisons: 6/6, recursive material diff 0.

## 4. MCP

- Staging online smoke: 12/12.
- Staging offline replay: 12/12.
- Fresh restore online smoke: 12/12.
- Fresh restore offline replay: 12/12.
- Final delivery-tree online smoke: 12/12.
- Final delivery-tree offline replay: 12/12.

The delivery copy of the smoke runner resolves `app/server.py` from the packaged layout; this was verified from inside `docs/mcp_delivery/`.

## 5. Six fixes

1. `query_data_availability` accepts exactly one of registered `pipeline_ids` or strictly validated custom `steps`. Valid WES steps derive FASTQ requirements; invalid tools return `-32602`; valid/no-data returns `not_available`.
2. `rnaseq_singletask` defaults to its locked 7-step atomic recipe. `expand_standard_steps=false` preserves the old single-node shape. The other 11 pipelines remain explicitly unexpanded.
3. Canonical CSV now reproduces the exact legacy catalog and can express the full slot/relationship schema. Final bootstrap is idempotent.
4. fastp/BWA have named R1/R2 slots; SAMtools produces BAI; GATK paired mode requires tumor/normal BAM+BAI and an execution-managed interval list.
5. Assets preserve `sample_role`, `mate`, individual, sample, and run identifiers. Binding is exact and fails closed; it never reuses the last positional candidate.
6. fastp and GATK input variants require one complete, uniquely inferred variant. Catalog replacement and NEXT publication occur in one Neo4j transaction; injected failure rolled back to the exact prior fingerprint.
7. Neo4j short IDs remain the internal routing identifiers. Before `agent_input` is returned, atomic steps are translated to Knowledge Card `meta.id` plus Knowledge Card input/output names and validated again. A missing or incompatible mapping fails closed as `no_match`.

MultiQC is again visible in stage two and is the final step in the locked RNA-seq recipe. Its incoming NEXT edges are order-only. In five successful real paired-WES LLM runs, core tumor/normal and R1/R2 bindings were stable; one run validly appended MultiQC, so custom `steps` and `match_id` are not stable fields.

## 6. Restore rehearsal

Final dump: `neo4j/datagraph-staging.dump`

SHA-256: `07572b120251d549062890c29e64a3f9ac2f5ea95dc5d0c517ec3a768c8017a9`

The dump was loaded into a fresh Neo4j 2026.06.0 home on `7689/7476`. Unified graph 9/9, dual-read 191/191 with 0 material differences, and MCP online/offline 12/12 all passed. A dump clone retains the database ID, so operators must also verify URI, port, process home, and system database identity.

## 7. Consumer acceptance

Acceptance was run from `docs/mcp_delivery/`, using only the integration/restore guides and packaged scripts.

| Task | Result | Timing |
|---|---|---:|
| RNA-seq standard plan | ready; 7 Knowledge Card execution IDs; I/O mapping verified | 2,032.1 ms cold |
| Legacy standard shape | single `rnaseq_singletask` node | 142.2 ms hot |
| Single-sample WES validation | valid | 252.1 ms hot |
| Custom-step data availability | available; required role `fastq_file` | 190.4 ms hot |
| MAF capability query | information; 4 pipelines | 0.7 ms hot |

Documentation gaps found and fixed during acceptance: old catalog counts and dump hash, the obsolete custom-availability limitation, missing standard-expansion switch semantics, paired role/mate and variant semantics, MultiQC behavior, and the packaged smoke runner's source-layout assumption. No source inspection is now needed for those tasks.

## 8. Residual risks

- The dump was rehearsed on Neo4j Community 2026.06.0/Java 21; cross-major restores were not tested.
- LLM custom planning still varies and may validly append MultiQC; contract validation remains the authoritative gate.
- Eleven pipelines remain pipeline-level and must not be treated as decomposed execution chains.
- GATK -> BCFtools remains intentionally non-executable: the current GATK Knowledge Card omits `filtered_vcf_index`, while BCFtools requires it and accepts `filtered_vcf` rather than the catalog's existing unfiltered edge.
- The CSV fallback can age after Neo4j becomes authoritative. Continuing to distribute both indefinitely risks recreating two truths.
- Compatibility aliases for generic fastp/BWA and single-slot GATK remain intentionally; a versioned deprecation should be discussed rather than removing them silently.
