# Feasibility Truth Table

> 注：这是 **assay 校验实施前** 的基线真值表，用于暴露系统判定与人工真值之间的偏差。

14 studies × 14 pipelines = 196 cells.

## Summary

- 一致: 176 (89.8%)
- 假阳性: 20 (10.2%)
- 假阴性: 0 (0.0%)

## Per-pipeline false-positive rate

| pipeline | 一致 | 假阳性 | 假阴性 | 假阳性率 |
| --- | --- | --- | --- | --- |
| cellranger_workflow | 5 | 9 | 0 | 64.3% |
| rnaseq_singletask | 7 | 7 | 0 | 50.0% |
| wes_somatic_pair | 14 | 0 | 0 | 0.0% |
| paired_fastq_to_unmapped_bam | 10 | 4 | 0 | 28.6% |
| diff_expr_go | 14 | 0 | 0 | 0.0% |
| diff_expr_kegg | 14 | 0 | 0 | 0.0% |
| rnaseq_unsupervised_cluster | 14 | 0 | 0 | 0.0% |
| wgcna | 14 | 0 | 0 | 0.0% |
| immune_infiltration_iobr | 14 | 0 | 0 | 0.0% |
| her2_pfs_survival | 14 | 0 | 0 | 0.0% |
| survival_analysis | 14 | 0 | 0 | 0.0% |
| tmb_survival_analysis | 14 | 0 | 0 | 0.0% |
| wes_somatic_maf_landscape | 14 | 0 | 0 | 0.0% |
| driver_gene_gender_analysis | 14 | 0 | 0 | 0.0% |

## Full table

| study | pipeline | 系统判定 | A 角色 | B assay | C 拓扑 | 真值 | 类型 | T1 strategies | visible roles |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HRA000071 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | rnaseq_singletask | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | wes_somatic_pair | ✗ | ✓ | 是 | ✗ | ✗ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | survival_analysis | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | tmb_survival_analysis | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000071 | driver_gene_gender_analysis | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1144} | {'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1} |
| HRA000074 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | rnaseq_singletask | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | wes_somatic_pair | ✗ | ✓ | 否 | ✗ | ✗ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | diff_expr_go | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | diff_expr_kegg | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | rnaseq_unsupervised_cluster | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA000074 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 1386} | {'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1} |
| HRA007167 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | rnaseq_singletask | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | wes_somatic_pair | ✗ | ✓ | 否 | ✗ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | diff_expr_go | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | diff_expr_kegg | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | rnaseq_unsupervised_cluster | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | wes_somatic_maf_landscape | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007167 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'RNA-Seq': 162} | {'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA007169 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | rnaseq_singletask | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | wes_somatic_pair | ✗ | ✓ | 是 | ✗ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA007169 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 336} | {'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2} |
| HRA001272 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | rnaseq_singletask | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | wes_somatic_pair | ✗ | ✓ | 是 | ✗ | ✗ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | diff_expr_go | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | diff_expr_kegg | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | rnaseq_unsupervised_cluster | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA001272 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1500, 'RNA-Seq': 860} | {'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1} |
| HRA000122 | cellranger_workflow | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {} |
| HRA000122 | rnaseq_singletask | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {} |
| HRA000122 | wes_somatic_pair | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {} |
| HRA000122 | paired_fastq_to_unmapped_bam | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {} |
| HRA000122 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | wes_somatic_maf_landscape | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA000122 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {} |
| HRA005191 | cellranger_workflow | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | rnaseq_singletask | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | wes_somatic_pair | ✗ | ✓ | 否 | ✗ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | wes_somatic_maf_landscape | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA005191 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 970} | {'fastq': 970, 'other': 1, 'metainfo': 1} |
| HRA001748 | cellranger_workflow | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | rnaseq_singletask | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | wes_somatic_pair | ✗ | ✓ | 否 | ✗ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | wes_somatic_maf_landscape | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001748 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'scRNA-Seq': 320} | {'fastq': 320, 'other': 1, 'metainfo': 1} |
| HRA001749 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | rnaseq_singletask | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | wes_somatic_pair | ✗ | ✓ | 是 | ✗ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA001749 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 356} | {'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | rnaseq_singletask | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | wes_somatic_pair | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA006499 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 1526} | {'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1} |
| HRA003107 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | rnaseq_singletask | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | wes_somatic_pair | ✗ | ✓ | 否 | ✗ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | diff_expr_go | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | diff_expr_kegg | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | rnaseq_unsupervised_cluster | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | wes_somatic_maf_landscape | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA003107 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WGS': 532, 'RNA-Seq': 620} | {'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1} |
| HRA000021 | cellranger_workflow | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | rnaseq_singletask | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | wes_somatic_pair | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | paired_fastq_to_unmapped_bam | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000021 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'bam': 1, 'vcf': 2, 'maf': 1} |
| HRA000873 | cellranger_workflow | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | rnaseq_singletask | ✓ | ✓ | 否 | ✓ | ✗ | 假阳性 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | wes_somatic_pair | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | paired_fastq_to_unmapped_bam | ✓ | ✓ | 是 | ✓ | ✓ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000873 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {'WES': 4060} | {'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1} |
| HRA000321 | cellranger_workflow | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | rnaseq_singletask | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | wes_somatic_pair | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | paired_fastq_to_unmapped_bam | ✗ | ✗ | 否 | ✗ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | diff_expr_go | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | diff_expr_kegg | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | rnaseq_unsupervised_cluster | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | wgcna | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | immune_infiltration_iobr | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | her2_pfs_survival | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | tmb_survival_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | wes_somatic_maf_landscape | ✓ | ✓ | N/A | ✓ | ✓ | 一致 | {} | {'maf': 1, 'metainfo': 1} |
| HRA000321 | driver_gene_gender_analysis | ✗ | ✗ | N/A | ✓ | ✗ | 一致 | {} | {'maf': 1, 'metainfo': 1} |

## False positives detail

### assay 不匹配

- HRA000071 / cellranger_workflow: strategies={'WES': 1144} roles={'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1}
- HRA000071 / rnaseq_singletask: strategies={'WES': 1144} roles={'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1}
- HRA000074 / cellranger_workflow: strategies={'RNA-Seq': 1386} roles={'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1}
- HRA000074 / paired_fastq_to_unmapped_bam: strategies={'RNA-Seq': 1386} roles={'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1}
- HRA007167 / cellranger_workflow: strategies={'RNA-Seq': 162} roles={'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1}
- HRA007167 / paired_fastq_to_unmapped_bam: strategies={'RNA-Seq': 162} roles={'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1}
- HRA007169 / cellranger_workflow: strategies={'WES': 336} roles={'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2}
- HRA007169 / rnaseq_singletask: strategies={'WES': 336} roles={'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2}
- HRA001272 / cellranger_workflow: strategies={'WES': 1500, 'RNA-Seq': 860} roles={'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1}
- HRA005191 / rnaseq_singletask: strategies={'scRNA-Seq': 970} roles={'fastq': 970, 'other': 1, 'metainfo': 1}
- HRA005191 / paired_fastq_to_unmapped_bam: strategies={'scRNA-Seq': 970} roles={'fastq': 970, 'other': 1, 'metainfo': 1}
- HRA001748 / rnaseq_singletask: strategies={'scRNA-Seq': 320} roles={'fastq': 320, 'other': 1, 'metainfo': 1}
- HRA001748 / paired_fastq_to_unmapped_bam: strategies={'scRNA-Seq': 320} roles={'fastq': 320, 'other': 1, 'metainfo': 1}
- HRA001749 / cellranger_workflow: strategies={'WES': 356} roles={'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1}
- HRA001749 / rnaseq_singletask: strategies={'WES': 356} roles={'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1}
- HRA006499 / cellranger_workflow: strategies={'WES': 1526} roles={'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1}
- HRA006499 / rnaseq_singletask: strategies={'WES': 1526} roles={'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1}
- HRA003107 / cellranger_workflow: strategies={'WGS': 532, 'RNA-Seq': 620} roles={'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1}
- HRA000873 / cellranger_workflow: strategies={'WES': 4060} roles={'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1}
- HRA000873 / rnaseq_singletask: strategies={'WES': 4060} roles={'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1}

### format 标注错误

_None_

### 拓扑不满足

_None_

### 角色缺失

_None_

### other

- HRA000071 / cellranger_workflow: strategies={'WES': 1144} roles={'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1}
- HRA000071 / rnaseq_singletask: strategies={'WES': 1144} roles={'fastq': 1144, 'bam': 1, 'other': 1, 'maf': 2, 'vcf': 2, 'clinical': 1, 'metainfo': 1}
- HRA000074 / cellranger_workflow: strategies={'RNA-Seq': 1386} roles={'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1}
- HRA000074 / paired_fastq_to_unmapped_bam: strategies={'RNA-Seq': 1386} roles={'fastq': 1386, 'maf': 2, 'expression_count': 1, 'expression_abundance': 2, 'other': 1, 'metainfo': 1}
- HRA007167 / cellranger_workflow: strategies={'RNA-Seq': 162} roles={'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1}
- HRA007167 / paired_fastq_to_unmapped_bam: strategies={'RNA-Seq': 162} roles={'fastq': 162, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1}
- HRA007169 / cellranger_workflow: strategies={'WES': 336} roles={'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2}
- HRA007169 / rnaseq_singletask: strategies={'WES': 336} roles={'fastq': 336, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2}
- HRA001272 / cellranger_workflow: strategies={'WES': 1500, 'RNA-Seq': 860} roles={'fastq': 2360, 'bam': 2, 'maf': 4, 'expression_count': 1, 'expression_abundance': 2, 'other': 3, 'vcf': 2, 'clinical': 1}
- HRA005191 / rnaseq_singletask: strategies={'scRNA-Seq': 970} roles={'fastq': 970, 'other': 1, 'metainfo': 1}
- HRA005191 / paired_fastq_to_unmapped_bam: strategies={'scRNA-Seq': 970} roles={'fastq': 970, 'other': 1, 'metainfo': 1}
- HRA001748 / rnaseq_singletask: strategies={'scRNA-Seq': 320} roles={'fastq': 320, 'other': 1, 'metainfo': 1}
- HRA001748 / paired_fastq_to_unmapped_bam: strategies={'scRNA-Seq': 320} roles={'fastq': 320, 'other': 1, 'metainfo': 1}
- HRA001749 / cellranger_workflow: strategies={'WES': 356} roles={'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1}
- HRA001749 / rnaseq_singletask: strategies={'WES': 356} roles={'fastq': 356, 'bam': 1, 'other': 2, 'maf': 3, 'vcf': 2, 'metainfo': 1}
- HRA006499 / cellranger_workflow: strategies={'WES': 1526} roles={'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1}
- HRA006499 / rnaseq_singletask: strategies={'WES': 1526} roles={'fastq': 1526, 'bam': 2, 'maf': 2, 'other': 1, 'vcf': 2, 'metainfo': 1}
- HRA003107 / cellranger_workflow: strategies={'WGS': 532, 'RNA-Seq': 620} roles={'fastq': 1152, 'bam': 1, 'other': 2, 'expression_count': 1, 'expression_abundance': 2, 'metainfo': 1}
- HRA000873 / cellranger_workflow: strategies={'WES': 4060} roles={'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1}
- HRA000873 / rnaseq_singletask: strategies={'WES': 4060} roles={'fastq': 4060, 'bam': 1, 'maf': 4, 'other': 1, 'vcf': 1}


## False negatives detail

_None_
