# Bio Pipeline MCP Agent 接入说明

本文面向调用 MCP 的规划 Agent 和执行 Agent，说明如何启动服务、调用
`route_pipeline_request`、读取 `tool-chain/v1`，以及在什么条件下允许执行。

## 1. 接口边界

本 MCP 只负责：

- 查询 Neo4j 工具目录；
- 选择标准流程或生成 custom 原子工具链；
- 匹配用户数据资产；
- 校验工具、输入槽、输出槽、NEXT 边和资产绑定；
- 返回执行 Agent 可消费的 JSON 合同。

本 MCP **不执行** FASTQ、BAM、VCF、表达矩阵或任何生信分析。

只有 `route_pipeline_request` 返回本文描述的 `tool-chain/v1` 和
`agent_input`。`health_check`、目录查询、链校验、数据可用性查询各自有独立返回格式。

## 2. 启动与 MCP 传输

从交付包根目录启动：

```bash
python -m venv .venv
.venv/bin/pip install -r app/requirements-neo4j.txt -r app/requirements-llm.txt
set -a; . ./.env; set +a
.venv/bin/python app/server.py
```

服务使用 stdio JSON-RPC，没有 HTTP 端口，也不会输出 ready 提示。先调用
`initialize`，再调用 `health_check`。仅当 `health_check.ready=true` 时继续。

一次路由调用：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "route_pipeline_request",
    "arguments": {
      "query": "我有双端 FASTQ，想做 RNA-seq 上游分析",
      "top_k": 5,
      "expand_standard_steps": true,
      "data_matcher_mode": "neo4j"
    }
  }
}
```

MCP 响应中，同一业务对象出现两次：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{ ... tool-chain/v1 的 JSON 字符串 ... }"
      }
    ],
    "structuredContent": {
      "schema_version": "tool-chain/v1",
      "agent_input": {}
    }
  }
}
```

Agent 应读取 `result.structuredContent`，不要重新解析 `content[0].text`。

## 3. 输出是否固定

`tool-chain/v1` 的核心字段固定，但它是按 `execution_kind` 区分的两个固定分支，
不是所有请求返回完全相同的业务内容。

| 请求类型 | `workflow_mode` | `agent_input.execution_kind` | 说明 |
|---|---|---|---|
| 标准流程 | `standard` | `tool_chain` | 返回登记 pipeline 或其锁定 HAS_STEP 展开 |
| 自定义工具链 | `custom` | `tool_chain` | 返回通过闭集校验的 atomic steps |
| 能力目录问答 | `capability` | `information` | 不生成可执行链，assets/tool_chain 固定为空 |

`ready`、`missing_assets`、`draft` 和 `no_match` 是 `tool_chain` 分支的状态，
不会改变核心 JSON 结构。兼容扩展字段允许增加，因此消费者应校验必需字段并忽略
不认识的额外字段。

## 4. `tool-chain/v1` 顶层字段

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `schema_version` | string | 是 | 固定为 `tool-chain/v1` |
| `selection_status` | enum | 是 | `ready`、`missing_assets`、`draft`、`no_match`、`requires_review`、`information` |
| `orchestration_status` | enum | 是 | `ready`、`missing_data`、`draft`、`no_match`、`requires_review`、`information` |
| `orchestration_ready` | boolean | 是 | 是否已满足编排执行条件 |
| `orchestration_message` | string | 是 | 当前编排状态说明 |
| `workflow_mode` | enum | 是 | `standard`、`custom` 或 `capability` |
| `intent` | object | 是 | 原始问题、分析目标、期望输出 |
| `workflow_plan` | object | 是 | 模式、pipeline、校验和拆解状态 |
| `agent_input` | object | 是 | 交给执行 Agent 的正式合同 |
| `force_custom` | boolean | 是 | 本次是否强制 custom |
| `data_matcher_mode` | enum | 是 | `neo4j`、`compare` 或 `csv` |

## 5. `agent_input` 字段

| 字段 | 类型 | 必需 | 含义 |
|---|---|---:|---|
| `execution_kind` | enum | 是 | `tool_chain` 或 `information`，执行 Agent 的主分支字段 |
| `workflow_mode` | enum | 是 | `standard`、`custom` 或 `capability` |
| `match_id` | string | 是 | 本次匹配标识；custom 可因可选步骤变化，不应用作永久业务主键 |
| `study_accession` | string/null | 是 | 匹配到的 study；能力问答为 null |
| `assets` | array | 是 | 已匹配的用户数据资产 |
| `tool_chain` | array | 是 | 有序步骤及正式输入绑定 |
| `feasibility` | object | 是 | 数据是否齐全及缺失项 |
| `selection_reason` | string | 是 | 选择该流程/工具链的原因 |
| `orchestration_status` | enum | 是 | 与顶层编排状态一致 |
| `orchestration_ready` | boolean | 是 | 与顶层可执行标志一致 |
| `orchestration_message` | string | 是 | 编排状态说明 |
| `extensions` | object | 是 | 质量门禁、规划校验和合同校验 |
| `pipeline_id` | string/null | 是 | v1 兼容字段；新 Agent 应读取 `tool_chain` |
| `files` | string[] | 是 | v1 兼容字段；新 Agent 应读取 `assets` |
| `files_text` | string | 是 | v1 兼容字段；新 Agent 应读取 `assets` |

### 5.1 Asset 字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `asset_id` | string | tool input 引用的唯一 ID |
| `role` | string | `fastq_r1`、`fastq_r2`、`count_matrix`、`maf_file` 等 |
| `path` | string | 执行端预期访问的路径 |
| `format` | string/null | 文件格式 |
| `path_verified` | boolean | MCP 主机是否验证路径存在；false 不等于资产不存在 |
| `source` | string/null | T1/T2 等来源 |
| `sample_accession` | string/null | 样本标识 |
| `run_accession` | string/null | run 标识 |
| `individual_accession` | string/null | 个体标识 |
| `sample_role` | enum/null | 配对分析中的 `tumor` 或 `normal` |
| `mate` | enum/null | 双端 FASTQ 的 `r1` 或 `r2` |

执行端必须原样保留 `sample_role`、`mate` 和 accession 字段，不得按 assets 数组
位置重新推断 tumor/normal 或 R1/R2。

### 5.2 Tool step 与 input 绑定

每个步骤至少包含：

```json
{
  "step_id": "bwa",
  "tool_id": "bwa_mem_paired",
  "inputs": {}
}
```

原子工具的 `tool_id` 固定使用对应 Knowledge Card 的 `meta.id`。Neo4j 中的
`bwa`、`star`、`samtools` 等短 ID 只用于 MCP 内部路由，不会出现在原子步骤的
对外 `tool_chain.tool_id` 中。未展开的 pipeline 仍使用 pipeline 自身的正式 ID。

输入键和 `from.output` 同样必须使用 Knowledge Card 中声明的名称。输入支持四种形状。

绑定已有资产：

```json
{
  "read1": {
    "asset_id": "EXAMPLE-tumor-r1"
  }
}
```

绑定上游正式输出：

```json
{
  "read1": {
    "from": {
      "step_id": "tumor_fastp",
      "output": "trimmed_r1"
    }
  }
}
```

绑定字面值：

```json
{
  "remove_duplicates": {"value": true}
}
```

聚合数组输入：

```json
{
  "qc_files": {
    "sources": [
      {"from": {"step_id": "fastqc", "output": "zip_reports"}},
      {"from": {"step_id": "samtools", "output": "stats"}},
      {"from": {"step_id": "featurecounts", "output": "summary"}}
    ],
    "flatten": true
  }
}
```

`sources` 中每项必须是一个 `asset_id` 或 `from`。若来源输出本身是
`Array[File]`，执行端在 `flatten=true` 时将其展开后再组装目标数组。

`from.output` 必须是源工具在目录登记的正式 output 名，不能用文件名、artifact 名或
自然语言别名替代。

### 5.3 原子工具 ID 示例

| 内部短 ID | 对外 `tool_id` |
|---|---|
| `fastp` | `fastp_paired_end` |
| `bwa` | `bwa_mem_paired` |
| `star` | `star_rrna_and_genome_alignment` |
| `rsem` | `rsem_quantification` |
| `samtools` | `samtools_alignment_processing` |
| `featurecounts` | `featurecounts_gene_counting` |
| `gatk` | `gatk_wes_somatic` |
| `bcftools` | `bcftools_somatic_postprocess` |
| `snpeff` | `snpeff_annotation` |

`fastqc`、`trim_galore`、`multiqc` 的内部短 ID 与 Knowledge Card `meta.id` 相同。

## 6. Standard ready 完整实例

以下为脱敏实例。`diff_expr_go` 尚无 HAS_STEP，因此保持单 pipeline 节点并明确标注
`pipeline_level_unexpanded`。

```json
{
  "schema_version": "tool-chain/v1",
  "selection_status": "ready",
  "orchestration_status": "ready",
  "orchestration_ready": true,
  "orchestration_message": "标准流程与工具链结构已确定。",
  "workflow_mode": "standard",
  "intent": {
    "query_text": "用 TPM 表达矩阵做差异分析和 GO 富集",
    "analysis_goal": "差异表达与 GO 富集",
    "requested_outputs": ["差异表达表", "GO 富集表"]
  },
  "workflow_plan": {
    "mode": "standard",
    "pipeline_ids": ["diff_expr_go"],
    "reference_pipeline_ids": [],
    "execution_status": "ready"
  },
  "agent_input": {
    "execution_kind": "tool_chain",
    "workflow_mode": "standard",
    "match_id": "match-example-standard",
    "study_accession": "EXAMPLE001",
    "assets": [
      {
        "asset_id": "EXAMPLE001-expression-1",
        "role": "expression_matrix",
        "path": "/data/EXAMPLE001/genes-TPM.tsv",
        "format": "tsv",
        "path_verified": false,
        "source": "T2",
        "sample_accession": null,
        "run_accession": null,
        "individual_accession": null,
        "sample_role": null,
        "mate": null
      }
    ],
    "tool_chain": [
      {
        "step_id": "diff_expr_go",
        "tool_id": "diff_expr_go",
        "inputs": {
          "expression_matrix": {
            "asset_id": "EXAMPLE001-expression-1"
          }
        },
        "decomposition_status": "pipeline_level_unexpanded",
        "expandable": false
      }
    ],
    "feasibility": {
      "status": "ready",
      "missing_assets": [],
      "data_ready": true,
      "message": "流程所需的用户样本数据已匹配。"
    },
    "selection_reason": "登记的标准流程覆盖该请求。",
    "orchestration_status": "ready",
    "orchestration_ready": true,
    "orchestration_message": "标准流程与工具链结构已确定。",
    "extensions": {
      "quality_gates": {},
      "plan_validation": {"ok": true, "errors": []},
      "contract_validation": {"ok": true, "errors": []}
    },
    "pipeline_id": "diff_expr_go",
    "files": ["/data/EXAMPLE001/genes-TPM.tsv"],
    "files_text": "/data/EXAMPLE001/genes-TPM.tsv"
  },
  "force_custom": false,
  "data_matcher_mode": "neo4j"
}
```

`rnaseq_singletask` 是例外：它有锁定 HAS_STEP，默认展开为
`fastqc → trim_galore → star → rsem/samtools → featurecounts → multiqc` 七个步骤。
传 `expand_standard_steps=false` 才返回旧的单 pipeline 节点形状。

## 7. 配对 WES custom `agent_input` 实例

下面实例展示四条 FASTQ 如何按 `sample_role + mate` 进入两条独立链，并在 GATK
汇合。参考基因组、索引和 `interval_list` 由执行端托管，不作为用户 asset 返回。

```json
{
  "execution_kind": "tool_chain",
  "workflow_mode": "custom",
  "match_id": "match-example-paired-wes",
  "study_accession": "EXAMPLE-WES",
  "assets": [
    {
      "asset_id": "EXAMPLE-tumor-r1",
      "role": "fastq_r1",
      "path": "/data/tumor_R1.fq.gz",
      "format": "fq.gz",
      "path_verified": false,
      "source": "T1",
      "sample_accession": "TUMOR-SAMPLE",
      "run_accession": "TUMOR-RUN",
      "individual_accession": "IND-001",
      "sample_role": "tumor",
      "mate": "r1"
    },
    {
      "asset_id": "EXAMPLE-tumor-r2",
      "role": "fastq_r2",
      "path": "/data/tumor_R2.fq.gz",
      "format": "fq.gz",
      "path_verified": false,
      "source": "T1",
      "sample_accession": "TUMOR-SAMPLE",
      "run_accession": "TUMOR-RUN",
      "individual_accession": "IND-001",
      "sample_role": "tumor",
      "mate": "r2"
    },
    {
      "asset_id": "EXAMPLE-normal-r1",
      "role": "fastq_r1",
      "path": "/data/normal_R1.fq.gz",
      "format": "fq.gz",
      "path_verified": false,
      "source": "T1",
      "sample_accession": "NORMAL-SAMPLE",
      "run_accession": "NORMAL-RUN",
      "individual_accession": "IND-001",
      "sample_role": "normal",
      "mate": "r1"
    },
    {
      "asset_id": "EXAMPLE-normal-r2",
      "role": "fastq_r2",
      "path": "/data/normal_R2.fq.gz",
      "format": "fq.gz",
      "path_verified": false,
      "source": "T1",
      "sample_accession": "NORMAL-SAMPLE",
      "run_accession": "NORMAL-RUN",
      "individual_accession": "IND-001",
      "sample_role": "normal",
      "mate": "r2"
    }
  ],
  "tool_chain": [
    {
      "step_id": "tumor_fastp",
      "tool_id": "fastp_paired_end",
      "inputs": {
        "sample_id": {"value": "TUMOR-SAMPLE"},
        "read1": {"asset_id": "EXAMPLE-tumor-r1"},
        "read2": {"asset_id": "EXAMPLE-tumor-r2"}
      },
      "depends_on": []
    },
    {
      "step_id": "tumor_bwa",
      "tool_id": "bwa_mem_paired",
      "inputs": {
        "sample_id": {"value": "TUMOR-SAMPLE"},
        "read1": {
          "from": {"step_id": "tumor_fastp", "output": "trimmed_r1"}
        },
        "read2": {
          "from": {"step_id": "tumor_fastp", "output": "trimmed_r2"}
        }
      },
      "depends_on": ["tumor_fastp"]
    },
    {
      "step_id": "tumor_samtools",
      "tool_id": "samtools_alignment_processing",
      "inputs": {
        "sample_id": {"value": "TUMOR-SAMPLE"},
        "alignment": {
          "from": {"step_id": "tumor_bwa", "output": "aligned_sam"}
        },
        "remove_duplicates": {"value": true}
      },
      "depends_on": ["tumor_bwa"]
    },
    {
      "step_id": "normal_fastp",
      "tool_id": "fastp_paired_end",
      "inputs": {
        "sample_id": {"value": "NORMAL-SAMPLE"},
        "read1": {"asset_id": "EXAMPLE-normal-r1"},
        "read2": {"asset_id": "EXAMPLE-normal-r2"}
      },
      "depends_on": []
    },
    {
      "step_id": "normal_bwa",
      "tool_id": "bwa_mem_paired",
      "inputs": {
        "sample_id": {"value": "NORMAL-SAMPLE"},
        "read1": {
          "from": {"step_id": "normal_fastp", "output": "trimmed_r1"}
        },
        "read2": {
          "from": {"step_id": "normal_fastp", "output": "trimmed_r2"}
        }
      },
      "depends_on": ["normal_fastp"]
    },
    {
      "step_id": "normal_samtools",
      "tool_id": "samtools_alignment_processing",
      "inputs": {
        "sample_id": {"value": "NORMAL-SAMPLE"},
        "alignment": {
          "from": {"step_id": "normal_bwa", "output": "aligned_sam"}
        },
        "remove_duplicates": {"value": true}
      },
      "depends_on": ["normal_bwa"]
    },
    {
      "step_id": "gatk",
      "tool_id": "gatk_wes_somatic",
      "inputs": {
        "tumor_bam": {
          "from": {"step_id": "tumor_samtools", "output": "sorted_bam"}
        },
        "tumor_bai": {
          "from": {"step_id": "tumor_samtools", "output": "sorted_bai"}
        },
        "normal_bam": {
          "from": {"step_id": "normal_samtools", "output": "sorted_bam"}
        },
        "normal_bai": {
          "from": {"step_id": "normal_samtools", "output": "sorted_bai"}
        }
      },
      "depends_on": ["tumor_samtools", "normal_samtools"]
    }
  ],
  "feasibility": {
    "status": "ready",
    "missing_assets": [],
    "data_ready": true,
    "message": "流程所需的用户样本数据已匹配。"
  },
  "selection_reason": "需要 tumor/normal 双链后汇合进行体细胞变异检测。",
  "orchestration_status": "draft",
  "orchestration_ready": false,
  "orchestration_message": "自定义方法链草案已形成，仍需执行端物化。",
  "extensions": {
    "quality_gates": {},
    "plan_validation": {"ok": true, "errors": []},
    "contract_validation": {"ok": true, "errors": []}
  },
  "pipeline_id": null,
  "files": [
    "/data/tumor_R1.fq.gz",
    "/data/tumor_R2.fq.gz",
    "/data/normal_R1.fq.gz",
    "/data/normal_R2.fq.gz"
  ],
  "files_text": "/data/tumor_R1.fq.gz\n/data/tumor_R2.fq.gz\n/data/normal_R1.fq.gz\n/data/normal_R2.fq.gz"
}
```

custom 的 `draft` 表示目录引用和结构校验通过，但执行端仍需完成 WDL/运行环境物化；
它不等于 `orchestration_ready=true`。

## 8. Capability information 实例

能力问答不可执行：

```json
{
  "execution_kind": "information",
  "workflow_mode": "capability",
  "match_id": "capability-example",
  "study_accession": null,
  "assets": [],
  "tool_chain": [],
  "feasibility": {
    "status": "not_applicable",
    "missing_assets": [],
    "data_ready": null,
    "message": "这是能力目录查询，不生成执行流程。"
  },
  "selection_reason": "用户询问当前目录能力。",
  "orchestration_status": "information",
  "orchestration_ready": false,
  "orchestration_message": "这是能力目录查询。",
  "extensions": {
    "capability_answer": {
      "pipelines": [],
      "atomic_tools": []
    },
    "plan_validation": {"ok": true, "errors": []},
    "contract_validation": {"ok": true, "errors": []}
  },
  "pipeline_id": null,
  "files": [],
  "files_text": ""
}
```

## 9. 执行门禁

执行 Agent 只有在以下条件**全部成立**时才允许提交运行：

```text
JSON-RPC 没有 error
AND agent_input.execution_kind == "tool_chain"
AND selection_status == "ready"
AND agent_input.orchestration_status == "ready"
AND agent_input.orchestration_ready == true
AND agent_input.feasibility.status == "ready"
AND agent_input.extensions.contract_validation.ok == true
```

以下状态一律不能直接执行：

- `information`：只是能力答案；
- `missing_assets` / `missing_data`：缺用户数据或数据类型不匹配；
- `no_match`：没有形成通过合同校验的链；
- `draft`：custom 结构有效，但仍需执行端物化；
- JSON-RPC `error.code=-32602`：参数或 custom chain 非法；
- JSON-RPC `error.code=-32001`：Neo4j、matcher 或依赖异常。

禁止为了执行而忽略 `contract_validation`、补猜 output 名、按数组位置配对资产，
或把 `path_verified=false` 直接解释成数据不存在。

## 10. Schema 与完整示例文件

交付包内同时提供：

| 文件 | 用途 |
|---|---|
| `schemas/agent_input.schema.json` | 深度校验 `agent_input` |
| `schemas/tool_chain_output.schema.json` | 校验完整 `route_pipeline_request` structuredContent |
| `schemas/agent_input.examples.json` | standard/custom/capability 脱敏实例 |
| `schemas/agent_tool_chain_schema.example.json` | 完整 `tool-chain/v1` 单例 |

Schema 使用 JSON Schema Draft 2020-12。调用方应把 schema 文件纳入自己的 CI，
对磁带、演示返回和线上结果执行合同校验。

## 11. 超时建议

| 调用 | 建议 timeout |
|---|---:|
| health、目录、validate、availability | 10 秒 |
| standard route | 30 秒 |
| custom route（使用内部 LLM） | 120 秒 |

如果调用方 Agent 自带模型，优先使用
`list_workflow_methods → validate_tool_chain → query_data_availability`，可避免内部 custom
规划的 30–60 秒模型耗时。
