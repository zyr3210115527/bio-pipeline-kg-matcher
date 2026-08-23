# 待确认：64 个输入槽的 builder_param / wdl_target

`io_slot.csv` 共 128 个输入槽，原本只有 33 个带 `builder_param`（12 个工具），其余 95 个
为空。为空的槽会被 `workflow_composer.py:1353` 直接跳过，`execution_params` 于是跟着空
——师兄看到的"三个输入 builder_param、wdl_target 全空"是这条链的末端，不是图谱缺数据。
图谱按设计就不携带 slot / wdl_target / builder_param（见 `tool_catalog_source.py` 模块
注释），这些是执行侧契约，只存在于 `data/csv/catalog/`。所以要改的是 MCP 这边的目录表，
图谱不用动。

本次自动补了 31 个（现共 64 个有值），规则是**角色唯一对应 + 双射校验**：每个必需输入槽
唯一对上一个必需文件参数，且没有必需参数落空，两边都对齐才落。角色对应不是我定的，是从
已填好的 12 个工具里反推出的既成约定（`sample_metainfo`→`metainfo_xlsx`/`meta_xlsx`，
`clinical_table`→`clinical_xls`，`count_matrix`→`counts_tsv`）。

下面 64 个槽、26 个工具没通过校验，**没有填，也没有猜**——这里猜错的后果是给出一张填满
的、看着合理的错参数表，要到执行端才炸。

每条只需要回答：**这个槽对应卡片里的哪个参数**（或者说明这个槽本来就不该存在）。

## B. 卡片是数组参数，一个参数对应几个槽要人定

### `cnvkit_cnv_clinical`

- 判定：卡片有数组型文件参数，一个参数对几个槽要人定
- 槽表里的输入槽：`aligned_bam`, `tabular_bio_data`, `clinical_table`
- 卡片数组参数：`tumor_bams:array[string]`, `tumor_bais:array[string]`, `normal_bams:array[string]`, `normal_bais:array[string]`
- 卡片单文件参数：`targets_bed`, `clinical_metadata`

### `fastqc`

- 判定：卡片有数组型文件参数，一个参数对几个槽要人定
- 槽表里的输入槽：`clean_fastq_read`, `raw_fastq_read`
- 卡片数组参数：`fastqs:array[file]+`

### `multiqc`

- 判定：卡片有数组型文件参数，一个参数对几个槽要人定
- 槽表里的输入槽：`quality_control_report`
- 卡片数组参数：`qc_files:array[file]`

### `rmats_alternative_splicing`

- 判定：卡片有数组型文件参数，一个参数对几个槽要人定
- 槽表里的输入槽：`transcriptome_bam`, `genome_annotation`
- 卡片数组参数：`group1_bams:array[string]`, `group2_bams:array[string]`, `group1_bais:array[string]`, `group2_bais:array[string]`

## C. 卡片有必需参数，槽表里没有对应的槽

### `fastp`

- 判定：卡片必需参数 ['read1', 'read2'] 在槽表里没有对应的槽（槽表缺槽）
- 槽表里的输入槽：
    - `raw_fastq_read` （required=false, artifact=raw_fastq_read, 角色=fastq）
    - `raw_fastq_read_r1` （required=false, artifact=raw_fastq_read, 角色=fastq）
    - `raw_fastq_read_r2` （required=false, artifact=raw_fastq_read, 角色=fastq）
    - 卡片必需参数 `read1` → `FastpPairedEndWorkflow.read1` · R1 FASTQ
    - 卡片必需参数 `read2` → `FastpPairedEndWorkflow.read2` · R2 FASTQ

### `gsea_pathway_enrichment`

- 判定：卡片必需参数 ['sample_metadata'] 在槽表里没有对应的槽（槽表缺槽）
- 槽表里的输入槽：
    - `tabular_bio_data` （required=true, artifact=analysis_summary, 角色=expr）
    - 卡片必需参数 `expression_matrix` → `GseaPathwayEnrichment.expression_matrix` · 基因表达矩阵文件，TSV格式，第一列为基因ID，其余列为样本ID
    - 卡片必需参数 `sample_metadata` → `GseaPathwayEnrichment.sample_metadata` · 样本元数据文件，支持TSV、XLS或XLSX格式，至少包含sample和group列
- 卡片可选文件参数：`gene_sets_gmt`

## D. 一个槽实际代表多个文件（双端 R1/R2）

### `trim_galore`

- 判定：同角色还剩可选文件参数 ['read2'] 无槽可放，一个槽实际代表多个文件（如双端 R1/R2）
- 槽表里的输入槽：
    - `raw_fastq_read` （required=true, artifact=—, 角色=fastq）
    - 卡片必需参数 `read1` → `TrimGaloreWorkflow.read1` · R1 FASTQ
- 卡片可选文件参数：`read2`

## E. 槽在卡片里找不到对应的必需参数

### `bcftools`

- 判定：槽 unfiltered_vcf(角色=vcf) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `unfiltered_vcf` （required=true, artifact=—, 角色=vcf）
    - 卡片必需参数 `filtered_vcf` → `BcftoolsSomaticPostprocessWorkflow.filtered_vcf` · 过滤后 VCF
    - 卡片必需参数 `filtered_vcf_index` → `BcftoolsSomaticPostprocessWorkflow.filtered_vcf_index` · VCF 索引

### `breast_cellchat`

- 判定：槽 genome_annotation(角色=ref) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `breast_cellchat.input_rds` · Seurat对象的RDS文件路径

### `bwa`

- 判定：槽 genome_annotation(角色=ref) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `clean_fastq_read` （required=false, artifact=clean_fastq_read, 角色=fastq）
    - `genome_annotation` （required=true, artifact=—, 角色=ref）
    - `clean_fastq_read_r1` （required=false, artifact=clean_fastq_read, 角色=fastq）
    - `clean_fastq_read_r2` （required=false, artifact=clean_fastq_read, 角色=fastq）
    - 卡片必需参数 `read1` → `BwaMemWorkflow.read1` · R1 FASTQ
    - 卡片必需参数 `read2` → `BwaMemWorkflow.read2` · R2 FASTQ

### `celltype_case_control_de`

- 判定：槽 tabular_bio_data(角色=expr) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `tabular_bio_data` （required=true, artifact=analysis_summary, 角色=expr）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `celltype_case_control_de.input_rds` · Seurat RDS格式的单细胞对象文件

### `dataset_downstream`

- 判定：槽 tabular_bio_data(角色=expr) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `tabular_bio_data` （required=true, artifact=analysis_summary, 角色=expr）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `dataset_downstream.input_rds` · Seurat RDS格式的输入文件
    - 卡片必需参数 `gene_order` → `dataset_downstream.gene_order` · 基因排序文件

### `dataset_matrix_annotation`

- 判定：槽 tabular_bio_data(角色=expr) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `tabular_bio_data` （required=true, artifact=analysis_summary, 角色=expr）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `dataset_matrix_annotation.input_rds` · 输入Seurat RDS文件路径

### `featurecounts`

- 判定：槽 genome_annotation(角色=ref) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `genome_annotation` （required=true, artifact=—, 角色=ref）
    - `sorted_dedup_bam` （required=true, artifact=—, 角色=bam）
    - 卡片必需参数 `bam` → `FeatureCountsWorkflow.bam` · 排序后的 BAM
    - 卡片必需参数 `gtf_file` → `FeatureCountsWorkflow.gtf_file` · GTF 注释

### `gatk`

- 判定：槽 genome_annotation(角色=ref) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `genome_annotation` （required=true, artifact=—, 角色=ref）
    - `sorted_dedup_bam` （required=false, artifact=sorted_dedup_bam, 角色=bam）
    - `tumor_bam` （required=false, artifact=sorted_dedup_bam, 角色=None）
    - `tumor_bai` （required=false, artifact=bai, 角色=None）
    - `normal_bam` （required=false, artifact=sorted_dedup_bam, 角色=None）
    - `normal_bai` （required=false, artifact=bai, 角色=None）
    - `interval_list` （required=true, artifact=interval_list, 角色=interval）
    - 卡片必需参数 `tumor_bam` → `GatkWesSomaticWorkflow.tumor_bam` · 肿瘤 BAM
    - 卡片必需参数 `tumor_bai` → `GatkWesSomaticWorkflow.tumor_bai` · 肿瘤 BAM 索引
    - 卡片必需参数 `normal_bam` → `GatkWesSomaticWorkflow.normal_bam` · 正常 BAM
    - 卡片必需参数 `normal_bai` → `GatkWesSomaticWorkflow.normal_bai` · 正常 BAM 索引
    - 卡片必需参数 `interval_list` → `GatkWesSomaticWorkflow.interval_list` · GATK 区间列表

### `immunotherapy_cellchat`

- 判定：槽 genome_annotation(角色=ref) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `immunotherapy_cellchat.input_rds` · Seurat对象的RDS文件路径

### `ipf_trajectory_regulon`

- 判定：槽 sample_metainfo(角色=meta) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `sample_metainfo` （required=true, artifact=sample_metainfo, 角色=meta）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `ipf_trajectory_regulon.input_rds` · Seurat RDS格式的单细胞数据对象文件

### `lung_tme_annotation_cnv`

- 判定：槽 tabular_bio_data(角色=expr) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `tabular_bio_data` （required=true, artifact=analysis_summary, 角色=expr）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `lung_tme_annotation_cnv.input_rds` · 输入Seurat RDS文件，包含单细胞RNA-seq数据
    - 卡片必需参数 `gene_order` → `lung_tme_annotation_cnv.gene_order` · 基因排序文件，用于CNV分析

### `paired_fastq_to_unmapped_bam`

- 判定：槽 fastq_1(角色=fastq) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `fastq_1` （required=true, artifact=—, 角色=fastq）
    - `fastq_2` （required=true, artifact=—, 角色=fastq）

### `rsem`

- 判定：槽 transcriptome_bam(角色=bam) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `genome_annotation` （required=true, artifact=—, 角色=ref）
    - `transcriptome_bam` （required=true, artifact=—, 角色=bam）
    - 卡片必需参数 `transcriptome_bam` → `RsemQuantificationWorkflow.transcriptome_bam` · STAR transcriptome BAM
    - 卡片必需参数 `rsem_index` → `RsemQuantificationWorkflow.rsem_index` · RSEM 索引

### `samtools`

- 判定：槽 aligned_bam(角色=bam) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `aligned_bam` （required=true, artifact=—, 角色=bam）
    - 卡片必需参数 `alignment` → `SamtoolsAlignmentWorkflow.alignment` · 待处理比对文件

### `scrna_cell_communication`

- 判定：槽 tabular_bio_data(角色=expr) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `tabular_bio_data` （required=true, artifact=analysis_summary, 角色=expr）
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `sample_metainfo` （required=true, artifact=sample_metainfo, 角色=meta）
- 卡片可选文件参数：`combined_counts`, `seurat_rds`, `cell_metadata`, `receiver_de_genes`, `background_expressed_genes`, `microenvironments`, `active_tfs`

### `snpeff`

- 判定：槽 filtered_vcf(角色=vcf) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `filtered_vcf` （required=true, artifact=—, 角色=vcf）
    - `genome_annotation` （required=true, artifact=—, 角色=ref）
    - 卡片必需参数 `input_vcf` → `SnpEffAnnotationWorkflow.input_vcf` · 输入 VCF

### `tcell_intervention`

- 判定：槽 tabular_bio_data(角色=expr) 对上 0 个必需参数[]
- 槽表里的输入槽：
    - `scrna_object_rds` （required=true, artifact=scrna_object, 角色=rds）
    - `tabular_bio_data` （required=true, artifact=analysis_summary, 角色=expr）
    - `sample_metainfo` （required=true, artifact=sample_metainfo, 角色=meta）
    - `genome_annotation` （required=true, artifact=genome_annotation, 角色=ref）
    - 卡片必需参数 `input_rds` → `tcell_intervention.input_rds` · 输入的Seurat RDS文件路径

## F. 一个槽对上多个候选参数

### `cellranger_workflow`

- 判定：槽 raw_fastq_read(角色=fastq) 对上 2 个必需参数['fastq_file1', 'fastq_file2']
- 槽表里的输入槽：
    - `raw_fastq_read` （required=true, artifact=raw_fastq_read, 角色=fastq）
    - `aligned_bam` （required=true, artifact=aligned_bam, 角色=None）
    - 卡片必需参数 `fastq_file1` → `CellRangerFullPipeline.fastq_file1` · 测序 reads 1 文件路径 (FASTQ 格式)
    - 卡片必需参数 `fastq_file2` → `CellRangerFullPipeline.fastq_file2` · 测序 reads 2 文件路径 (FASTQ 格式)
- 卡片可选文件参数：`transcriptome`

### `star`

- 判定：槽 genome_annotation(角色=ref) 对上 2 个必需参数['rrna_star_index', 'genome_star_index']
- 槽表里的输入槽：
    - `clean_fastq_read` （required=true, artifact=—, 角色=fastq）
    - `genome_annotation` （required=true, artifact=—, 角色=ref）
    - 卡片必需参数 `read1` → `StarRnaSeqWorkflow.read1` · R1 FASTQ
    - 卡片必需参数 `rrna_star_index` → `StarRnaSeqWorkflow.rrna_star_index` · rRNA STAR 索引
    - 卡片必需参数 `genome_star_index` → `StarRnaSeqWorkflow.genome_star_index` · 基因组 STAR 索引
- 卡片可选文件参数：`read2`
