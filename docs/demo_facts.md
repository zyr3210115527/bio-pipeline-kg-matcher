# Demo 事实清单（现跑）

生成时间：2026-07-24T02:21:44Z

## 1. Neo4j 工具目录

- atomic 工具数：12
- pipeline/task_pipeline 数：12
- 工具节点总数：24
- NEXT data 边：11
- NEXT order 边：3
- Neo4j 连接状态：connected

## 2. CSV 数据规模

- study 数：14
- individual 数：3494
- sample 数：6918
- T1 文件数：13772
- T11 文件数：15484
- T2 文件数：86
- T1 strategy 分布：{"WES": 8922, "RNA-Seq": 3028, "scRNA-Seq": 1290, "WGS": 532}
- T1 无 format 列；T11 format 分布：{"fq.gz": 5362, "fastq.gz": 9106, "bam": 1016}

## 3. T11 不可见记录

- T11 中未被 T1 覆盖：1712 条
- 按 study：{"HRA000122": 696, "HRA000021": 1016}
- 按 format：{"fq.gz": 696, "bam": 1016}

## 4. 格式/角色标注疑似矛盾

- 扫描到矛盾项：0

## 5. Study × Pipeline 真值表摘要

- 总格数：182
- 系统判定可行：39
- 系统判定不可行：143

## 6. Pipeline 覆盖率

| pipeline | 涉及 study 数 | 可行 study 数 |
|---|---|---|
| cellranger_workflow | 13 | 2 |
| diff_expr_go | 13 | 4 |
| diff_expr_kegg | 13 | 4 |
| driver_gene_gender_analysis | 13 | 1 |
| her2_pfs_survival | 13 | 0 |
| immune_infiltration_iobr | 13 | 0 |
| paired_fastq_to_unmapped_bam | 13 | 7 |
| rnaseq_singletask | 13 | 4 |
| rnaseq_unsupervised_cluster | 13 | 4 |
| survival_analysis | 13 | 1 |
| tmb_survival_analysis | 13 | 1 |
| wes_somatic_maf_landscape | 13 | 9 |
| wes_somatic_pair | 13 | 2 |
| wgcna | 13 | 0 |

## 7. 零覆盖 Pipeline

- her2_pfs_survival
- immune_infiltration_iobr
- wgcna

## 8. 演示查询 Token 与成本估算

| 查询 | 平均 tokens | 估算成本 USD |
|---|---|---|
| 配对肿瘤正常 WES | 10433.0 | 1.0433 |
| trim_to_fastp | 12402.0 | 1.2402 |
| 双端 FASTQ RNA-seq 上游 | 4713.0 | 0.4713 |
| TPM 聚类 | 6619.0 | 0.6619 |
| GO+KEGG 富集 | 5614.0 | 0.5614 |
| 单样本 WES FASTQ | 11520.0 | 1.152 |

## 9. 原始覆盖明细（前 30 条）

| study | pipeline | feasible | reason |
|---|---|---|---|
| HRA000021 | cellranger_workflow | False | 缺少FASTQ 测序数据（R1/R2），无法执行「cellranger_workflow」，请补充对应数据后再运行。 |
| HRA000021 | diff_expr_go | False | 缺少TPM/FPKM 表达丰度矩阵，无法执行「diff_expr_go」，请补充对应数据后再运行。 |
| HRA000021 | diff_expr_kegg | False | 缺少TPM/FPKM 表达丰度矩阵，无法执行「diff_expr_kegg」，请补充对应数据后再运行。 |
| HRA000021 | driver_gene_gender_analysis | False | 缺少临床数据（Clinical）、样本信息（MetaInfo），无法执行「driver_gene_gender_anal |
| HRA000021 | her2_pfs_survival | False | 缺少表达矩阵、临床数据（Clinical）、样本信息（MetaInfo），无法执行「her2_pfs_survival」 |
| HRA000021 | immune_infiltration_iobr | False | 缺少表达矩阵、临床数据（Clinical）、样本信息（MetaInfo），无法执行「immune_infiltratio |
| HRA000021 | paired_fastq_to_unmapped_bam | False | 缺少FASTQ 测序数据（R1/R2），无法执行「paired_fastq_to_unmapped_bam」，请补充对应 |
| HRA000021 | rnaseq_singletask | False | 缺少FASTQ 测序数据（R1/R2），无法执行「rnaseq_singletask」，请补充对应数据后再运行。 |
| HRA000021 | rnaseq_unsupervised_cluster | False | 缺少原始 count 表达矩阵，无法执行「rnaseq_unsupervised_cluster」，请补充对应数据后再运 |
| HRA000021 | survival_analysis | False | 缺少临床数据（Clinical）、样本信息（MetaInfo），无法执行「survival_analysis」，请补充对 |
| HRA000021 | tmb_survival_analysis | False | 缺少临床数据（Clinical）、样本信息（MetaInfo），无法执行「tmb_survival_analysis」， |
| HRA000021 | wes_somatic_maf_landscape | True | 所需数据角色齐全，可以执行。 |
| HRA000021 | wes_somatic_pair | False | 缺少FASTQ 测序数据（R1/R2），无法执行「wes_somatic_pair」，请补充对应数据后再运行。 |
| HRA000021 | wgcna | False | 缺少表达矩阵、临床数据（Clinical）、样本信息（MetaInfo），无法执行「wgcna」，请补充对应数据后再运行 |
| HRA000071 | cellranger_workflow | False | 「cellranger_workflow」需要 scRNA-Seq 测序数据，当前匹配到的 FASTQ 为 WES，无法 |
| HRA000071 | diff_expr_go | False | 缺少TPM/FPKM 表达丰度矩阵，无法执行「diff_expr_go」，请补充对应数据后再运行。 |
| HRA000071 | diff_expr_kegg | False | 缺少TPM/FPKM 表达丰度矩阵，无法执行「diff_expr_kegg」，请补充对应数据后再运行。 |
| HRA000071 | driver_gene_gender_analysis | True | 所需数据角色齐全，可以执行。 |
| HRA000071 | her2_pfs_survival | False | 缺少表达矩阵，无法执行「her2_pfs_survival」，请补充对应数据后再运行。 |
| HRA000071 | immune_infiltration_iobr | False | 缺少表达矩阵，无法执行「immune_infiltration_iobr」，请补充对应数据后再运行。 |
| HRA000071 | paired_fastq_to_unmapped_bam | True | 所需数据角色齐全，可以执行。 |
| HRA000071 | rnaseq_singletask | False | 「rnaseq_singletask」需要 RNA-Seq 测序数据，当前匹配到的 FASTQ 为 WES，无法直接使用 |
| HRA000071 | rnaseq_unsupervised_cluster | False | 缺少原始 count 表达矩阵，无法执行「rnaseq_unsupervised_cluster」，请补充对应数据后再运 |
| HRA000071 | survival_analysis | True | 所需数据角色齐全，可以执行。 |
| HRA000071 | tmb_survival_analysis | True | 所需数据角色齐全，可以执行。 |
| HRA000071 | wes_somatic_maf_landscape | True | 所需数据角色齐全，可以执行。 |
| HRA000071 | wes_somatic_pair | False | 「wes_somatic_pair」需要为 study 登记肿瘤/正常角色规则；当前 matched 的 study 均 |
| HRA000071 | wgcna | False | 缺少表达矩阵，无法执行「wgcna」，请补充对应数据后再运行。 |
| HRA000074 | cellranger_workflow | False | 「cellranger_workflow」需要 scRNA-Seq 测序数据，当前匹配到的 FASTQ 为 RNA-Se |
| HRA000074 | diff_expr_go | True | 所需数据角色齐全，可以执行。 |
