# MCP Example Transcripts

以下为实测请求/响应的 canonical structuredContent。JSON-RPC 原始响应还包含一份等价的 text content；逐字原始请求/响应和字符数见 `mcp_smoke_cassette.json`。

## 1. Health

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"health_check","arguments":{}}}
```

```json
{"schema_version":"mcp-health/v1","connected":true,"ready":true,"database":"datagraph-staging","snapshot_id":"dg-b23135d49c950d0846a563bc","datagraph_node_count":32744,"tool_count":24,"error":null,"mcp_timing_ms":184.2}
```

冷启动总耗时 234.8 ms。

## 2. Capability Summary

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_pipeline_capabilities","arguments":{"detail":"summary"}}}
```

```json
{"source":"neo4j","pipeline_count":12,"pipelines":[{"tool_id":"diff_expr_go","tool_kind":"pipeline","name":"diff_expr_go","inputs":["expression_matrix"],"outputs":["differential_expression","go_enrichment"],"allowed_next_tool_ids":[],"decomposition_status":"neo4j_pipeline_level_tool","internal_tool_ids":["diff_expr_go"]},{"tool_id":"rnaseq_singletask","tool_kind":"task_pipeline","name":"RNA-seq 单任务完整上游流程","inputs":["fastq_1","fastq_2","gtf_file","rrna_star_index","rsem_index","star_genome_index"],"outputs":["aligned_bam","expression_count_matrix","expression_abundance_matrix","quality_control_report"],"allowed_next_tool_ids":[],"decomposition_status":"neo4j_locked_recipe","internal_tool_ids":["fastqc","trim_galore","star","rsem","samtools","featurecounts","multiqc"]}],"mcp_timing_ms":1751.8}
```

示例只展示数组中的两个条目；原始 transcript 包含全部 12 个。

## 3. Validate-only

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"validate_tool_chain","arguments":{"steps":[{"step_id":"trim","tool_id":"fastp","inputs":{"raw_fastq_read":{"asset_role":"fastq_file"}}},{"step_id":"align","tool_id":"bwa","inputs":{"clean_fastq_read":{"from":{"step_id":"trim","output":"clean_fastq_read"}},"genome_annotation":{"asset_role":"reference_file"}}}]}}}
```

```json
{"schema_version":"tool-chain-validation/v1","valid":true,"validation":{"ok":true,"errors":[],"warnings":[],"required_external_inputs":[]},"normalized_steps":[{"order":1,"step_id":"trim","tool_id":"fastp","inputs":{"raw_fastq_read":{"asset_role":"fastq_file"}},"depends_on":[]},{"order":2,"step_id":"align","tool_id":"bwa","inputs":{"clean_fastq_read":{"from":{"step_id":"trim","output":"clean_fastq_read"}},"genome_annotation":{"asset_role":"reference_file"}},"depends_on":[]}],"mcp_timing_ms":1661.3}
```

## 4. Data Availability

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"query_data_availability","arguments":{"intent":{"query_text":"paired RNA-seq FASTQ","omics_type":"bulk RNA-seq","input_hint":"FASTQ"},"pipeline_ids":["rnaseq_singletask"]}}}
```

```json
{"schema_version":"data-availability/v1","status":"available","data_matcher_mode":"neo4j","matched_data":{"data_schema":"normalized-v2","file_candidates":[{"source":"T1","files":"HRR024685_f1.fq.gz","read_pair":"R1","input_role":"fastq"},{"source":"T1","files":"HRR024685_r2.fq.gz","read_pair":"R2","input_role":"fastq"}],"counts":{"cohort_candidates":10,"file_candidates":2,"backup_file_candidates":10,"data_combinations":1}},"feasibility":{"ok":true,"missing_roles":[],"actual_file_count":2,"message":"所需数据角色齐全，可以执行。"},"mcp_timing_ms":1806.1}
```

## 5. Route

```json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"route_pipeline_request","arguments":{"query":"我有双端 FASTQ 想做 RNA-seq 上游分析"},"_meta":{"progressToken":"route-5"}}}
```

```json
{"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"route-5","progress":0,"total":1,"message":"started"}}
{"schema_version":"tool-chain/v1","selection_status":"ready","orchestration_status":"ready","workflow_mode":"standard","workflow_plan":{"mode":"standard","pipeline_ids":["rnaseq_singletask"]},"agent_input":{"execution_kind":"tool_chain","workflow_mode":"standard","study_accession":"HRA000071","feasibility":{"status":"ready","missing_assets":[]}},"data_matcher_mode":"neo4j","mcp_timing_ms":1896.0}
{"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":"route-5","progress":1,"total":1,"message":"completed"}}
```

## 6. Protocol Error vs Business Gap

参数非法：

```json
{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"route_pipeline_request","arguments":{"query":""}}}
{"jsonrpc":"2.0","id":6,"error":{"code":-32602,"message":"query must be a non-empty string","data":{"category":"invalid_parameters","retryable":false}}}
```

能力未登记是成功响应中的业务状态：

```json
{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"query_data_availability","arguments":{"intent":{"query_text":"unknown"},"pipeline_ids":["not_registered"]}}}
{"schema_version":"data-availability/v1","status":"capability_gap","unknown_pipeline_ids":["not_registered"],"data_matcher_mode":"neo4j"}
```

