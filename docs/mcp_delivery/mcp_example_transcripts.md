# MCP Example Transcripts

以下省略与重点无关的资产属性和步骤输入；真实响应仍应通过 `schemas/tool_chain_output.schema.json`。

## Top-3 路由

请求：

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"route_pipeline_request","arguments":{"query":"双端 RNA-seq FASTQ 生成表达丰度和 count 矩阵","top_k":3,"data_matcher_mode":"neo4j"}}}
```

结构化响应：

```json
{
  "schema_version": "tool-chain/v2",
  "selection_status": "ready",
  "candidate_count": 1,
  "candidates": [
    {
      "rank": 1,
      "match_note": "完整覆盖定量和计数目标",
      "workflow_mode": "custom",
      "match_id": "match-...",
      "validation_ok": true,
      "feasibility_status": "ready",
      "study_accession": "HRA000074",
      "assets": [{"asset_id":"...","role":"fastq_r1","path":"..."}],
      "tool_chain": [
        {"step_id":"fastp","tool_id":"fastp_paired_end","inputs":{}},
        {"step_id":"star","tool_id":"star_rrna_and_genome_alignment","inputs":{}},
        {"step_id":"samtools","tool_id":"samtools_alignment_processing","inputs":{}},
        {"step_id":"featurecounts","tool_id":"featurecounts_gene_counting","inputs":{}},
        {"step_id":"rsem","tool_id":"rsem_quantification","inputs":{}}
      ]
    }
  ],
  "unsupported_reason": null,
  "intent": {"query_text":"双端 RNA-seq FASTQ 生成表达丰度和 count 矩阵","analysis_goal":"...","requested_outputs":[]},
  "planner_metadata": {"used":true,"status":"ok","model":"deepseek-v4-pro","calls":1},
  "data_matcher_mode": "neo4j"
}
```

## 尚未原子化

请求：

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"route_pipeline_request","arguments":{"query":"对表达矩阵做差异表达和 GO/KEGG 富集"}}}
```

响应重点：

```json
{
  "schema_version": "tool-chain/v2",
  "selection_status": "unsupported",
  "candidate_count": 0,
  "candidates": [],
  "unsupported_reason": "差异表达与富集分析尚未在当前 atomic 目录中原子化，暂不支持。"
}
```

## 有合法链但本地无完整数据

```json
{
  "schema_version": "tool-chain/v2",
  "selection_status": "no_candidate",
  "candidate_count": 0,
  "candidates": [],
  "unsupported_reason": "候选链未同时通过目录校验和完整用户样本数据匹配。"
}
```

## 目录浏览

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"route_pipeline_request","arguments":{"query":"有哪些原子工具"}}}
```

响应重点为 `selection_status="information"`、`candidate_count=0`、`candidates=[]`；目录信息位于响应扩展字段。该分支不调用 LLM，也不应执行。
