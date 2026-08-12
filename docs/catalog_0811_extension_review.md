# 0811 工具目录扩展评审单

由 `scripts/python/extend_catalog_from_senior_0811.py` 生成。

## 1. catalog_id 重映射（2 位 -> 3 位）

| tool_id | 旧 | 新 |
|---|---|---|
| bcftools | T06 | T009 |
| bwa | T03 | T006 |
| diff_expr_go | T13 | T029 |
| diff_expr_kegg | T14 | T030 |
| driver_gene_gender_analysis | T15 | T031 |
| fastp | T01 | T001 |
| fastqc | T02 | T002 |
| featurecounts | T11 | T012 |
| gatk | T05 | T008 |
| her2_pfs_survival | T16 | T032 |
| immune_infiltration_iobr | T17 | T033 |
| multiqc | T12 | T013 |
| paired_fastq_to_unmapped_bam | T18 | T034 |
| rnaseq_singletask | TASK_RNASEQ_SINGLETASK | T059 |
| rnaseq_unsupervised_cluster | T19 | T035 |
| rsem | T10 | T011 |
| samtools | T04 | T007 |
| snpeff | T07 | T010 |
| star | T09 | T005 |
| survival_analysis | T20 | T036 |
| tmb_survival_analysis | T21 | T037 |
| trim_galore | T08 | T004 |
| wes_somatic_maf_landscape | T22 | T038 |
| wgcna | T23 | T039 |

## 2. 新增 27 个工具（全部登记为 pipeline）

| catalog_id | tool_id | 输入槽 | 输出槽 | 适用组学 |
|---|---|---|---|---|
| T003 | cellranger_workflow | raw_fastq_read, aligned_bam | quality_control_report, tabular_bio_data, aligned_bam | sc-RNA, bulk_RNA |
| T040 | bootstrap_stability | （无） | tabular_bio_data, visualization_result | bulk_RNA |
| T041 | breast_cellchat | scrna_object_rds, genome_annotation | visualization_result, quality_control_report | sc-RNA, bulk_RNA |
| T042 | celltype_case_control_de | scrna_object_rds, tabular_bio_data, genome_annotation | quality_control_report | sc-RNA, bulk_RNA |
| T043 | cnvkit_cnv_clinical | aligned_bam, tabular_bio_data, clinical_table | visualization_result, tabular_bio_data | WGS, WES, Clinical |
| T044 | cox_model | tabular_bio_data, clinical_table, sample_metainfo | quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T045 | dataset_downstream | scrna_object_rds, tabular_bio_data, genome_annotation | quality_control_report | sc-RNA |
| T046 | dataset_matrix_annotation | scrna_object_rds, tabular_bio_data, genome_annotation | quality_control_report | sc-RNA |
| T047 | de_enrichment | tabular_bio_data, clinical_table, sample_metainfo | quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T048 | deg_enrichment | tabular_bio_data, clinical_table, sample_metainfo | quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T049 | deg_trend | tabular_bio_data, clinical_table, sample_metainfo | visualization_result, quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T050 | gene_boxplot | tabular_bio_data, clinical_table, sample_metainfo | quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T051 | gsea_pathway_enrichment | tabular_bio_data | tabular_bio_data, visualization_result, quality_control_report | bulk_RNA |
| T052 | hvg_pca_gmm | （无） | tabular_bio_data, quality_control_report, visualization_result | sc-RNA, bulk_RNA |
| T053 | immunotherapy_cellchat | scrna_object_rds, genome_annotation | visualization_result, quality_control_report | sc-RNA |
| T054 | ipf_trajectory_regulon | scrna_object_rds, sample_metainfo, genome_annotation | quality_control_report | sc-RNA, bulk_RNA |
| T055 | km_survival | tabular_bio_data, clinical_table, sample_metainfo | quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T056 | lung_tme_annotation_cnv | scrna_object_rds, tabular_bio_data, genome_annotation | quality_control_report | sc-RNA |
| T057 | preprocess_counts | tabular_bio_data | tabular_bio_data, quality_control_report | bulk_RNA |
| T058 | rmats_alternative_splicing | transcriptome_bam, genome_annotation | aligned_bam, tabular_bio_data, quality_control_report, visualization_result | bulk_RNA |
| T060 | scrna_cell_communication | tabular_bio_data, scrna_object_rds, sample_metainfo | tabular_bio_data, scrna_object_rds, quality_control_report, visualization_result | sc-RNA, bulk_RNA |
| T061 | stage_heatmap | tabular_bio_data, clinical_table, sample_metainfo | visualization_result, quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T062 | tcell_intervention | scrna_object_rds, tabular_bio_data, sample_metainfo, genome_annotation | quality_control_report | sc-RNA, bulk_RNA |
| T063 | umap | tabular_bio_data, clinical_table, sample_metainfo | visualization_result, quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T064 | wes_somatic_pair | raw_fastq_read_r1, raw_fastq_read_r2, interval_list, genome_annotation, unfiltered_vcf | aligned_bam, unfiltered_vcf, variant_index_tbi, quality_control_report | WGS, WES |
| T065 | wgcna_hub | tabular_bio_data, clinical_table, sample_metainfo | quality_control_report, tabular_bio_data | bulk_RNA, Clinical |
| T066 | wgcna_module_trait | tabular_bio_data, clinical_table, sample_metainfo | quality_control_report, tabular_bio_data | bulk_RNA, Clinical |

## 3. 待确认：可提升为 atomic 的候选

以下工具的 0811 输入输出是干净的单步签名，但 0811 的 `tool_relationship.csv`
只覆盖 T001-T013，它们目前一条 NEXT 边都没有。没有 NEXT 边的 atomic 工具
无法出现在任何合法链路里，正是当初 multiqc 必须被特判绕开的那种情况。
所以本次一律登记为 pipeline，提升需要同时人工补 NEXT 四元组。

| tool_id | 单步理由 |
|---|---|
| gsea_pathway_enrichment | GSEA 单个可执行程序，单输入单步 |
| preprocess_counts | 单步计数矩阵预处理：TABULAR_BIO_DATA 进，TABULAR_BIO_DATA + QC 出 |
| rmats_alternative_splicing | rMATS 单个可执行程序，转录组 BAM 进 |
| umap | UMAP 单一降维算法，无多工具编排 |

## 4. 无法原子化：0811 未声明任何输入

- T040 bootstrap_stability
- T052 hvg_pca_gmm

## 5. 未映射的语义格式

无。

## 6. 扩展后目录规模

- tools: 51
- io_slots: 241
- artifact_types: 43
- catalog_formats: 31
- catalog_functions: 62
- relationships: 1166
