# 目标态工具目录规格

> 状态：设计稿，不是迁移指令。依据是 `docs/wdl_inventory.json` 与对应 WDL command。本文不授权修改 CSV、Neo4j、绑定逻辑或 `tool-chain/v1`。

## 1. 范围与不变项

1. 保持 `tool-chain/v1` 的 `inputs.<slot> = {from...}` / `{asset_role...}` 结构；不引入 `items[]`。
2. 多实例用具名槽：`raw_fastq_read_r1/r2`、`tumor_sorted_dedup_bam`、`normal_sorted_dedup_bam`。
3. 条件必需用输入变体集合；一次 step 必须选且只选一个 variant。
4. `slot_name` 是接口身份，`artifact` 是类型兼容性；两者不再等同。
5. WDL 没有独立 task 边界的软件不虚构槽，标记为 `待补`。
6. 报告按生产工具聚合为 `Array[File]` 报告束，再绑定 MultiQC 的对应具名输入。这不改契约结构，但要求执行端物化该数组输出。

## 2. CSV schema

### 2.1 输入槽

`tool_input_format.csv` 建议从 2 列扩展为：

| 列 | 类型/约束 | 含义 |
|---|---|---|
| tool_id | string, FK | 保留 catalog id（T01 等） |
| slot_name | string, required | 工具内唯一的契约键，不从 artifact 推导 |
| artifact | string, FK/枚举 | 数据类型，用于上下游兼容校验 |
| semantic_label | string | 人读语义，取代仅有的 `语义输入格式` |
| required | boolean | **在所属 variant 内**是否必需 |
| variant | string | `single_end`、`paired_end`、`single`、`paired` 等；共享槽可写多个 variant |
| wdl_type | enum | `File`、`File?`、`Array[File]`等，不用 format 反推 cardinality |
| dimension | enum/blank | `mate`、`sample_role`、`producer`或空 |
| dimension_value | string/blank | `r1/r2`、`tumor/normal`、`fastp/samtools/...` |
| execution_managed | boolean | 参考索引/注释等是否由执行端托管 |
| wdl_binding | string | `path.wdl:Task.variable` 映射；命令内中间槽用 `command:<token>` |

变体约束建议单独新建 `tool_input_variant.csv`，不在每个槽行重复组约束：

| 列 | 含义 |
|---|---|
| tool_id | 工具 |
| variant | 工具内唯一变体名 |
| exactly_one_variant | 当工具有多个 variant 时必须为 true |
| min_present | 该 variant 中至少存在的槽数；MultiQC 的报告集合使用 1 |
| max_present | 可空；通常等于变体槽数 |

### 2.2 输出槽

`tool_output_format.csv` 建议列为：`tool_id,slot_name,artifact,semantic_label,wdl_type,dimension,dimension_value,wdl_binding`。输出没有 `required` 和 input variant 的校验语义；optional 由 `wdl_type=File?` 表达。

### 2.3 NEXT

`tool_relationship.csv` 保留现有列，但唯一键必须是：

```
(tool_id, next_tool_id, kind, output, input)
```

`kind=data` 时 `output`/`input` 必填且必须引用已登记槽；`kind=order` 时两者必须为空。

### 2.4 向后兼容迁移

- 现有行先做等价扩展：`slot_name=artifact=SEMANTIC_TO_ARTIFACT[label]`，`required` 从 `OPTIONAL_INPUT_SLOTS` 回填，`variant=legacy`。
- 该扩展本身只保持当前行为，不引入 mate/sample role。任何新具名槽上线前，必须同时完成 NEXT 四元组、资产取得/绑定和 variant 校验。
- 旧 `语义输入格式` 列可在一个过渡版保留为 alias，但同步器不得再由它生成 `slot_name`。

## 3. 变体语义

```
fastp single_end = [raw_fastq_read_r1]
fastp paired_end = [raw_fastq_read_r1, raw_fastq_read_r2]

trim_galore single_end = [raw_fastq_read_r1]
trim_galore paired_end = [raw_fastq_read_r1, raw_fastq_read_r2]

star single_end = [clean_fastq_read_r1, genome_index]
star paired_end = [clean_fastq_read_r1, clean_fastq_read_r2, genome_index]

gatk single = [sorted_dedup_bam, sorted_dedup_bai, genome_reference,
               interval_list, known_sites]
gatk paired = [tumor_sorted_dedup_bam, tumor_sorted_dedup_bai,
               normal_sorted_dedup_bam, normal_sorted_dedup_bai,
               genome_reference, interval_list, germline_resource,
               common_variants]

exactly_one_variant = true
```

`panel_of_normals` 在 WDL 中通过空 String 条件启用，因此是 paired variant 的 optional 槽。MultiQC 的 `summary` variant 对各 producer 槽均为 optional，但 `min_present=1`。

## 4. 28 工具目标槽表

下表是校验脚本的机器可读区域；表头不得改名。`required` 仅对 input 有意义。`待补` 行不是可同步槽。

| tool_id | slot_name | direction | artifact | required | variant | WDL variable | evidence |
|---|---|---|---|---|---|---|---|
| fastp | raw_fastq_read_r1 | input | raw_fastq_read | true | single_end,paired_end | read1 | wes_somatic_pair.wdl:PreprocessSample.read1 |
| fastp | raw_fastq_read_r2 | input | raw_fastq_read | true | paired_end | read2 | wes_somatic_pair.wdl:PreprocessSample.read2 |
| fastp | clean_fastq_read_r1 | output | clean_fastq_read | false | - | command --out1 | wes_somatic_pair.wdl:150-157 |
| fastp | clean_fastq_read_r2 | output | clean_fastq_read | false | - | command --out2 | wes_somatic_pair.wdl:150-157 |
| fastp | fastp_reports | output | quality_control_report | false | - | command --html,--json | wes_somatic_pair.wdl:156-157; Array[File] bundle |
| fastqc | raw_fastq_read_r1 | input | raw_fastq_read | true | raw_single,raw_paired | sample_r1 | rnaseq_singletask.wdl:RNASeqAnalysis.sample_r1 |
| fastqc | raw_fastq_read_r2 | input | raw_fastq_read | true | raw_paired | sample_r2 | rnaseq_singletask.wdl:RNASeqAnalysis.sample_r2 |
| fastqc | clean_fastq_read_r1 | input | clean_fastq_read | true | clean_single,clean_paired | command trimmed R1 | wes_somatic_pair.wdl:159 |
| fastqc | clean_fastq_read_r2 | input | clean_fastq_read | true | clean_paired | command trimmed R2 | wes_somatic_pair.wdl:159 |
| fastqc | fastqc_reports | output | quality_control_report | false | - | fastqc_htmls,fastqc_zips | rnaseq_singletask.wdl:247-248; Array[File] bundle |
| trim_galore | raw_fastq_read_r1 | input | raw_fastq_read | true | single_end,paired_end | sample_r1 | rnaseq_singletask.wdl:69,115-117 |
| trim_galore | raw_fastq_read_r2 | input | raw_fastq_read | true | paired_end | sample_r2 | rnaseq_singletask.wdl:70,115 |
| trim_galore | clean_fastq_read_r1 | output | clean_fastq_read | false | - | trimmed_r1 | rnaseq_singletask.wdl:249 |
| trim_galore | clean_fastq_read_r2 | output | clean_fastq_read | false | - | trimmed_r2 | rnaseq_singletask.wdl:250 |
| trim_galore | trim_galore_reports | output | quality_control_report | false | - | command side output | Trim Galore command; WDL declaration pending |
| bwa | clean_fastq_read_r1 | input | clean_fastq_read | true | paired_end | command trimmed R1 | wes_somatic_pair.wdl:161-165 |
| bwa | clean_fastq_read_r2 | input | clean_fastq_read | true | paired_end | command trimmed R2 | wes_somatic_pair.wdl:161-165 |
| bwa | genome_reference | input | genome_reference | true | paired_end | ref_path | wes_somatic_pair.wdl:PreprocessSample.ref_path |
| bwa | aligned_bam | output | aligned_bam | false | - | command pipe | BWA output pipes to samtools sort; boundary is conceptual |
| star | clean_fastq_read_r1 | input | clean_fastq_read | true | single_end,paired_end | sample_r1 then TRIMMED_R1 | rnaseq_singletask.wdl:69,130-132 |
| star | clean_fastq_read_r2 | input | clean_fastq_read | true | paired_end | sample_r2 then TRIMMED_R2 | rnaseq_singletask.wdl:70,130-132 |
| star | genome_index | input | genome_index | true | single_end,paired_end | star_genome_index | rnaseq_singletask.wdl:73 |
| star | rrna_depleted_fastq_read_r1 | output | rrna_depleted_fastq_read | false | - | unmapped_r1 | rnaseq_singletask.wdl:251 |
| star | rrna_depleted_fastq_read_r2 | output | rrna_depleted_fastq_read | false | - | unmapped_r2 | rnaseq_singletask.wdl:252 |
| star | aligned_bam | output | aligned_bam | false | - | genome_bam | rnaseq_singletask.wdl:253 |
| star | transcriptome_bam | output | transcriptome_bam | false | - | transcript_bam | rnaseq_singletask.wdl:254 |
| star | star_reports | output | quality_control_report | false | - | log | rnaseq_singletask.wdl:262; STAR log subset requires materialization |
| samtools | aligned_bam | input | aligned_bam | true | default | genome_bam or BWA stream | rnaseq_singletask.wdl:253; wes command pipe |
| samtools | sorted_dedup_bam | output | sorted_dedup_bam | false | - | dedup_bam or bam | rnaseq_singletask.wdl:255; wes PreprocessSample.bam |
| samtools | sorted_dedup_bai | output | bam_index | false | - | dedup_bai or bai | rnaseq_singletask.wdl:256; wes PreprocessSample.bai |
| samtools | samtools_reports | output | quality_control_report | false | - | flagstat,stats,idxstats | wes_somatic_pair.wdl:193-201; Array[File] bundle |
| gatk | sorted_dedup_bam | input | sorted_dedup_bam | true | single | command markdup BAM | wes_somatic_pair.wdl:168-190 |
| gatk | sorted_dedup_bai | input | bam_index | true | single | command markdup BAI | wes_somatic_pair.wdl:174 |
| gatk | tumor_sorted_dedup_bam | input | sorted_dedup_bam | true | paired | tumor_bam | wes_somatic_pair.wdl:Mutect2Pair.tumor_bam |
| gatk | tumor_sorted_dedup_bai | input | bam_index | true | paired | tumor_bai | wes_somatic_pair.wdl:Mutect2Pair.tumor_bai |
| gatk | normal_sorted_dedup_bam | input | sorted_dedup_bam | true | paired | normal_bam | wes_somatic_pair.wdl:Mutect2Pair.normal_bam |
| gatk | normal_sorted_dedup_bai | input | bam_index | true | paired | normal_bai | wes_somatic_pair.wdl:Mutect2Pair.normal_bai |
| gatk | genome_reference | input | genome_reference | true | single,paired | ref_path | wes_somatic_pair.wdl:PreprocessSample.ref_path and Mutect2Pair.ref_path |
| gatk | interval_list | input | interval_list | true | single,paired | interval_list | wes_somatic_pair.wdl:PreprocessSample.interval_list and Mutect2Pair.interval_list |
| gatk | known_sites | input | known_sites_vcf | true | single | known_sites | wes_somatic_pair.wdl:PreprocessSample.known_sites Array[String] |
| gatk | germline_resource | input | population_vcf | true | paired | pop_af_resource | wes_somatic_pair.wdl:Mutect2Pair.pop_af_resource |
| gatk | common_variants | input | population_vcf | true | paired | common_variants | wes_somatic_pair.wdl:Mutect2Pair.common_variants |
| gatk | panel_of_normals | input | panel_of_normals_vcf | false | paired | pon_path | wes_somatic_pair.wdl:247-251 conditional String path |
| gatk | bqsr_bam | output | sorted_dedup_bam | false | - | bam | wes_somatic_pair.wdl:PreprocessSample.bam |
| gatk | bqsr_bai | output | bam_index | false | - | bai | wes_somatic_pair.wdl:PreprocessSample.bai |
| gatk | unfiltered_vcf | output | unfiltered_vcf | false | - | unfiltered_vcf | wes_somatic_pair.wdl:Mutect2Pair.unfiltered_vcf |
| gatk | unfiltered_vcf_index | output | vcf_index | false | - | unfiltered_vcf_index | wes_somatic_pair.wdl:Mutect2Pair.unfiltered_vcf_index |
| gatk | filtered_vcf | output | filtered_vcf | false | - | filtered_vcf | wes_somatic_pair.wdl:Mutect2Pair.filtered_vcf |
| gatk | filtered_vcf_index | output | vcf_index | false | - | filtered_vcf_index | wes_somatic_pair.wdl:Mutect2Pair.filtered_vcf_index |
| gatk | gatk_reports | output | quality_control_report | false | - | qc_files | wes_somatic_pair.wdl:Mutect2Pair.qc_files Array[File] |
| bcftools | unfiltered_vcf | input | unfiltered_vcf | true | filter | unfiltered_vcf | wes_somatic_pair.wdl:Mutect2Pair.unfiltered_vcf |
| bcftools | filtered_vcf | input | filtered_vcf | true | normalize | filtered_vcf | wes_somatic_pair.wdl:PostprocessAndAnnotate.filtered_vcf |
| bcftools | genome_reference | input | genome_reference | true | normalize | ref_path | wes_somatic_pair.wdl:PostprocessAndAnnotate.ref_path |
| bcftools | filtered_vcf | output | filtered_vcf | false | - | filtered_vcf | wes_somatic_pair.wdl:Mutect2Pair.filtered_vcf |
| bcftools | filtered_vcf_index | output | vcf_index | false | - | filtered_vcf_index | wes_somatic_pair.wdl:Mutect2Pair.filtered_vcf_index |
| bcftools | pass_vcf | output | filtered_vcf | false | - | pass_vcf | wes_somatic_pair.wdl:PostprocessAndAnnotate.pass_vcf |
| bcftools | pass_vcf_index | output | vcf_index | false | - | pass_vcf_index | wes_somatic_pair.wdl:PostprocessAndAnnotate.pass_vcf_index |
| bcftools | normalized_vcf | output | normalized_vcf | false | - | normalized_vcf | wes_somatic_pair.wdl:PostprocessAndAnnotate.normalized_vcf |
| bcftools | normalized_vcf_index | output | vcf_index | false | - | normalized_vcf_index | wes_somatic_pair.wdl:PostprocessAndAnnotate.normalized_vcf_index |
| bcftools | bcftools_reports | output | quality_control_report | false | - | qc_files subset | wes_somatic_pair.wdl:PostprocessAndAnnotate.qc_files |
| snpeff | normalized_vcf | input | normalized_vcf | true | default | normalized_vcf | wes_somatic_pair.wdl:PostprocessAndAnnotate.normalized_vcf command |
| snpeff | annotation_database | input | annotation_database | true | default | snpeff_genome/config | wes_somatic_pair.wdl:349-351 |
| snpeff | annotated_vcf | output | annotated_vcf | false | - | annotated_vcf | wes_somatic_pair.wdl:PostprocessAndAnnotate.annotated_vcf |
| snpeff | annotated_vcf_index | output | vcf_index | false | - | annotated_vcf_index | wes_somatic_pair.wdl:PostprocessAndAnnotate.annotated_vcf_index |
| snpeff | snpeff_reports | output | quality_control_report | false | - | snpeff_html,snpeff_csv | wes_somatic_pair.wdl:413-414; Array[File] bundle |
| rsem | transcriptome_bam | input | transcriptome_bam | true | default | transcript_bam | rnaseq_singletask.wdl:254 |
| rsem | transcriptome_index | input | transcriptome_index | true | default | rsem_index | rnaseq_singletask.wdl:74 |
| rsem | gene_abundance_matrix | output | expression_abundance_matrix | false | - | rsem_genes | rnaseq_singletask.wdl:257 |
| rsem | isoform_abundance_matrix | output | expression_abundance_matrix | false | - | rsem_isoforms | rnaseq_singletask.wdl:258 |
| featurecounts | sorted_dedup_bam | input | sorted_dedup_bam | true | default | dedup_bam | rnaseq_singletask.wdl:255 |
| featurecounts | genome_annotation_gtf | input | genome_annotation | true | default | gtf_file | rnaseq_singletask.wdl:75 |
| featurecounts | expression_count_matrix | output | expression_count_matrix | false | - | featurecounts | rnaseq_singletask.wdl:259 |
| featurecounts | featurecounts_reports | output | quality_control_report | false | - | featurecounts_summary | rnaseq_singletask.wdl:260; Array[File] bundle |
| multiqc | fastp_reports | input | quality_control_report | false | summary | tumor_qc/normal_qc subset | wes_somatic_pair.wdl:MultiQC arrays |
| multiqc | fastqc_reports | input | quality_control_report | false | summary | tumor_qc/normal_qc or fastqc arrays | wes_somatic_pair.wdl:429-430; rnaseq lines 247-248 |
| multiqc | trim_galore_reports | input | quality_control_report | false | summary | workdir side outputs | rnaseq_singletask MultiQC scans dot |
| multiqc | star_reports | input | quality_control_report | false | summary | log subset | rnaseq_singletask.wdl:log and MultiQC scans dot |
| multiqc | samtools_reports | input | quality_control_report | false | summary | tumor_qc/normal_qc subset | wes_somatic_pair.wdl:429-430 |
| multiqc | gatk_reports | input | quality_control_report | false | summary | mutect_qc | wes_somatic_pair.wdl:431 |
| multiqc | bcftools_reports | input | quality_control_report | false | summary | mutect_qc/postprocess_qc subset | wes_somatic_pair.wdl:431-432 |
| multiqc | snpeff_reports | input | quality_control_report | false | summary | postprocess_qc subset | wes_somatic_pair.wdl:432 |
| multiqc | featurecounts_reports | input | quality_control_report | false | summary | workdir side output | rnaseq_singletask MultiQC scans dot |
| multiqc | quality_control_report | output | quality_control_report | false | - | multiqc_html or multiqc_report | wes_somatic_pair.wdl:459; rnaseq_singletask.wdl:261 |
| cellranger | raw_fastq_read_r1 | input | raw_fastq_read | true | paired_end | fastq_file1 | cellranger_workflow.wdl:RunFullPipeline.fastq_file1 |
| cellranger | raw_fastq_read_r2 | input | raw_fastq_read | true | paired_end | fastq_file2 | cellranger_workflow.wdl:RunFullPipeline.fastq_file2 |
| cellranger | transcriptome_reference | input | transcriptome_index | true | paired_end | transcriptome | cellranger_workflow.wdl:RunFullPipeline.transcriptome |
| cellranger | fastqc_reports | output | quality_control_report | false | - | fastqc_reports | cellranger_workflow.wdl:RunFullPipeline.fastqc_reports |
| cellranger | raw_feature_bc_matrix | output | feature_barcode_matrix | false | - | raw_feature_bc_matrix | cellranger_workflow.wdl:RunFullPipeline.raw_feature_bc_matrix |
| cellranger | filtered_feature_bc_matrix | output | feature_barcode_matrix | false | - | filtered_feature_bc_matrix | cellranger_workflow.wdl:RunFullPipeline.filtered_feature_bc_matrix |
| cellranger | web_summary | output | quality_control_report | false | - | web_summary | cellranger_workflow.wdl:RunFullPipeline.web_summary |
| cellranger | cloupe_file | output | cloupe_file | false | - | cloupe_file | cellranger_workflow.wdl:RunFullPipeline.cloupe_file |
| cellranger | aligned_bam | output | aligned_bam | false | - | bam_file | cellranger_workflow.wdl:RunFullPipeline.bam_file File? |
| cellranger | metrics_summary | output | quality_control_report | false | - | metrics_summary | cellranger_workflow.wdl:RunFullPipeline.metrics_summary |
| driver_gene_gender | somatic_maf | input | somatic_maf | true | default | maf | driver_gene_gender_analysis.wdl:analyze_driver_gene_gender.maf |
| driver_gene_gender | clinical_table | input | clinical_table | true | default | clinical_xls | driver_gene_gender_analysis.wdl:analyze_driver_gene_gender.clinical_xls |
| driver_gene_gender | sample_metadata | input | sample_metadata | true | default | metainfo_xlsx | driver_gene_gender_analysis.wdl:analyze_driver_gene_gender.metainfo_xlsx |
| driver_gene_gender | sample_mapping | output | sample_metadata | false | - | sample_mapping_tsv | driver_gene_gender_analysis.wdl:37 |
| driver_gene_gender | gene_results | output | analysis_table | false | - | gene_results_tsv | driver_gene_gender_analysis.wdl:43 |
| driver_gene_gender | mutation_matrix | output | mutation_matrix | false | - | binary_matrix_tsv_gz | driver_gene_gender_analysis.wdl:44 |
| driver_gene_gender | diagnostics | output | quality_control_report | false | - | requested presence,mapping,group/cohort/tumor summaries | driver_gene_gender_analysis.wdl:38-42; Array[File] bundle |
| driver_gene_gender | figures | output | analysis_figure | false | - | 8 PNG/PDF outputs | driver_gene_gender_analysis.wdl:45-52; Array[File] bundle |
| tmb_calculation | somatic_maf | input | somatic_maf | true | default | maf_file | tmb_survival_analysis.wdl:PreparePatientTMB.maf_file |
| tmb_calculation | clinical_table | input | clinical_table | true | default | clinical_file | tmb_survival_analysis.wdl:PreparePatientTMB.clinical_file |
| tmb_calculation | sample_metadata | input | sample_metadata | true | default | metainfo_file | tmb_survival_analysis.wdl:PreparePatientTMB.metainfo_file |
| tmb_calculation | patient_tmb | output | tmb_table | false | - | patient_tmb_tsv | tmb_survival_analysis.wdl:PreparePatientTMB.patient_tmb_tsv |
| tmb_calculation | unique_mutations | output | mutation_table | false | - | unique_mutations_tsv | tmb_survival_analysis.wdl:PreparePatientTMB.unique_mutations_tsv |
| tmb_calculation | run_mapping | output | sample_metadata | false | - | run_mapping_tsv | tmb_survival_analysis.wdl:PreparePatientTMB.run_mapping_tsv |
| tmb_calculation | unmapped_runs | output | quality_control_report | false | - | unmapped_runs_tsv | tmb_survival_analysis.wdl:PreparePatientTMB.unmapped_runs_tsv |
| tmb_calculation | preprocessing_summary | output | quality_control_report | false | - | preprocessing_summary_json | tmb_survival_analysis.wdl:PreparePatientTMB.preprocessing_summary_json |
| limma | 待补 | 待补 | 待补 | false | 待补 | no independent variable | DiffExprGo/Kegg are composite tasks |
| clusterprofiler | 待补 | 待补 | 待补 | false | 待补 | no independent variable | composite R task |
| reactomepa | 待补 | 待补 | 待补 | false | 待补 | no independent variable | DiffExprKegg composite task |
| annotationdbi_org_hs | 待补 | 待补 | 待补 | false | 待补 | no independent variable | org.Hs.eg.db named in meta; AnnotationDbi not named; no task boundary |
| edger | 待补 | 待补 | 待补 | false | 待补 | no independent variable | package not named in WDL; preprocess_counts is composite |
| mclust | 待补 | 待补 | 待补 | false | 待补 | no independent variable | package not named in WDL; clustering tasks are composite |
| iobr_cibersort | 待补 | 待补 | 待补 | false | 待补 | no independent variable | RunImmuneInfiltration is whole workflow task |
| survival_survminer | 待补 | 待补 | 待补 | false | 待补 | no independent variable | analysis tasks exist; package names absent; no boundary |
| dbscan | 待补 | 待补 | 待补 | false | 待补 | no independent variable | package not named in WDL; her2 task is composite |
| maftools | 待补 | 待补 | 待补 | false | 待补 | no independent variable | package not named in WDL; landscape task is composite |
| deseq2 | 待补 | 待补 | 待补 | false | 待补 | no independent variable | package not named in WDL; WGCNA task is composite |
| wgcna | 待补 | 待补 | 待补 | false | 待补 | no independent variable | RunWGCNA also includes STRINGdb/igraph logic |
| stringdb_igraph | 待补 | 待补 | 待补 | false | 待补 | no independent variable | packages not named in WDL; RunWGCNA is composite |

## 5. 目标 NEXT 边

### 5.1 可由现有 WDL/command 直接审核的边

| 源工具 | 产物槽 | 目标工具 | 接收槽 | kind | 依据 |
|---|---|---|---|---|---|
| fastp | clean_fastq_read_r1 | fastqc | clean_fastq_read_r1 | data | WES PreprocessSample command |
| fastp | clean_fastq_read_r2 | fastqc | clean_fastq_read_r2 | data | WES PreprocessSample command |
| fastp | clean_fastq_read_r1 | bwa | clean_fastq_read_r1 | data | WES PreprocessSample command |
| fastp | clean_fastq_read_r2 | bwa | clean_fastq_read_r2 | data | WES PreprocessSample command |
| fastp | fastp_reports | multiqc | fastp_reports | data | WES qc_files 聚合 |
| fastqc | fastqc_reports | multiqc | fastqc_reports | data | WES/RNA WDL |
| fastqc | - | trim_galore | - | order | RNA workflow 先 QC 后 trimming |
| trim_galore | clean_fastq_read_r1 | star | clean_fastq_read_r1 | data | RNA command |
| trim_galore | clean_fastq_read_r2 | star | clean_fastq_read_r2 | data | RNA command |
| trim_galore | trim_galore_reports | multiqc | trim_galore_reports | data | RNA MultiQC 扫描工作目录 |
| bwa | aligned_bam | samtools | aligned_bam | data | WES command pipe |
| star | aligned_bam | samtools | aligned_bam | data | RNA task |
| star | transcriptome_bam | rsem | transcriptome_bam | data | RNA task |
| star | star_reports | multiqc | star_reports | data | RNA task log/materialized STAR log |
| samtools | sorted_dedup_bam | featurecounts | sorted_dedup_bam | data | RNA task |
| samtools | sorted_dedup_bam | gatk | sorted_dedup_bam | data | WES preprocessing single variant |
| samtools | sorted_dedup_bai | gatk | sorted_dedup_bai | data | WES preprocessing single variant |
| samtools | sorted_dedup_bam | gatk | tumor_sorted_dedup_bam | data | WES PreprocessTumor → Mutect2Pair |
| samtools | sorted_dedup_bai | gatk | tumor_sorted_dedup_bai | data | WES PreprocessTumor → Mutect2Pair |
| samtools | sorted_dedup_bam | gatk | normal_sorted_dedup_bam | data | WES PreprocessNormal → Mutect2Pair |
| samtools | sorted_dedup_bai | gatk | normal_sorted_dedup_bai | data | WES PreprocessNormal → Mutect2Pair |
| samtools | samtools_reports | multiqc | samtools_reports | data | WES qc_files |
| gatk | unfiltered_vcf | bcftools | unfiltered_vcf | data | Mutect2Pair command |
| gatk | filtered_vcf | bcftools | filtered_vcf | data | PostprocessAndAnnotate input |
| gatk | gatk_reports | multiqc | gatk_reports | data | mutect_qc |
| bcftools | normalized_vcf | snpeff | normalized_vcf | data | PostprocessAndAnnotate command |
| bcftools | bcftools_reports | multiqc | bcftools_reports | data | WES qc_files |
| snpeff | snpeff_reports | multiqc | snpeff_reports | data | postprocess_qc |
| featurecounts | featurecounts_reports | multiqc | featurecounts_reports | data | RNA MultiQC scan |
| cellranger | fastqc_reports | multiqc | fastqc_reports | data | RunFullPipeline output |
| cellranger | web_summary | multiqc | fastqc_reports | data | 待确认：MultiQC 是否解析 Cell Ranger web summary |
| cellranger | metrics_summary | multiqc | fastqc_reports | data | 待确认：MultiQC Cell Ranger module 接受文件粒度 |

上表 32 行：30 条有 WDL/command 直接依据，2 条 Cell Ranger 报告边待确认。当前 CSV 是 14 条（11 data + 3 order）。报告槽落地后，fastp/FastQC/Trim Galore/STAR/SAMtools/GATK/BCFtools/SnpEff/featureCounts 到 MultiQC 可从 order 或隐式扫描升级为 data，前提是执行端能物化每个 `Array[File]` 报告束。

### 5.2 待原子边界后确认的边

| 候选边 | 状态 | 理由 |
|---|---|---|
| rsem.gene_abundance_matrix → limma | 待确认边界 | limma 可接经合适变换/归一化的连续表达量；当前 DiffExpr task 与 enrichment 复合 |
| featurecounts.expression_count_matrix → deseq2 | 待确认边界 | raw counts 是 DESeq2 合理输入，但没有独立 WDL task |
| featurecounts.expression_count_matrix → limma | 不登记 | raw counts 不能在没有 voom/normalization 语义时当作 TPM/FPKM |
| rsem.gene_abundance_matrix → deseq2 | 不登记 | RSEM abundance 不是当前约定的 raw-count 契约 |
| limma → clusterprofiler/reactomepa | 待确认边界 | GO/Kegg WDL 支持生物学顺序，但中间 gene-list artifact 未独立声明 |
| deseq2 → wgcna | 待确认 | 当前 WGCNA WDL 输入是 counts，PrepareInputs 自行预处理；不应先假定 DESeq2 中间产物 |
| tmb_calculation.patient_tmb → survival_survminer | 待确认边界 | AnalyzeTMBSurvival 实际接 patient_tmb_tsv，但 survival 节点未拆 |
| maftools → driver_gene_gender/survival/tmb | 不建议作为必经边 | 三者的 WDL 直接接 MAF，不需要先经过 maftools |

## 6. 规模和影响

### 6.1 槽与边

- 当前 12 atomic tools：34 槽（19 input + 15 output），14 NEXT（11 data + 3 order）。
- 本规格可同步的具体槽：109；13 个复合边界工具只有 `待补` 占位，不计入可同步槽。当前到目标的距离是缺 95 槽、有 20 个 legacy 槽将被具名槽替代，14 个共有槽属性相同。
- 目标 NEXT 目前有 30 条可审核边 + 2 条 Cell Ranger 待确认边；16 工具的下游边不在边界未定时补齐。

### 6.2 stage-two 提示词

当前 12 工具菜单已知为 3323 字符。在不改叙述密度的前提下：

- 仅将 12 工具扩展到本规格槽，预计约 7.5k–9k 字符。
- 28 工具都完成独立边界后，按目前每工具平均描述量估算约 11k–15k。这是区间而非精确值，因为 13 个工具的槽和 NEXT 尚未有 WDL 边界。
- 应将菜单序列化纳入回归基线，而不在本阶段改 prompt 来“优化”数字。

### 6.3 测试影响

任务背景记录为 63 个测试；2026-07-24 实际 `unittest discover` 已收集并运行 64 个（其中 3 个 skip）。需重点重跑/扩展的是：

- atomic capability 数量和菜单快照：当前断言 12 个工具的用例。
- stage-two prompt 只读取 atomic 目录、接口名和 `allowed_next_tool_ids` 的用例。
- `_validate_custom_steps` 的 input/output 精确名、artifact 兼容、NEXT、必需外部输入和连通性用例。
- `_custom_tool_chain` / `_select_asset` 的 FASTQ R1/R2、tumor/normal、BAM/BAI 资产绑定用例。
- Neo4j 集成测试中的 tool/edge 数量断言。
- 新增必需：variant 互斥、paired 缺 R2、tumor/normal 角色冲突、同工具对多条 NEXT、MultiQC `min_present=1`、报告束类型校验。

## 7. 判断

规格中最需要先审批的不是某个 artifact 名，而是“目录原子边界是否允许比 WDL task 更细”。BWA → samtools 和 GATK/BCFtools/SnpEff 都这样做了，但 WDL 没有声明所有中间产物。如果继续这个方向，拆解负责人必须同时交付 WDL task 拆分或明确的物化适配层，否则目录是不可执行的逻辑图。

我建议多子命令工具用稳定阶段节点 + `operation_profile`，并保持现有生物学中间产物边界；不为 index/stats/query 每个子命令建节点。这能保持菜单可用，同时避免伪造 WDL 未暴露的交换文件。

1.5 节未列出但必须纳入实施设计的缺口是 MultiQC 的多生产者扇入：只有“一个 generic report 槽”不够，必须是每个 producer 一个具名 `Array[File]` 槽，再加 `min_present=1`。这是条件必需性的另一个实例。

明天拆解前最应先定：规范槽名/WDL 映射、variant 校验契约、复合 task 的物化边界。报告粒度和 16 工具 artifact 命名紧随其后，但不应在前三项未定时开始录入。
