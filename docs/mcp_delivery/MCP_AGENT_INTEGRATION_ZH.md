# MCP Agent 接入合同

## 1. 定位

本 MCP 只做流程编排和数据匹配，不执行生信任务。`route_pipeline_request` 对每个普通分析请求只调用一次 LLM，由 LLM 同时生成 1-3 条业务 pipeline 推荐和 1-5 条有序原子链。服务端为业务推荐查询 Neo4j 工具节点和数据证据，并对原子链逐条做闭集、槽位、NEXT、数据完整性、资产绑定和 Knowledge Card 校验。

标准流程/预制菜执行模式已取消。`recommendations[]` 可以展示 Neo4j 的 pipeline/task_pipeline 节点及数据，但不表示执行链；`candidates[].tool_chain` 仍只包含 `tool_kind=atomic` 的工具。系统不从 WDL 或未拆解流程中编造步骤。

## 2. 调用

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "route_pipeline_request",
    "arguments": {
      "query": "双端 RNA-seq FASTQ 生成表达丰度和 count 矩阵",
      "top_k": 3,
      "data_matcher_mode": "neo4j"
    }
  }
}
```

`query` 必填；`top_k` 取 1-3，默认 3。不要再传 `force_custom` 或 `expand_standard_steps`。`include_internal=true` 仅供诊断，会额外返回 LLM 分析和候选淘汰原因。

MCP 返回值同时出现在 `result.structuredContent` 和 `result.content[0].text`。Agent 应优先读取结构化值。

## 3. `tool-chain/v2`

顶层稳定字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定 `tool-chain/v2` |
| `selection_status` | enum | `ready`、`unsupported`、`no_candidate`、`information` |
| `candidate_count` | integer | 0-3，等于 `candidates.length` |
| `candidates` | array | 按 `rank` 排序的候选链 |
| `recommendation_count` | integer | 0-3，等于 `recommendations.length` |
| `recommendations` | array | 业务 pipeline、Neo4j 工具详情和逐文件数据证据 |
| `unsupported_reason` | string/null | 无法原子化或无候选时的解释 |
| `intent` | object | 规则抽取的查询意图，不是执行参数 |
| `planner_metadata` | object | LLM 状态、模型、一次调用及 token 信息 |
| `data_matcher_mode` | enum | 本次数据后端 |

每个 `candidate` 独立拥有：

| 字段 | 说明 |
|---|---|
| `rank` | 1 最贴合；只用于本次响应内排序 |
| `match_note` | 推荐侧重或差异 |
| `workflow_mode` | 固定 `custom` |
| `match_id` | 本次候选标识，不保证跨调用稳定 |
| `validation_ok` | 榜内固定为 `true` |
| `feasibility_status` | 榜内固定为 `ready`，表示用户样本数据完整，不表示任务已执行 |
| `study_accession` | 数据组合所属 study，允许 null |
| `assets` | 该候选独立的数据资产 |
| `tool_chain` | Knowledge Card 执行 ID、输入名和依赖绑定 |
| `extensions` | 配对 matcher、内部 ID、合同校验等诊断信息 |

`ready` 只表示“编排合同已通过且用户样本数据完整”。线程、内存、参考基因组、GTF、索引、interval list 等由执行端管理，不影响本 MCP 的编排成功状态。

每个 `recommendation` 的 `tool.catalog_status` 为 `registered` 或 `missing_from_neo4j`。`data.status` 为 `available` 或 `missing_from_graph`；`data.assets[].graph_status` 逐文件说明图谱是否确认，缺失文件不会带虚构路径。`recommendations[]` 是信息层，不能直接当作 atomic 执行链。

### 3.1 `execution_params`（可直接投递的参数）

每个 `recommendation` 另带 `execution_params` 与 `execution_params_missing`，把 `data.assets` 转成 PipelineBuilder 可直接投递的键值：

| 字段 | 说明 |
|---|---|
| `execution_params` | `{真实参数名: 真实路径}`。键 = 该流程 `knowledge_card.yaml` 的 `interface.params[].name`（即图内 `io_slot.builder_param`，如 `maf_file`/`counts_tsv`），**不是** slot 名，也不是 `wdl_target`；值 = `data.assets` 里已被图谱确认的真实文件路径。多文件流程给多个键（如 wgcna → `counts_tsv`/`clinical_xls`/`metainfo_xlsx`）。 |
| `execution_params_missing` | 无法解析出确认路径的数据参数清单（`param`/`slot`/`role`/`reason`）。**绝不臆造路径**。 |

**值可能是字符串，也可能是字符串数组。** WDL 侧为 `Array[File]` 的参数返回**路径数组**（fastqc 的 `fastqs`、multiqc 的 `qc_files`、cnvkit 的 `tumor_bams`/`tumor_bais`/`normal_bams`/`normal_bais`、rmats 的 `group1_bams`/`group2_bams` 等），其余返回单个路径字符串。这是规格第 2 条的原有要求，0823 才真正落地——此前这些参数被压成单值，执行端按数组解会崩，或者更糟：scatter 只跑第一个样本，不报错只是少做。**消费方不要假定 `execution_params` 的值一定是 `str`**；`cnvkit` 的四个数组按同下标配对（第 i 个 tumor_bam 对第 i 个 tumor_bai），不得重排。

`reason` 目前有两个取值，**处置对象不同，不要合并处理**：

| `reason` | 含义 | 谁来修 |
|---|---|---|
| `no_confirmed_path` | 参数绑定正确，但图里没有该资产的确认路径（如 T1 FASTQ 的 `file_path=NOT_FOUND`） | 数据侧补 `file_path` |
| `slot_not_bound` | 该输入槽在 `data/csv/catalog/io_slot.csv` 里没有 `builder_param`，映射不到 WDL 参数。此时 `param` 为 `null` | MCP 侧补目录表，待确认清单见 `docs/待确认_builder_param.md` |

`slot_not_bound` 是 0823 新增。此前这类槽被无声跳过，回包是 `execution_params: {}` 且
`execution_params_missing: []`——等于宣称"零个参数、且一个都不缺"，按 `not missing` 判可提交
就会把一个绑不上参数的流程当成能跑的。新增取值是加法，不影响已有消费逻辑；但**如果你按
`reason` 做过白名单分支，需要放行这个新值**。参考文件槽和别名行仍然不报。

> 0823 收口后，`io_slot.csv` 的 122 个输入槽已全部绑定（余下 5 条是 `variant_alias_for`
> 别名行，按设计留空且不上报），故 `slot_not_bound` 在当前目录下不应再出现。保留该取值是
> 为了将来新接工具时不再回到"无声跳过"。

规则：只映射图谱确认的**数据**输入；参考基因组 / 索引 / GTF / interval / PoN 等有卡片默认值的参考资源不出现在 `execution_params` 里（既不映射也不报缺）。用户选定某条后，可直接 `{pipeline_id, params: <execution_params>}` 投递。

> 注意：上游 FASTQ（T1）在参考数据里 `file_path` 为 `NOT_FOUND`，故 rnaseq / 配对 WES 等以 fastq 为输入的流程，其 `sample_r1`/`sample_r2` 会进入 `execution_params_missing`，需数据侧补齐 `file_path` 后才能给出真实路径。maf / 表达矩阵 / 临床 / metainfo 等 T2 产物路径齐全，可直接给出。

## 4. Agent 消费规则

1. 先检查 `schema_version == "tool-chain/v2"`。
2. 读取 `recommendations[]` 展示业务流程与数据；仅在 `selection_status == "ready"` 时执行 `candidates[]`。
3. 两个数组都按 `rank` 展示；不要把 recommendation 当作 candidate 执行，也不要默认所有候选都执行。
4. 选择某条后，只使用该条自己的 `assets`、`tool_chain`、`study_accession` 和 `match_id`，禁止跨候选拼接。
5. `asset_id` 绑定用户数据；`from.step_id/from.output` 绑定前序产物；`value` 是字面量；`sources` 是多来源聚合。
6. 保留 tumor/normal 的 `sample_role` 和 R1/R2 的 `mate`，不得按数组位置重新配对。
7. 不依赖步骤列表或 `match_id` 跨调用判等；LLM 可以合法给出另一条已验证链。

## 5. 无结果

- `unsupported`：需求依赖尚未原子化能力，例如差异表达、GO/KEGG 富集、WGCNA 或生存分析。不得转而执行 pipeline-level 节点。
- `no_candidate`：LLM 未给出可用链，或所有候选在严格校验/完整数据匹配中被淘汰。不是空成功。
- `information`：目录浏览请求，或只有业务推荐而没有可执行 atomic 候选；使用返回的信息，不执行工作流。

候选因数据不足被淘汰时，不会以 `missing_assets` 状态混入 Top-3。`include_internal=true` 可查看 `extensions.rejected_candidates[].stage`，取值包括 `validation`、`data_matching`、`asset_binding` 和 `contract_validation`。

## 6. 配对 WES

配对候选只有在同时存在 tumor/normal 两条分支及 GATK 四槽时，才走专用配对数据匹配。每个候选独立匹配，不共享资产选择状态。合法结果应有四条 FASTQ，并满足：

- tumor R1/R2 的 `sample_role=tumor`，normal R1/R2 的 `sample_role=normal`；
- mate 分别为 `r1`、`r2`；
- GATK 的 tumor/normal BAM 与 BAI 绑定到对应分支；
- 打乱资产数组顺序不改变绑定。

当前 Knowledge Card 尚未登记 `GATK -> BCFtools` 所需的 filtered VCF index。完整过滤/注释链会严格阻断，不能由 Agent 假造索引；仅到 GATK 未过滤 VCF 的配对链可正常返回。
> **0823 已修正，上一段作废。** GATK 的 `GatkWesSomaticWorkflow` 内部就跑了 `FilterMutectCalls`，
> workflow 同时输出 `unfiltered_vcf` / `unfiltered_vcf_index` / `filtered_vcf` / `filtered_vcf_index`，
> 只是槽表当初只建了前者。现已补齐 `gatk::output::filtered_vcf` + `filtered_vcf_index` 与
> `bcftools::input::filtered_vcf_index`，`GATK -> BCFtools` 走**过滤后**的 VCF，完整链不再阻断。
>
> 顺带修掉一条静默错误：BCFtools 的输入槽原名 `unfiltered_vcf`，与 GATK 的同名输出对接，
> 于是 Mutect2 的**原始** VCF 被喂给 `bcftools view -f PASS`。FILTER 注记要 `FilterMutectCalls`
> 之后才存在——这条线不报错，只安静地给出空的 PASS 集合。如果你的下游对 0823 之前的
> 空结果做过兜底，可以撤掉了。

## 7. 其他六个工具

`list_pipeline_capabilities` 和 `list_workflow_methods` 是目录查询，不代表数据可用。`validate_tool_chain` 只校验原子链。`query_data_availability` 要求 `intent` 加且只加 `pipeline_ids` 或 `steps` 之一。`health_check` 检查 Neo4j 与统一图合同。`render_pipeline_answer` 把 v2 候选渲染成中文摘要。

## 8. v1 迁移

原先读取 `agent_input.tool_chain` 的代码改为遍历 `candidates[i].tool_chain`；`agent_input.assets/study_accession/match_id` 同理下移到 candidate。删除 standard/custom 分支、`force_custom`、`expand_standard_steps` 以及把 Top1 复制回旧 `agent_input` 的兼容逻辑。

正式 JSON Schema 见 `schemas/tool_chain_output.schema.json`。
