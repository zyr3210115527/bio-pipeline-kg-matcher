# Fix C: Catalog Reproducibility

## Pre-Fix Difference Evidence

This appendix was generated from read-only production and an isolated legacy CSV bootstrap. Relationship identity includes type, both canonical endpoints, and the complete property object.

| Graph | Nodes | Relationships | Fingerprint |
|---|---:|---:|---|
| Production | 218 | 548 | `439dff931e236038985e50ce7f821e69736917f38440dfa408735ac89f57de1f` |
| Legacy CSV bootstrap | 122 | 253 | `bdd04bd94a8f73e35c4dff377ea04b9a1466120053c107b50029d68528b042ec` |

Missing production relationships: **301**. Incorrect extra CSV mappings: **6**.

### Missing Relationship Counts

| Type | Count |
|---|---:|
| `ALLOW_FORMAT` | 77 |
| `HAS_FUNCTION` | 11 |
| `HAS_INPUT_SLOT` | 24 |
| `HAS_OUTPUT_SLOT` | 31 |
| `INPUT` | 21 |
| `MANIFEST_AS` | 45 |
| `OUTPUT` | 37 |
| `PRODUCES` | 31 |
| `REQUIRES` | 24 |

### Complete 301 Missing Relationships

#### ALLOW_FORMAT (77)

| Start | End | Properties |
|---|---|---|
| `io_slot:diff_expr_go::in::expression` | `format:tsv` | `{}` |
| `io_slot:diff_expr_go::out::differential` | `format:tsv` | `{}` |
| `io_slot:diff_expr_go::out::enrichment` | `format:tsv` | `{}` |
| `io_slot:diff_expr_kegg::in::expression` | `format:tsv` | `{}` |
| `io_slot:diff_expr_kegg::out::differential` | `format:tsv` | `{}` |
| `io_slot:diff_expr_kegg::out::enrichment` | `format:tsv` | `{}` |
| `io_slot:driver_gene_gender_analysis::in::clinical` | `format:xls` | `{}` |
| `io_slot:driver_gene_gender_analysis::in::clinical` | `format:xlsx` | `{}` |
| `io_slot:driver_gene_gender_analysis::in::maf` | `format:maf` | `{}` |
| `io_slot:driver_gene_gender_analysis::in::metainfo` | `format:xlsx` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::figures` | `format:pdf` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::figures` | `format:png` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::matrix` | `format:gz` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::matrix` | `format:tsv` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::statistics` | `format:tsv` | `{}` |
| `io_slot:her2_pfs_survival::in::clinical` | `format:xls` | `{}` |
| `io_slot:her2_pfs_survival::in::clinical` | `format:xlsx` | `{}` |
| `io_slot:her2_pfs_survival::in::expression` | `format:tsv` | `{}` |
| `io_slot:her2_pfs_survival::in::metainfo` | `format:xlsx` | `{}` |
| `io_slot:her2_pfs_survival::out::figures` | `format:pdf` | `{}` |
| `io_slot:her2_pfs_survival::out::figures` | `format:png` | `{}` |
| `io_slot:her2_pfs_survival::out::statistics` | `format:tsv` | `{}` |
| `io_slot:her2_pfs_survival::out::summary` | `format:json` | `{}` |
| `io_slot:her2_pfs_survival::out::summary` | `format:txt` | `{}` |
| `io_slot:immune_infiltration_iobr::in::clinical` | `format:xls` | `{}` |
| `io_slot:immune_infiltration_iobr::in::clinical` | `format:xlsx` | `{}` |
| `io_slot:immune_infiltration_iobr::in::expression` | `format:tsv` | `{}` |
| `io_slot:immune_infiltration_iobr::in::metainfo` | `format:xlsx` | `{}` |
| `io_slot:immune_infiltration_iobr::out::figures` | `format:pdf` | `{}` |
| `io_slot:immune_infiltration_iobr::out::figures` | `format:png` | `{}` |
| `io_slot:immune_infiltration_iobr::out::fractions` | `format:tsv` | `{}` |
| `io_slot:immune_infiltration_iobr::out::qc` | `format:json` | `{}` |
| `io_slot:immune_infiltration_iobr::out::qc` | `format:tsv` | `{}` |
| `io_slot:immune_infiltration_iobr::out::qc` | `format:txt` | `{}` |
| `io_slot:multiqc::input::quality_control_report` | `format:html` | `{}` |
| `io_slot:multiqc::input::quality_control_report` | `format:tsv` | `{}` |
| `io_slot:multiqc::input::quality_control_report` | `format:zip` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::in::fastq_1` | `format:fq.gz` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::in::fastq_2` | `format:fq.gz` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::out::bam` | `format:bam` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::out::list` | `format:list` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::in::counts` | `format:tsv` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::out::assignments` | `format:tsv` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::out::figures` | `format:pdf` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::out::figures` | `format:png` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::out::stability` | `format:tsv` | `{}` |
| `io_slot:survival_analysis::in::clinical` | `format:xls` | `{}` |
| `io_slot:survival_analysis::in::clinical` | `format:xlsx` | `{}` |
| `io_slot:survival_analysis::in::maf` | `format:maf` | `{}` |
| `io_slot:survival_analysis::in::metainfo` | `format:xlsx` | `{}` |
| `io_slot:survival_analysis::out::figures` | `format:pdf` | `{}` |
| `io_slot:survival_analysis::out::figures` | `format:png` | `{}` |
| `io_slot:survival_analysis::out::statistics` | `format:txt` | `{}` |
| `io_slot:tmb_survival_analysis::in::clinical` | `format:xls` | `{}` |
| `io_slot:tmb_survival_analysis::in::clinical` | `format:xlsx` | `{}` |
| `io_slot:tmb_survival_analysis::in::maf` | `format:maf` | `{}` |
| `io_slot:tmb_survival_analysis::in::metainfo` | `format:xlsx` | `{}` |
| `io_slot:tmb_survival_analysis::out::figures` | `format:pdf` | `{}` |
| `io_slot:tmb_survival_analysis::out::figures` | `format:png` | `{}` |
| `io_slot:tmb_survival_analysis::out::statistics` | `format:json` | `{}` |
| `io_slot:tmb_survival_analysis::out::statistics` | `format:tsv` | `{}` |
| `io_slot:tmb_survival_analysis::out::tmb` | `format:tsv` | `{}` |
| `io_slot:wes_somatic_maf_landscape::in::maf` | `format:maf` | `{}` |
| `io_slot:wes_somatic_maf_landscape::out::figures` | `format:pdf` | `{}` |
| `io_slot:wes_somatic_maf_landscape::out::figures` | `format:png` | `{}` |
| `io_slot:wes_somatic_maf_landscape::out::maf` | `format:maf` | `{}` |
| `io_slot:wes_somatic_maf_landscape::out::statistics` | `format:tsv` | `{}` |
| `io_slot:wgcna::in::clinical` | `format:xls` | `{}` |
| `io_slot:wgcna::in::clinical` | `format:xlsx` | `{}` |
| `io_slot:wgcna::in::counts` | `format:tsv` | `{}` |
| `io_slot:wgcna::in::metainfo` | `format:xlsx` | `{}` |
| `io_slot:wgcna::out::archives` | `format:gz` | `{}` |
| `io_slot:wgcna::out::figures` | `format:pdf` | `{}` |
| `io_slot:wgcna::out::figures` | `format:png` | `{}` |
| `io_slot:wgcna::out::hub_genes` | `format:tsv` | `{}` |
| `io_slot:wgcna::out::modules` | `format:tsv` | `{}` |
| `io_slot:wgcna::out::qc` | `format:tsv` | `{}` |

#### HAS_FUNCTION (11)

| Start | End | Properties |
|---|---|---|
| `tool_id:diff_expr_go` | `function:差异表达与 GO 富集分析` | `{}` |
| `tool_id:diff_expr_kegg` | `function:差异表达与 Reactome 通路富集分析流程` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `function:驱动基因突变频率性别分层分析` | `{}` |
| `tool_id:her2_pfs_survival` | `function:HER2 表达与无进展生存期分析` | `{}` |
| `tool_id:immune_infiltration_iobr` | `function:免疫浸润分析 (IOBR CIBERSORT)` | `{}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `function:双端 FASTQ 转未比对 BAM` | `{}` |
| `tool_id:rnaseq_unsupervised_cluster` | `function:RNA-seq 无监督聚类分析流程` | `{}` |
| `tool_id:survival_analysis` | `function:生存分析流程` | `{}` |
| `tool_id:tmb_survival_analysis` | `function:肿瘤突变负荷生存分析流程` | `{}` |
| `tool_id:wes_somatic_maf_landscape` | `function:WES 体细胞突变 MAF 景观分析流程` | `{}` |
| `tool_id:wgcna` | `function:WGCNA 加权基因共表达网络分析` | `{}` |

#### HAS_INPUT_SLOT (24)

| Start | End | Properties |
|---|---|---|
| `tool_id:diff_expr_go` | `io_slot:diff_expr_go::in::expression` | `{"order":1}` |
| `tool_id:diff_expr_kegg` | `io_slot:diff_expr_kegg::in::expression` | `{"order":1}` |
| `tool_id:driver_gene_gender_analysis` | `io_slot:driver_gene_gender_analysis::in::clinical` | `{"order":2}` |
| `tool_id:driver_gene_gender_analysis` | `io_slot:driver_gene_gender_analysis::in::maf` | `{"order":1}` |
| `tool_id:driver_gene_gender_analysis` | `io_slot:driver_gene_gender_analysis::in::metainfo` | `{"order":3}` |
| `tool_id:her2_pfs_survival` | `io_slot:her2_pfs_survival::in::clinical` | `{"order":2}` |
| `tool_id:her2_pfs_survival` | `io_slot:her2_pfs_survival::in::expression` | `{"order":1}` |
| `tool_id:her2_pfs_survival` | `io_slot:her2_pfs_survival::in::metainfo` | `{"order":3}` |
| `tool_id:immune_infiltration_iobr` | `io_slot:immune_infiltration_iobr::in::clinical` | `{"order":2}` |
| `tool_id:immune_infiltration_iobr` | `io_slot:immune_infiltration_iobr::in::expression` | `{"order":1}` |
| `tool_id:immune_infiltration_iobr` | `io_slot:immune_infiltration_iobr::in::metainfo` | `{"order":3}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `io_slot:paired_fastq_to_unmapped_bam::in::fastq_1` | `{"order":1}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `io_slot:paired_fastq_to_unmapped_bam::in::fastq_2` | `{"order":2}` |
| `tool_id:rnaseq_unsupervised_cluster` | `io_slot:rnaseq_unsupervised_cluster::in::counts` | `{"order":1}` |
| `tool_id:survival_analysis` | `io_slot:survival_analysis::in::clinical` | `{"order":2}` |
| `tool_id:survival_analysis` | `io_slot:survival_analysis::in::maf` | `{"order":1}` |
| `tool_id:survival_analysis` | `io_slot:survival_analysis::in::metainfo` | `{"order":3}` |
| `tool_id:tmb_survival_analysis` | `io_slot:tmb_survival_analysis::in::clinical` | `{"order":2}` |
| `tool_id:tmb_survival_analysis` | `io_slot:tmb_survival_analysis::in::maf` | `{"order":1}` |
| `tool_id:tmb_survival_analysis` | `io_slot:tmb_survival_analysis::in::metainfo` | `{"order":3}` |
| `tool_id:wes_somatic_maf_landscape` | `io_slot:wes_somatic_maf_landscape::in::maf` | `{"order":1}` |
| `tool_id:wgcna` | `io_slot:wgcna::in::clinical` | `{"order":2}` |
| `tool_id:wgcna` | `io_slot:wgcna::in::counts` | `{"order":1}` |
| `tool_id:wgcna` | `io_slot:wgcna::in::metainfo` | `{"order":3}` |

#### HAS_OUTPUT_SLOT (31)

| Start | End | Properties |
|---|---|---|
| `tool_id:diff_expr_go` | `io_slot:diff_expr_go::out::differential` | `{"order":1}` |
| `tool_id:diff_expr_go` | `io_slot:diff_expr_go::out::enrichment` | `{"order":2}` |
| `tool_id:diff_expr_kegg` | `io_slot:diff_expr_kegg::out::differential` | `{"order":1}` |
| `tool_id:diff_expr_kegg` | `io_slot:diff_expr_kegg::out::enrichment` | `{"order":2}` |
| `tool_id:driver_gene_gender_analysis` | `io_slot:driver_gene_gender_analysis::out::figures` | `{"order":3}` |
| `tool_id:driver_gene_gender_analysis` | `io_slot:driver_gene_gender_analysis::out::matrix` | `{"order":2}` |
| `tool_id:driver_gene_gender_analysis` | `io_slot:driver_gene_gender_analysis::out::statistics` | `{"order":1}` |
| `tool_id:her2_pfs_survival` | `io_slot:her2_pfs_survival::out::figures` | `{"order":2}` |
| `tool_id:her2_pfs_survival` | `io_slot:her2_pfs_survival::out::statistics` | `{"order":1}` |
| `tool_id:her2_pfs_survival` | `io_slot:her2_pfs_survival::out::summary` | `{"order":3}` |
| `tool_id:immune_infiltration_iobr` | `io_slot:immune_infiltration_iobr::out::figures` | `{"order":3}` |
| `tool_id:immune_infiltration_iobr` | `io_slot:immune_infiltration_iobr::out::fractions` | `{"order":1}` |
| `tool_id:immune_infiltration_iobr` | `io_slot:immune_infiltration_iobr::out::qc` | `{"order":2}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `io_slot:paired_fastq_to_unmapped_bam::out::bam` | `{"order":1}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `io_slot:paired_fastq_to_unmapped_bam::out::list` | `{"order":2}` |
| `tool_id:rnaseq_unsupervised_cluster` | `io_slot:rnaseq_unsupervised_cluster::out::assignments` | `{"order":1}` |
| `tool_id:rnaseq_unsupervised_cluster` | `io_slot:rnaseq_unsupervised_cluster::out::figures` | `{"order":3}` |
| `tool_id:rnaseq_unsupervised_cluster` | `io_slot:rnaseq_unsupervised_cluster::out::stability` | `{"order":2}` |
| `tool_id:survival_analysis` | `io_slot:survival_analysis::out::figures` | `{"order":2}` |
| `tool_id:survival_analysis` | `io_slot:survival_analysis::out::statistics` | `{"order":1}` |
| `tool_id:tmb_survival_analysis` | `io_slot:tmb_survival_analysis::out::figures` | `{"order":3}` |
| `tool_id:tmb_survival_analysis` | `io_slot:tmb_survival_analysis::out::statistics` | `{"order":2}` |
| `tool_id:tmb_survival_analysis` | `io_slot:tmb_survival_analysis::out::tmb` | `{"order":1}` |
| `tool_id:wes_somatic_maf_landscape` | `io_slot:wes_somatic_maf_landscape::out::figures` | `{"order":3}` |
| `tool_id:wes_somatic_maf_landscape` | `io_slot:wes_somatic_maf_landscape::out::maf` | `{"order":1}` |
| `tool_id:wes_somatic_maf_landscape` | `io_slot:wes_somatic_maf_landscape::out::statistics` | `{"order":2}` |
| `tool_id:wgcna` | `io_slot:wgcna::out::archives` | `{"order":5}` |
| `tool_id:wgcna` | `io_slot:wgcna::out::figures` | `{"order":4}` |
| `tool_id:wgcna` | `io_slot:wgcna::out::hub_genes` | `{"order":2}` |
| `tool_id:wgcna` | `io_slot:wgcna::out::modules` | `{"order":1}` |
| `tool_id:wgcna` | `io_slot:wgcna::out::qc` | `{"order":3}` |

#### INPUT (21)

| Start | End | Properties |
|---|---|---|
| `tool_id:diff_expr_go` | `format:tsv` | `{}` |
| `tool_id:diff_expr_kegg` | `format:tsv` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `format:maf` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `format:xls` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `format:xlsx` | `{}` |
| `tool_id:her2_pfs_survival` | `format:tsv` | `{}` |
| `tool_id:her2_pfs_survival` | `format:xls` | `{}` |
| `tool_id:her2_pfs_survival` | `format:xlsx` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:tsv` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:xls` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:xlsx` | `{}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `format:fq.gz` | `{}` |
| `tool_id:rnaseq_unsupervised_cluster` | `format:tsv` | `{}` |
| `tool_id:survival_analysis` | `format:maf` | `{}` |
| `tool_id:survival_analysis` | `format:xlsx` | `{}` |
| `tool_id:tmb_survival_analysis` | `format:maf` | `{}` |
| `tool_id:tmb_survival_analysis` | `format:xlsx` | `{}` |
| `tool_id:wes_somatic_maf_landscape` | `format:maf` | `{}` |
| `tool_id:wgcna` | `format:tsv` | `{}` |
| `tool_id:wgcna` | `format:xls` | `{}` |
| `tool_id:wgcna` | `format:xlsx` | `{}` |

#### MANIFEST_AS (45)

| Start | End | Properties |
|---|---|---|
| `artifact_type:analysis_figure` | `format:pdf` | `{"primary":true}` |
| `artifact_type:analysis_figure` | `format:png` | `{"primary":true}` |
| `artifact_type:analysis_summary` | `format:json` | `{"primary":true}` |
| `artifact_type:analysis_summary` | `format:tsv` | `{"primary":false}` |
| `artifact_type:analysis_summary` | `format:txt` | `{"primary":false}` |
| `artifact_type:binary_mutation_matrix` | `format:gz` | `{"primary":true}` |
| `artifact_type:binary_mutation_matrix` | `format:tsv` | `{"primary":false}` |
| `artifact_type:clinical_survival_table` | `format:tsv` | `{"primary":false}` |
| `artifact_type:clinical_survival_table` | `format:xls` | `{"primary":true}` |
| `artifact_type:clinical_survival_table` | `format:xlsx` | `{"primary":true}` |
| `artifact_type:clinical_table` | `format:tsv` | `{"primary":false}` |
| `artifact_type:clinical_table` | `format:xls` | `{"primary":true}` |
| `artifact_type:clinical_table` | `format:xlsx` | `{"primary":true}` |
| `artifact_type:cluster_assignment_table` | `format:tsv` | `{"primary":true}` |
| `artifact_type:cluster_stability_table` | `format:tsv` | `{"primary":true}` |
| `artifact_type:differential_expression_table` | `format:tsv` | `{"primary":true}` |
| `artifact_type:enrichment_result_table` | `format:tsv` | `{"primary":true}` |
| `artifact_type:expression_abundance_matrix` | `format:tsv` | `{"primary":true}` |
| `artifact_type:expression_abundance_matrix` | `format:xls` | `{"primary":false}` |
| `artifact_type:expression_abundance_matrix` | `format:xlsx` | `{"primary":false}` |
| `artifact_type:expression_count_matrix` | `format:tsv` | `{"primary":true}` |
| `artifact_type:expression_tpm_matrix` | `format:tsv` | `{"primary":true}` |
| `artifact_type:file_list` | `format:list` | `{"primary":true}` |
| `artifact_type:hub_gene_table` | `format:tsv` | `{"primary":true}` |
| `artifact_type:immune_fraction_matrix` | `format:tsv` | `{"primary":true}` |
| `artifact_type:mutation_statistics_table` | `format:tsv` | `{"primary":true}` |
| `artifact_type:quality_control_report` | `format:json` | `{"primary":false}` |
| `artifact_type:quality_control_report` | `format:tsv` | `{"primary":true}` |
| `artifact_type:quality_control_report` | `format:txt` | `{"primary":false}` |
| `artifact_type:raw_fastq_read` | `format:fq.gz` | `{"primary":true}` |
| `artifact_type:sample_metadata` | `format:html` | `{}` |
| `artifact_type:sample_metadata` | `format:log` | `{}` |
| `artifact_type:sample_metadata` | `format:tsv` | `{}` |
| `artifact_type:sample_metadata` | `format:zip` | `{}` |
| `artifact_type:sample_metainfo` | `format:xls` | `{"primary":false}` |
| `artifact_type:sample_metainfo` | `format:xlsx` | `{"primary":true}` |
| `artifact_type:somatic_maf` | `format:maf` | `{"primary":true}` |
| `artifact_type:sorted_dedup_bam` | `format:fq.gz` | `{}` |
| `artifact_type:survival_statistics` | `format:json` | `{"primary":false}` |
| `artifact_type:survival_statistics` | `format:tsv` | `{"primary":true}` |
| `artifact_type:survival_statistics` | `format:txt` | `{"primary":false}` |
| `artifact_type:tmb_table` | `format:tsv` | `{"primary":true}` |
| `artifact_type:unmapped_bam` | `format:bam` | `{"primary":true}` |
| `artifact_type:unmapped_bam` | `format:sam` | `{}` |
| `artifact_type:wgcna_module_table` | `format:tsv` | `{"primary":true}` |

#### OUTPUT (37)

| Start | End | Properties |
|---|---|---|
| `tool_id:diff_expr_go` | `format:tsv` | `{}` |
| `tool_id:diff_expr_kegg` | `format:tsv` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `format:gz` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `format:pdf` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `format:png` | `{}` |
| `tool_id:driver_gene_gender_analysis` | `format:tsv` | `{}` |
| `tool_id:her2_pfs_survival` | `format:json` | `{}` |
| `tool_id:her2_pfs_survival` | `format:pdf` | `{}` |
| `tool_id:her2_pfs_survival` | `format:png` | `{}` |
| `tool_id:her2_pfs_survival` | `format:tsv` | `{}` |
| `tool_id:her2_pfs_survival` | `format:txt` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:json` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:pdf` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:png` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:tsv` | `{}` |
| `tool_id:immune_infiltration_iobr` | `format:txt` | `{}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `format:bam` | `{}` |
| `tool_id:paired_fastq_to_unmapped_bam` | `format:list` | `{}` |
| `tool_id:rnaseq_unsupervised_cluster` | `format:pdf` | `{}` |
| `tool_id:rnaseq_unsupervised_cluster` | `format:png` | `{}` |
| `tool_id:rnaseq_unsupervised_cluster` | `format:tsv` | `{}` |
| `tool_id:rnaseq_unsupervised_cluster` | `format:txt` | `{}` |
| `tool_id:survival_analysis` | `format:pdf` | `{}` |
| `tool_id:survival_analysis` | `format:png` | `{}` |
| `tool_id:survival_analysis` | `format:txt` | `{}` |
| `tool_id:tmb_survival_analysis` | `format:json` | `{}` |
| `tool_id:tmb_survival_analysis` | `format:pdf` | `{}` |
| `tool_id:tmb_survival_analysis` | `format:png` | `{}` |
| `tool_id:tmb_survival_analysis` | `format:tsv` | `{}` |
| `tool_id:wes_somatic_maf_landscape` | `format:maf` | `{}` |
| `tool_id:wes_somatic_maf_landscape` | `format:pdf` | `{}` |
| `tool_id:wes_somatic_maf_landscape` | `format:png` | `{}` |
| `tool_id:wes_somatic_maf_landscape` | `format:tsv` | `{}` |
| `tool_id:wgcna` | `format:gz` | `{}` |
| `tool_id:wgcna` | `format:pdf` | `{}` |
| `tool_id:wgcna` | `format:png` | `{}` |
| `tool_id:wgcna` | `format:tsv` | `{}` |

#### PRODUCES (31)

| Start | End | Properties |
|---|---|---|
| `io_slot:diff_expr_go::out::differential` | `artifact_type:differential_expression_table` | `{}` |
| `io_slot:diff_expr_go::out::enrichment` | `artifact_type:enrichment_result_table` | `{}` |
| `io_slot:diff_expr_kegg::out::differential` | `artifact_type:differential_expression_table` | `{}` |
| `io_slot:diff_expr_kegg::out::enrichment` | `artifact_type:enrichment_result_table` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::matrix` | `artifact_type:binary_mutation_matrix` | `{}` |
| `io_slot:driver_gene_gender_analysis::out::statistics` | `artifact_type:mutation_statistics_table` | `{}` |
| `io_slot:her2_pfs_survival::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:her2_pfs_survival::out::statistics` | `artifact_type:survival_statistics` | `{}` |
| `io_slot:her2_pfs_survival::out::summary` | `artifact_type:analysis_summary` | `{}` |
| `io_slot:immune_infiltration_iobr::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:immune_infiltration_iobr::out::fractions` | `artifact_type:immune_fraction_matrix` | `{}` |
| `io_slot:immune_infiltration_iobr::out::qc` | `artifact_type:quality_control_report` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::out::bam` | `artifact_type:unmapped_bam` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::out::list` | `artifact_type:file_list` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::out::assignments` | `artifact_type:cluster_assignment_table` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::out::stability` | `artifact_type:cluster_stability_table` | `{}` |
| `io_slot:survival_analysis::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:survival_analysis::out::statistics` | `artifact_type:survival_statistics` | `{}` |
| `io_slot:tmb_survival_analysis::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:tmb_survival_analysis::out::statistics` | `artifact_type:survival_statistics` | `{}` |
| `io_slot:tmb_survival_analysis::out::tmb` | `artifact_type:tmb_table` | `{}` |
| `io_slot:wes_somatic_maf_landscape::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:wes_somatic_maf_landscape::out::maf` | `artifact_type:somatic_maf` | `{}` |
| `io_slot:wes_somatic_maf_landscape::out::statistics` | `artifact_type:mutation_statistics_table` | `{}` |
| `io_slot:wgcna::out::archives` | `artifact_type:analysis_summary` | `{}` |
| `io_slot:wgcna::out::figures` | `artifact_type:analysis_figure` | `{}` |
| `io_slot:wgcna::out::hub_genes` | `artifact_type:hub_gene_table` | `{}` |
| `io_slot:wgcna::out::modules` | `artifact_type:wgcna_module_table` | `{}` |
| `io_slot:wgcna::out::qc` | `artifact_type:quality_control_report` | `{}` |

#### REQUIRES (24)

| Start | End | Properties |
|---|---|---|
| `io_slot:diff_expr_go::in::expression` | `artifact_type:expression_abundance_matrix` | `{}` |
| `io_slot:diff_expr_kegg::in::expression` | `artifact_type:expression_abundance_matrix` | `{}` |
| `io_slot:driver_gene_gender_analysis::in::clinical` | `artifact_type:clinical_table` | `{}` |
| `io_slot:driver_gene_gender_analysis::in::maf` | `artifact_type:somatic_maf` | `{}` |
| `io_slot:driver_gene_gender_analysis::in::metainfo` | `artifact_type:sample_metainfo` | `{}` |
| `io_slot:her2_pfs_survival::in::clinical` | `artifact_type:clinical_survival_table` | `{}` |
| `io_slot:her2_pfs_survival::in::expression` | `artifact_type:expression_tpm_matrix` | `{}` |
| `io_slot:her2_pfs_survival::in::metainfo` | `artifact_type:sample_metainfo` | `{}` |
| `io_slot:immune_infiltration_iobr::in::clinical` | `artifact_type:clinical_table` | `{}` |
| `io_slot:immune_infiltration_iobr::in::expression` | `artifact_type:expression_tpm_matrix` | `{}` |
| `io_slot:immune_infiltration_iobr::in::metainfo` | `artifact_type:sample_metainfo` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::in::fastq_1` | `artifact_type:raw_fastq_read` | `{}` |
| `io_slot:paired_fastq_to_unmapped_bam::in::fastq_2` | `artifact_type:raw_fastq_read` | `{}` |
| `io_slot:rnaseq_unsupervised_cluster::in::counts` | `artifact_type:expression_count_matrix` | `{}` |
| `io_slot:survival_analysis::in::clinical` | `artifact_type:clinical_survival_table` | `{}` |
| `io_slot:survival_analysis::in::maf` | `artifact_type:somatic_maf` | `{}` |
| `io_slot:survival_analysis::in::metainfo` | `artifact_type:sample_metainfo` | `{}` |
| `io_slot:tmb_survival_analysis::in::clinical` | `artifact_type:clinical_survival_table` | `{}` |
| `io_slot:tmb_survival_analysis::in::maf` | `artifact_type:somatic_maf` | `{}` |
| `io_slot:tmb_survival_analysis::in::metainfo` | `artifact_type:sample_metainfo` | `{}` |
| `io_slot:wes_somatic_maf_landscape::in::maf` | `artifact_type:somatic_maf` | `{}` |
| `io_slot:wgcna::in::clinical` | `artifact_type:clinical_table` | `{}` |
| `io_slot:wgcna::in::counts` | `artifact_type:expression_count_matrix` | `{}` |
| `io_slot:wgcna::in::metainfo` | `artifact_type:sample_metainfo` | `{}` |

### Complete 6 Incorrect CSV Mappings

| Type | CSV bootstrap start | CSV bootstrap end | CSV properties | Production state |
|---|---|---|---|---|
| `ALLOW_FORMAT` | `io_slot:star::output::aligned_bam` | `format:fq.gz` | `{}` | relationship absent |
| `MANIFEST_AS` | `artifact_type:aligned_bam` | `format:fq.gz` | `{}` | relationship absent |
| `MANIFEST_AS` | `artifact_type:expression_abundance_matrix` | `format:tsv` | `{}` | {"primary":true} |
| `MANIFEST_AS` | `artifact_type:expression_count_matrix` | `format:tsv` | `{}` | {"primary":true} |
| `MANIFEST_AS` | `artifact_type:quality_control_report` | `format:tsv` | `{}` | {"primary":true} |
| `MANIFEST_AS` | `artifact_type:raw_fastq_read` | `format:fq.gz` | `{}` | {"primary":true} |

### Node Coverage and Property Drift

The legacy bootstrap also omitted **96** nodes and produced **29** shared nodes with different labels or properties. It produced no extra node identities.

Missing node identities:

- `artifact_type:analysis_figure`
- `artifact_type:analysis_summary`
- `artifact_type:binary_mutation_matrix`
- `artifact_type:clinical_survival_table`
- `artifact_type:clinical_table`
- `artifact_type:cluster_assignment_table`
- `artifact_type:cluster_stability_table`
- `artifact_type:differential_expression_table`
- `artifact_type:enrichment_result_table`
- `artifact_type:expression_tpm_matrix`
- `artifact_type:file_list`
- `artifact_type:hub_gene_table`
- `artifact_type:immune_fraction_matrix`
- `artifact_type:mutation_statistics_table`
- `artifact_type:sample_metadata`
- `artifact_type:sample_metainfo`
- `artifact_type:somatic_maf`
- `artifact_type:survival_statistics`
- `artifact_type:tmb_table`
- `artifact_type:unmapped_bam`
- `artifact_type:wgcna_module_table`
- `format:csv`
- `format:dir`
- `format:gz`
- `format:list`
- `format:maf`
- `format:pdf`
- `format:png`
- `format:xls`
- `format:xlsx`
- `function:HER2 表达与无进展生存期分析`
- `function:RNA-seq 无监督聚类分析流程`
- `function:WES 体细胞突变 MAF 景观分析流程`
- `function:WGCNA 加权基因共表达网络分析`
- `function:免疫浸润分析 (IOBR CIBERSORT)`
- `function:双端 FASTQ 转未比对 BAM`
- `function:差异表达与 GO 富集分析`
- `function:差异表达与 Reactome 通路富集分析流程`
- `function:生存分析流程`
- `function:肿瘤突变负荷生存分析流程`
- `function:驱动基因突变频率性别分层分析`
- `io_slot:diff_expr_go::in::expression`
- `io_slot:diff_expr_go::out::differential`
- `io_slot:diff_expr_go::out::enrichment`
- `io_slot:diff_expr_kegg::in::expression`
- `io_slot:diff_expr_kegg::out::differential`
- `io_slot:diff_expr_kegg::out::enrichment`
- `io_slot:driver_gene_gender_analysis::in::clinical`
- `io_slot:driver_gene_gender_analysis::in::maf`
- `io_slot:driver_gene_gender_analysis::in::metainfo`
- `io_slot:driver_gene_gender_analysis::out::figures`
- `io_slot:driver_gene_gender_analysis::out::matrix`
- `io_slot:driver_gene_gender_analysis::out::statistics`
- `io_slot:her2_pfs_survival::in::clinical`
- `io_slot:her2_pfs_survival::in::expression`
- `io_slot:her2_pfs_survival::in::metainfo`
- `io_slot:her2_pfs_survival::out::figures`
- `io_slot:her2_pfs_survival::out::statistics`
- `io_slot:her2_pfs_survival::out::summary`
- `io_slot:immune_infiltration_iobr::in::clinical`
- `io_slot:immune_infiltration_iobr::in::expression`
- `io_slot:immune_infiltration_iobr::in::metainfo`
- `io_slot:immune_infiltration_iobr::out::figures`
- `io_slot:immune_infiltration_iobr::out::fractions`
- `io_slot:immune_infiltration_iobr::out::qc`
- `io_slot:paired_fastq_to_unmapped_bam::in::fastq_1`
- `io_slot:paired_fastq_to_unmapped_bam::in::fastq_2`
- `io_slot:paired_fastq_to_unmapped_bam::out::bam`
- `io_slot:paired_fastq_to_unmapped_bam::out::list`
- `io_slot:rnaseq_unsupervised_cluster::in::counts`
- `io_slot:rnaseq_unsupervised_cluster::out::assignments`
- `io_slot:rnaseq_unsupervised_cluster::out::figures`
- `io_slot:rnaseq_unsupervised_cluster::out::stability`
- `io_slot:survival_analysis::in::clinical`
- `io_slot:survival_analysis::in::maf`
- `io_slot:survival_analysis::in::metainfo`
- `io_slot:survival_analysis::out::figures`
- `io_slot:survival_analysis::out::statistics`
- `io_slot:tmb_survival_analysis::in::clinical`
- `io_slot:tmb_survival_analysis::in::maf`
- `io_slot:tmb_survival_analysis::in::metainfo`
- `io_slot:tmb_survival_analysis::out::figures`
- `io_slot:tmb_survival_analysis::out::statistics`
- `io_slot:tmb_survival_analysis::out::tmb`
- `io_slot:wes_somatic_maf_landscape::in::maf`
- `io_slot:wes_somatic_maf_landscape::out::figures`
- `io_slot:wes_somatic_maf_landscape::out::maf`
- `io_slot:wes_somatic_maf_landscape::out::statistics`
- `io_slot:wgcna::in::clinical`
- `io_slot:wgcna::in::counts`
- `io_slot:wgcna::in::metainfo`
- `io_slot:wgcna::out::archives`
- `io_slot:wgcna::out::figures`
- `io_slot:wgcna::out::hub_genes`
- `io_slot:wgcna::out::modules`
- `io_slot:wgcna::out::qc`

Changed shared nodes are preserved in the machine-readable evidence file `docs/fix_c_catalog_diff.json`.

## Implementation and Gates

### Where the Missing Content Came From

The production graph does not contain creation or update timestamps for catalog nodes or relationships, so a last-import time cannot be recovered. Provenance is only partial:

- 23 tool nodes carry `catalog_source=sister-tool-csv`; the task pipeline carries `sister-task-pipeline`.
- 28 slots carry `sister-tool-csv`, 10 carry `sister-task-pipeline`, 3 carry `bam-artifact-contract-fix-2026-07-22`, and 3 carry `qc-report-contract-fix-2026-07-22`.
- The remaining 55 slots, all 33 artifacts, all 35 functions, all 27 formats, and all legacy `INPUT`/`OUTPUT` relationships have no source marker or timestamp. They pre-existed the reviewed sync path; whether each was created manually or by an older import is **待确认**.
- Repository history confirms two later repair scripts for the six source-marked BAM/QC slots. `cypher/import/04_import_workflow_relations.cypher` explains the legacy `INPUT`/`OUTPUT` model, but it cannot reproduce the current slot graph.

### Schema Finding

The old three tool relation tables were insufficient. They could not express pipeline-level slots, exact labels and node properties, per-slot formats, `primary/order` relationship properties, legacy `INPUT`/`OUTPUT`, or all artifact/function/format nodes. This was the root cause, not merely missing rows.

`data/csv/catalog/` now contains five typed node tables and one complete relationship table:

- `tool_id.csv`: all tool properties and labels
- `io_slot.csv`: explicit slot identity, name, direction, required state, source, and one-of metadata
- `artifact_type.csv`, `function.csv`, `format.csv`: complete referenced nodes and properties
- `relationships.csv`: all non-NEXT relationships with exact endpoint identities and JSON properties

NEXT remains in the reviewed `relations/tool_relationship.csv`; bootstrap applies that table after rebuilding the canonical non-NEXT graph. `validate_csv.py` now checks typed headers, unique identities, slot tool/direction/required constraints, relationship types, endpoint foreign keys, and property JSON.

### Bootstrap Behavior

Ordinary `--apply` still manages only reviewed NEXT edges. Explicit `--apply --bootstrap-catalog` atomically replaces only nodes bearing catalog labels, recreates the canonical CSV graph, then applies NEXT. The data graph labels are disjoint and were preserved. Re-running bootstrap removes stale catalog rows instead of silently accumulating them.

### Gate Results

| Gate | Result |
|---|---|
| Legacy pre-B CSV on independent empty home | 218 nodes / 548 relationships; exact fingerprint `439dff931e236038985e50ce7f821e69736917f38440dfa408735ac89f57de1f` |
| Required pre-B counts | tools 24; atomic/pipeline 12/12; input/output slots 49/50; NEXT 14; HAS_STEP 7 |
| Authorized post-B CSV | 218 nodes / 556 relationships; NEXT 22; fingerprint `27f0baa7b3845f033fac9b8c66188ca14bf3d331639a1c25ebba91ca257b1a0b` |
| Idempotency | Two consecutive post-B bootstraps produced the same counts and `27f0baa7...b1a0b` fingerprint |
| CSV validation | Passed with canonical schema checks enabled |
| Staging bootstrap | Passed on `7688/datagraph-staging`; production remained read-only |
| Full regression | 76 tests OK, including all original 68; 3 existing real integrations skipped |

The specification's old fingerprint and NEXT=22 cannot describe the same graph: adding eight relationships necessarily changes both relationship count and fingerprint. The conservative resolution was to prove the mandated old fingerprint against the B-pre-change CSV first, then establish and verify the new B-authorized fingerprint without relabeling either value.
