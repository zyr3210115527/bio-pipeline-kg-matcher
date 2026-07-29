# DeepSeek + Neo4j 四问路由实例

测试日期：2026-07-22  
模型：`deepseek-v4-pro` (`thinking=enabled`, `reasoning_effort=high`)  
工具真源：本机 Neo4j 2026.06.0

## Neo4j 目录快照

- 24 个 tool：12 atomic、11 pipeline、1 task pipeline。
- 14 条审核后的 `NEXT`。
- `rnaseq_singletask` 有 7 条锁定 `HAS_STEP`：
  `fastqc -> trim_galore -> star -> {rsem, samtools -> featurecounts} -> multiqc`。
- 公共运行时不解析 WDL 工具，Neo4j 不可用时也不会回退到 WDL。

## 正常模式

| # | 用户问题摘要 | 模型判定 | 返回的 Neo4j 流程 | 数据状态 |
| --- | --- | --- | --- | --- |
| 1 | paired-end RNA-seq，指定 FastQC/Trim Galore/rRNA/STAR/RSEM/FeatureCounts/MultiQC | `standard` | `rnaseq_singletask`，展开为 7 个 Neo4j atomic tool | `ready` |
| 2 | 双端 RNA-seq 质控、剪切、比对、表达计数 | `standard` | `rnaseq_singletask`，展开为 7 个 Neo4j atomic tool | `ready` |
| 3 | RNA-seq FASTQ 完整上游分析 | `standard` | `rnaseq_singletask`，展开为 7 个 Neo4j atomic tool | `ready` |
| 4 | FASTQ 转 GATK 后续使用的 uBAM | `standard` | `paired_fastq_to_unmapped_bam` pipeline-level Neo4j tool | `ready` |
| 5 | 能做什么 / 有哪些流程处理 MAF | `capability` | 返回 Neo4j 能力目录，不生成 tool chain | `information` |
| 6 | 从 RNA-seq FASTQ 到表达矩阵选哪个流程 | `standard` | `rnaseq_singletask` | `ready` |
| 7 | 完整 RNA 上游去掉 RSEM，仅保留 featureCounts | `custom` | 6 个已登记 atomic tool 的方法链 | `draft` |
| 8 | 把 RSEM 换成尚未登记的 Salmon | `custom` | 报告 decomposition gap，不编造 tool | `no_match` |

前三问已匹配用户的 R1/R2 FASTQ，因此状态为 `ready`。`rrna_star_index`、
`star_genome_index`、`rsem_index` 和 `gtf_file` 属于执行端按物种/参考版本托管的资源，
不进入 `missing_assets`。运行参数同样不进入请求、展示或状态判定。

四问的 LLM 分类均为一次调用完成，模型字段均为
`deepseek-v4-pro`；预制菜的所有展示步骤均带 `source=neo4j`。返回中未出现
`RNASeqAnalysis`、`wdl_path` 或旧 26-task 目录。

## 强制自助餐

`force_custom=true` 只绕过预制菜判定，不放宽 atomic tool、slot 或 NEXT 约束。

| # | 结果 | 模型给出的关键依据 |
| --- | --- | --- |
| 1 | 成功生成 7 步完整链 | `fastqc -> trim_galore -> star -> {samtools -> featurecounts, rsem} -> multiqc`，`validation.ok=true`。 |
| 2 | 生成可表达的 `fastqc -> trim_galore -> star -> rsem` | 覆盖质控、剪切、比对和 RSEM 表达定量；FastQC raw/clean FASTQ 已改为可选候选输入，不再要求两者同时存在。 |
| 3 | 成功生成 7 步完整链 | 泛化“完整上游分析”也能稳定返回同一 Neo4j atomic recipe，`validation.ok=true`。 |
| 4 | `steps=[]`，返回 decomposition gap | atomic 目录没有 FASTQ-to-uBAM/FastqToSam；uBAM 是未比对 BAM，不能用 BWA 链代替。 |

工具契约已将 BWA 输出从 uBAM 校正为 `aligned_bam`，STAR 的主基因组 BAM 输出也
校正为 `aligned_bam`，与 SAMtools 输入精确匹配；同时仍显式允许
`sorted_dedup_bam -> aligned_bam` 子类兼容。FastQC/MultiQC
报告也从 `sample_metadata` 校正为 `quality_control_report`。因此预制菜的锁定 recipe
和强制自助餐现在都能表达完整 RNA 链。

## 提示词与稳定性修正

- 自助餐必须覆盖全部用户目标，不能只返回“最小差异”。
- 最终产物无法产生时返回 `steps=[] + decomposition_gaps`，不用无法衔接的部分链伪装完成。
- 明确 uBAM 与 aligned BAM 的语义边界。
- 将 `LLM_MAX_TOKENS` 从 4000 提高到 8000，并对自助餐的非 JSON 返回最多重试一次。
- 统一 LLM 客户端对瞬时连接错误最多重试一次，标准选择和自助餐都受保护，日志不包含凭证或完整 endpoint。
- 明确 `step_id` 必须是非数字字符串；对模型偶发返回的唯一数字 ID 做确定性规范化，并同步改写 `from`/`depends_on` 引用。
- 自助餐验证器现在会确定性比较上游 output artifact 和下游 input artifact，不再只依赖模型自己发现 slot 冲突。
- 明确 MultiQC 不解析 RSEM/FeatureCounts 表达矩阵；其步骤仅直接依赖 `rsem` 与 `featurecounts`，日志由执行端收集。

## NEXT 导入边界

`scripts/python/sync_neo4j_tool_catalog.py --apply` 默认只删除并重建
`source='curated-next-csv'` 的 NEXT。实际导入前后对全部工具、slot、artifact、format、
function、`HAS_STEP` 及其他非 NEXT 关系计算指纹，SHA-256 完全一致。
因此原始 NEXT 校正没有改动师姐登记的工具功能或输入输出。
后续经明确确认单独执行了 BAM artifact 和 QC report 两个定向契约修复，未改动 NEXT。
