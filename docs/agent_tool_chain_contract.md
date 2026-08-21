# 知识图谱 MCP 工具链返回格式

## 1. 用途

知识图谱 MCP 根据用户问题返回：

- 用户想做什么分析；
- 分析需要哪些工具；
- 已匹配到哪些数据文件；
- 工具之间如何衔接。


## 2. 返回格式

```json
{
  "schema_version": "tool-chain/v1",
  "selection_status": "ready",
  "intent": {},
  "agent_input": {}
}
```

### 顶层字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `schema_version` | 是 | 固定填写 `tool-chain/v1`。 |
| `selection_status` | 是 | 匹配状态，例如 `ready`、`missing_assets`、`no_match`。 |
| `intent` | 是 | 用户问题和分析目标。 |
| `agent_input` | 是 | 数据资产和工具链。 |

## 3. `intent`

```json
{
  "query_text": "使用 RNA-seq count 数据进行无监督聚类，并评估聚类稳定性。",
  "analysis_goal": "RNA-seq 无监督聚类和稳定性评估",
  "requested_outputs": [
    "样本聚类结果",
    "PCA 聚类图",
    "聚类稳定性结果"
  ]
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `query_text` | 是 | 用户原始问题。 |
| `analysis_goal` | 是 | 归纳后的分析目标。 |
| `requested_outputs` | 否 | 用户希望获得的结果。 |

## 4. `assets`

`assets` 表示知识图谱已经匹配到的现有数据文件。

```json
{
  "asset_id": "HRA00XXXX-counts",
  "role": "count_matrix",
  "path": "/data/HRA00XXXX/genes-counts.tsv",
  "format": "tsv"
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `asset_id` | 是 | 文件唯一标识，供工具输入引用。 |
| `role` | 是 | 文件用途，例如 `count_matrix`、`clinical_file`。 |
| `path` | 是 | 执行端可以访问的文件路径。 |
| `format` | 否 | 文件格式，例如 `tsv`、`xlsx`、`maf`。 |
| `sample_attribution` | 是 | 样本级字段（`sample_id`/`sample_name`/`sample_role`/`read_pair` 等）为空时的**原因**，取值见下。 |
| `sample_attribution_note` | 是 | 同上，给人看的一句话解释；`per_sample` 时为空串。 |

### 4.1 样本级字段为空，先看 `sample_attribution` 再下结论

同样一片 null，含义可能完全相反，**不要一律当成「数据缺失」**：

| 取值 | 含义 | 该怎么办 |
| --- | --- | --- |
| `per_sample` | 样本归属已解析，样本级字段有值 | 正常使用 |
| `cohort_aggregate` | 队列级聚合文件（表达矩阵、MAF、临床表、sc-RNA 队列产物），**不属于任何单个样本** | 空值属正常，照常提交；别去补样本号 |
| `attribution_missing` | 文件名带 `HRI*`/`HRS*` 样本号，本该定位到样本，但图内缺 `generated_from`/`in_sample` 边 | **这是真缺口**，如实报给用户，不要猜样本归属 |

来历：0821 师兄看富集分析的 plan 时问「数据有的是 null」。查证后富集用的
`HRA001272-Genes-TPM-1.0.tsv` 在图里确实没有 `generated_from`、没有 `in_sample`、
`run_accession` 也是 null——**那是队列级矩阵的本质，不是漏查**。但当时输出里没有
任何东西能说明这点，而隔壁 WES 的逐样本 VCF 也是一片 null，原因却是图里缺边。

0821 实测 35,572 个 T2 的分布：31,313 有血缘；3,676 无血缘但文件名带样本号
（`HRI147472.svaba.somatic.indel.vcf` 这类，属 `attribution_missing`）；179 文件名里
没有任何样本号（属 `cohort_aggregate`）。判据用**文件名里有没有样本号**，不用
`run_accession` 是否为空——后者会把那 3,676 个逐样本文件一起划进「本来就没有」，
等于把真缺口盖成正常现象。全量交叉验证：判成 `cohort_aggregate` 的 179 个在图里
确实全都没有血缘，零误报。

## 5. `tool_chain`

`tool_chain` 表示需要调用的工具以及它们之间的输入关系。

```json
{
  "step_id": "cluster",
  "tool_id": "hvg_pca_gmm",
  "inputs": {
    "logcpm_tsv": {
      "from": {
        "step_id": "preprocess",
        "output": "normalized_logcpm_tsv"
      }
    }
  }
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `step_id` | 是 | 本次工具链中一次工具调用的唯一标识，供上下游关系引用。 |
| `tool_id` | 是 | 原子步骤使用 Knowledge Card 的 `meta.id`；未展开 pipeline 使用 pipeline 正式 ID。 |
| `inputs` | 是 | 工具输入来自哪个文件或哪个上游工具。 |

### 输入来自已有文件

```json
{
  "count_tsv": {
    "asset_id": "HRA00XXXX-counts"
  }
}
```

表示 `count_tsv` 使用知识图谱找到的 `HRA00XXXX-counts` 文件。

### 输入来自上游工具

```json
{
  "logcpm_tsv": {
    "from": {
      "step_id": "preprocess",
      "output": "normalized_logcpm_tsv"
    }
  }
}
```

表示：

- 上游步骤的 `step_id` 是 `preprocess`；
- 使用上游产生的 `normalized_logcpm_tsv`；
- 将该结果作为当前工具的 `logcpm_tsv` 输入。

原子步骤的 `inputs` 键和 `from.output` 必须使用 Knowledge Card 中声明的名称。
Neo4j 的短 ID 只用于 MCP 内部路由、`NEXT` 和 `HAS_STEP` 校验，不对执行 Agent 输出。

## 6. 完整示例

```json
{
  "schema_version": "tool-chain/v1",
  "selection_status": "ready",
  "intent": {
    "query_text": "使用 HRA00XXXX 的 RNA-seq count 数据进行无监督聚类，并评估聚类稳定性。",
    "analysis_goal": "RNA-seq 无监督聚类和稳定性评估",
    "requested_outputs": [
      "样本聚类结果",
      "PCA 聚类图",
      "聚类稳定性结果"
    ]
  },
  "agent_input": {
    "execution_kind": "tool_chain",
    "match_id": "match-HRA00XXXX-rnaseq-cluster-001",
    "study_accession": "HRA00XXXX",
    "assets": [
      {
        "asset_id": "HRA00XXXX-counts",
        "role": "count_matrix",
        "path": "/data/HRA00XXXX/HRA00XXXX-Genes-counts-1.0.tsv",
        "format": "tsv"
      }
    ],
    "tool_chain": [
      {
        "step_id": "preprocess",
        "tool_id": "preprocess_counts",
        "inputs": {
          "count_tsv": {
            "asset_id": "HRA00XXXX-counts"
          }
        }
      },
      {
        "step_id": "cluster",
        "tool_id": "hvg_pca_gmm",
        "inputs": {
          "logcpm_tsv": {
            "from": {
              "step_id": "preprocess",
              "output": "normalized_logcpm_tsv"
            }
          }
        }
      },
      {
        "step_id": "stability",
        "tool_id": "bootstrap_stability",
        "inputs": {
          "logcpm_tsv": {
            "from": {
              "step_id": "preprocess",
              "output": "normalized_logcpm_tsv"
            }
          }
        }
      }
    ],
    "feasibility": {
      "status": "ready",
      "missing_assets": []
    },
    "selection_reason": "RNA-seq count 矩阵需要先进行预处理；预处理结果可以同时用于聚类和稳定性分析。"
  }
}
```

这个示例表示：

```text
preprocess_counts
      ├──→ hvg_pca_gmm
      └──→ bootstrap_stability
```

知识图谱不需要单独返回 `edges`。执行端会根据两个工具中的 `inputs.from` 自动生成依赖关系。



## 8. 基本要求

知识图谱返回前只需检查：

1. 每个步骤的 `step_id` 唯一；
2. `tool_id` 使用双方约定的正式工具名称；
3. `asset_id` 能在 `assets` 中找到；
4. `from.step_id` 指向存在的上游步骤；
5. `from.output` 使用上游工具正式定义的输出名称；
6. 工具链不存在循环依赖。

## 9. 本 MCP 的兼容扩展

本实现保持以上必填字段不变，并增加以下可选信息：

- `agent_input.workflow_mode`：`standard`、`custom` 或 `capability`；
- `agent_input.extensions.quality_gates`：标准 pipeline 的已知代码或科学口径风险；
- `agent_input.extensions.contract_validation`：asset、step、正式 output 引用与顺序校验结果；
- `agent_input.extensions.unverified_paths`：已匹配但未在当前 MCP 主机验证存在性的路径；
- `selection_status=draft`：自助餐方法链结构有效，但尚待执行端物化为执行流程；
- `selection_status=requires_review`：保留给旧调用端兼容；当前编排器只展示质量风险，
  不再用执行端实现风险阻断流程编排。
- `selection_status=information`：能力目录问答，不代表执行成功或失败；此时
  `agent_input.execution_kind=information`、`tool_chain=[]`、`feasibility.status=not_applicable`，
  具体目录位于 `capability_answer` 和 `agent_input.extensions.capability_answer`。

过渡期间还保留 `pipeline_id`、`files`、`files_text`，旧调用端可以继续读取；新 agent 应以 `assets` 和 `tool_chain` 为准。

`feasibility` 仅由用户样本数据决定。FASTQ、表达/计数矩阵、MAF、BAM/VCF、
Clinical 和 MetaInfo 缺失可进入 `missing_assets`。GTF、参考基因组、STAR/RSEM 索引等
执行端托管资源，以及所有运行参数，都不由本 MCP 收集或展示，也不影响
`selection_status` 与 `orchestration_status`。

## 10. 标准展开与配对样本

- `route_pipeline_request` 默认 `expand_standard_steps=true`。有 `HAS_STEP` 的 `rnaseq_singletask` 返回 7 个 atomic step；传 `false` 可取旧的单 pipeline 节点形状。
- 其余 11 个 pipeline 没有 `HAS_STEP`，仍返回单节点，并显式标记 `decomposition_status=pipeline_level_unexpanded`、`expandable=false`。
- 原子步骤对外 `tool_id` 使用 Knowledge Card `meta.id`；Neo4j 短 ID 只用于内部路由和 NEXT/HAS_STEP 校验。
- 原子步骤的 input 键与 `from.output` 使用 Knowledge Card 名称。`value` 表示标量，`sources + flatten=true` 表示聚合数组输入。
- MultiQC 的 `qc_files` 显式聚合已登记的报告输出，不再返回空 inputs 或仅依赖 order-only NEXT。
- 配对 FASTQ asset 增加 `sample_role`、`mate`、`individual_accession`、`sample_accession`、`run_accession`。执行端必须保留这些字段，不得按数组位置重新配对。
- 内部 fastp/GATK variant 仍负责配对安全；输出边界将合法双端 fastp 转为 `fastp_paired_end.read1/read2`，将配对 GATK 转为 `gatk_wes_somatic`。Knowledge Card 不支持的单端 fastp 或单样本 GATK 会失败关闭。

`query_data_availability` 接受且只接受 `pipeline_ids` 或 `steps` 之一。`steps` 会先经过与 `validate_tool_chain` 相同的闭集校验，再从正式 input 槽推导资产角色；非法 chain 返回参数错误，合法但无数据返回 `not_available`。

## recommendations[].data.alternatives（数据集选择）

每条业务推荐除了选中的那组数据，还会给出其他可用的数据集，供前端做选择器。
第一条 `selected=true`，与 `data.assets` 是同一组，所以只读旧字段的调用方不受影响。

```jsonc
"alternatives": [
  {
    "study_accession": "HRA000021",
    "study_title": "ESCC WGS study",
    "tumor_type": "esophageal cancer",
    "individual_accession": "HRI035286",   // 配对分析才有；同一 study 会有多个病人
    "label": "HRA000021 · esophageal cancer · 个体 HRI035286",
    "selected": true,
    "assets": [ /* 与 data.assets 同构 */ ],
    "matched_count": 4,
    "study_accessions": ["HRA000021"],
    "sample_roles": {"tumor": 818, "normal": 812, "unresolved": 2},
    "role_resolved": true,                 // tumor 和 normal 都判得出，配对/分组分析可做
    "execution_params": {                  // 直接可提交，键是真实 WDL 参数名
      "tumor_r1": "/hpcdisk1/.../HRR067348_1.fastq.gz",
      "tumor_r2": "/hpcdisk1/.../HRR067348_2.fastq.gz",
      "normal_r1": "/hpcdisk1/.../HRR067347_1.fastq.gz",
      "normal_r2": "/hpcdisk1/.../HRR067347_2.fastq.gz"
    },
    "execution_params_missing": [],
    "submittable": true                    // execution_params 齐全且无缺项
  }
]
```

用于渲染选择器的三个字段：

- `label` —— 直接可显示的一行文字，不要显示裸文件路径。
- `submittable` —— 参数是否齐全。为 false 时可以列出但应置灰，
  `execution_params_missing` 里是缺哪个参数。
- `role_resolved` —— 该 study 能否判出 tumor/normal。差异表达要分组、
  配对分析要角色时，为 false 的数据集选了也做不了。

切换数据集不需要再请求一次：每组都自带 `execution_params`，直接换用即可。

数量上限 10 组。配对分析的多组是**同一 study 的不同病人**（`individual_accession`
不同），非配对分析的多组通常是**不同 study**。
