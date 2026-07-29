# Neo4j NEXT 关系校正说明

## 目的

本次只校正 `data/csv/relations/tool_relationship.csv` 中已经由工具目录声明的
`NEXT` 关系，不修改工具名称、功能、输入输出语义或适用组学。

`NEXT` 表示一个工具在流程顺序上可以跟随另一个工具。它不是文件绑定关系；
真正的输入来源必须继续通过 input slot、output slot、artifact type 和 format 校验。

## 校正结果

原表包含 17 条关系，校正后保留 14 条，删除 3 条。

| 删除关系 | 原因 |
| --- | --- |
| `T18 fq_to_ubam -> T03 BWA` | uBAM 不能直接作为 BWA 的 FASTQ 输入；规范链路还需要 SamToFastq、BWA-MEM 和 MergeBamAlignment 等步骤，当前工具闭集中无法忠实表达。 |
| `T13 diff_expr_go -> T12 MultiQC` | GO 富集结果不是 MultiQC 的标准输入，二者不存在稳定的数据依赖。 |
| `T14 diff_expr_kegg -> T12 MultiQC` | Reactome/通路富集结果不是 MultiQC 的标准输入，二者不存在稳定的数据依赖。 |

保留的主链如下：

```text
WES/DNA:
fastp -> FastQC -> BWA -> SAMtools -> GATK -> BCFtools -> SnpEff
                            \-> featureCounts -> MultiQC

RNA-seq:
FastQC -> Trim Galore -> STAR -> RSEM -> MultiQC
                              \-> SAMtools -> featureCounts -> MultiQC
```

其中 `FastQC -> BWA`、`FastQC -> Trim Galore`、`SnpEff -> MultiQC` 和
`RSEM -> MultiQC` 只表示允许的执行顺序或报告汇总关系。编排器不得把 FastQC
报告当成 FASTQ，也不得把分析结果文件直接当成 MultiQC 输入；数据绑定仍需走
正式 slot/artifact 契约。

## 尚未处理的边界

- 当前工具闭集中没有 `SamToFastq` 和 `MergeBamAlignment`，因此不保留
  `fq_to_ubam -> BWA` 的直接关系。
- `GATK -> BCFtools` 只表示通用 VCF 后处理候选。Mutect2 场景仍应先经过
  `FilterMutectCalls`；当前目录未注册该独立工具。
- 本次不新增师姐未声明的 NEXT，不推测 WGCNA、聚类、突变景观或生存分析的
  下游关系。

## 对补充改动清单的取舍

补充清单中的以下项目已经由校正版满足：

- 删除 `diff_expr_go -> MultiQC` 和 `diff_expr_kegg -> MultiQC`；
- 不存在 `STAR -> featureCounts` 短路，保留 `STAR -> SAMtools -> featureCounts`；
- 删除 `paired_fastq_to_unmapped_bam -> BWA`；
- 使用 `FastQC -> Trim Galore`，不存在反向 `Trim Galore -> FastQC`；
- 保留 `STAR -> SAMtools`。

没有采纳 `featureCounts -> diff_expr_go` 和
`featureCounts -> diff_expr_kegg` 两条直连。原因不是保守，而是当前正式输入输出契约
明确不兼容：featureCounts 输出 `Raw Counts`，两个差异流程的 WDL 和 knowledge card
均声明仅接受 `FPKM/TPM`，并通过 `quant_type` 限定为 FPKM 或 TPM。直接连接会让
NEXT 顺序看似合理，但无法形成合法的数据绑定。

未来只有满足下列任一条件后才能增加这两条路径：

1. 注册 `Raw Counts -> TPM/FPKM` 的正式定量/标准化工具；或
2. 注册能直接消费 Raw Counts 的 DESeq2/edgeR/limma-voom 差异分析工具。

在此之前，模型应把该路径报告为方法缺口，不得用格式同为 TSV 作为兼容依据。

## Neo4j 同步规则

- `catalog_id` 使用 CSV 中的 `T01` 至 `T23`。
- `tool_id` 使用稳定、可读、适合 agent 输出的工具标识。
- 已有 pipeline 节点保留原 `tool_id` 和全部 slot，只补充 `catalog_id`。
- 默认 `--apply` 会先确认 NEXT 两端工具已存在，缺失时直接报错，不自动创建或改写工具。
- 默认同步只重建带 `source='curated-next-csv'` 的 `NEXT` 关系，不触碰工具名称、功能、slot、artifact、format、`HAS_STEP` 或其他关系。
- `--bootstrap-catalog` 仅用于新库首次初始化，不属于本次 NEXT 校正的常规同步路径。

## 验收标准

1. Neo4j 中 23 个 catalog tool 均可按 `catalog_id` 查询。
2. `NEXT {source:'curated-next-csv'}` 恰好 14 条。
3. 不存在 `T18 -> T03`、`T13 -> T12`、`T14 -> T12`。
4. 所有 NEXT 起点和终点都存在，且没有自环。
5. 自助餐只能选择 Neo4j 返回的工具，并同时通过 NEXT 与 artifact/slot 校验。

## 后续显式授权的契约修复

这两项不属于原始 NEXT 校正，是后续测试发现且单独确认后执行的定向修复：

- BWA 输出从错误的 `unmapped_bam` 改为 `aligned_bam`；STAR 的基因组比对 BAM
  从语义过重的 `sorted_dedup_bam` 改为 `aligned_bam`，与 SAMtools 输入精确衔接。
  `sorted_dedup_bam -> aligned_bam` 仍保留为一般性的子类兼容规则。
- FastQC/MultiQC 的报告 artifact 从错误的 `sample_metadata` 改为
  `quality_control_report`；MultiQC 报告输入为可选，不直接解析表达矩阵。

对应迁移脚本为 `fix_bam_artifact_contracts.py` 和 `fix_qc_report_contracts.py`，
二者均不修改 NEXT。
