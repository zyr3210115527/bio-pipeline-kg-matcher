# WDL 与当前目录的映射审计

> 审计日期：2026-07-24。本文只记录事实和差异；不修改 CSV、Neo4j 或运行时。机器可读明细见 `docs/wdl_inventory.json`。

## 1. WDL 布局与规模

- 位置：`incoming/bio_pipelines_repo/pipelines/<pipeline_id>/<pipeline_id>.wdl`。
- 结构：每个目录是一个流程，不是按原子工具分目录，也不是平铺。
- 数量：14 个 `.wdl`，14 个 workflow 定义，**26 个 task 定义**。“28”是本轮拟定目录中 12 个已登记工具 + 16 个待原子化软件/脚本的概念总数，不是 WDL task 数。
- 配套文件：14/14 目录有 `knowledge_card.yaml`，13/14 有 `example_inputs.json`；`rnaseq_unsupervised_cluster` 缺少 example inputs。没有 pipeline 级 README 或 Dockerfile。
- 每个 WDL 都同时有 workflow 和 task；不是“只有零散 task”。

## 2. Workflow 调用顺序

| pipeline | workflow | call 顺序（alias 保留） |
|---|---|---|
| cellranger_workflow | CellRangerFullPipeline | RunFullPipeline |
| diff_expr_go | DiffExprGoWorkflow | DiffExprGo |
| diff_expr_kegg | DiffExprKeggWorkflow | DiffExprKegg |
| driver_gene_gender_analysis | driver_gene_gender_analysis | analyze_driver_gene_gender |
| her2_pfs_survival | her2_pfs_survival | analyze_her2_pfs |
| immune_infiltration_iobr | ImmuneInfiltrationIOBRCIBERSORT | RunImmuneInfiltration |
| paired_fastq_to_unmapped_bam | ConvertPairedFastQsToUnmappedBamWf | PairedFastQsToUnmappedBAM → CreateFoFN（后者在 `if create_fq` 中） |
| rnaseq_singletask | RNASeqPipeline | RNASeqAnalysis |
| rnaseq_unsupervised_cluster | rnaseq_unsupervised_cluster | preprocess_counts → hvg_pca_gmm → bootstrap_stability |
| survival_analysis | SurvivalAnalysis | ExtractMutation → LogRankTest → CoxRegression → SummarizeResults |
| tmb_survival_analysis | TMBSurvivalAnalysis | PreparePatientTMB → AnalyzeTMBSurvival |
| wes_somatic_maf_landscape | wes_somatic_maf_landscape | prepare_maf_for_landscape → plot_top30_mutation_landscape |
| wes_somatic_pair | WesSomaticPair | PreprocessTumor → PreprocessNormal → Mutect2Pair → PostprocessAndAnnotate → MultiQC |
| wgcna | HRA000074_WGCNA | PrepareInputs → RunWGCNA |

## 3. Task 人读汇总

表中 `?` 是 WDL optional type，`=...` 表示有默认值。完整默认值和每个声明的源码行号在 JSON 清单中。

| WDL / task | File 输入 | 其他主要输入 | 输出 | command 摘要 | runtime |
|---|---|---|---|---|---|
| cellranger_workflow / RunFullPipeline | fastq_file1, fastq_file2, transcriptome | sample_id, expect_cells, force_cells, chemistry, no_bam | fastqc_reports:Array[File], raw/filtered_feature_bc_matrix, web_summary, cloupe_file, bam_file?, metrics_summary | `cellranger count`; FastQC | docker, cpu, memory, disk |
| diff_expr_go / DiffExprGo | expression_matrix | sample arrays, quant_type, cutoffs, script path | differential_expression, up/down genes, 6 GO tables, mapping, background | Rscript（脚本参数） | docker |
| diff_expr_kegg / DiffExprKegg | expression_matrix | sample arrays, quant_type, cutoffs, script path | differential_expression, up/down genes, reactome_up/down, mapping, background | Rscript（脚本参数） | docker |
| driver_gene_gender / analyze_driver_gene_gender | maf, clinical_xls, metainfo_xlsx | input_samples; plotting/default resource params | 7 TSV/TSV.GZ + 8 PNG/PDF | `analyze_driver_gene_gender.R` | docker, cpu, memory |
| her2_pfs / analyze_her2_pfs | tpm_matrix, clinical_xls, metainfo_xlsx | gene, winsor limits | summary, QC, logrank, analysis, outliers, figure/warning arrays | `her2_pfs_survival.R` | docker, cpu, memory, disk |
| immune_infiltration / RunImmuneInfiltration | expression_tsv, clinical_xls, metainfo_xlsx | sample_ids and analysis/default params | status/summary/warning/manifests, CIBERSORT/fraction tables, 10 figures | `immune_infiltration_iobr.R` | docker, cpu, memory, disk |
| paired_fastq_to_unmapped_bam / PairedFastQsToUnmappedBAM | fastq_1, fastq_2 | read-group metadata, gatk_path, resources | output_unmapped_bam | GATK FastqToSam | docker, memory, disk, preemptible |
| paired_fastq_to_unmapped_bam / CreateFoFN | 无（ubam 是 String） | ubam, fofn_name | fofn_list | `ls >` FoFN | docker, preemptible |
| rnaseq_singletask / RNASeqAnalysis | sample_r1, sample_r2?, 3 indexes, gtf_file | is_paired, adapter, strandedness, resources | FastQC arrays; trimmed/unmapped R1/R2; genome/transcript BAM; dedup BAM/BAI; RSEM 2 files; counts/summary; MultiQC/log | FastQC, Trim Galore, STAR×2, samtools sort/fixmate/markdup/index, RSEM, featureCounts, MultiQC | docker, cpu, memory, disk |
| rnaseq_cluster / preprocess_counts | count_tsv | filtering/resource params | normalized_logcpm, sample/gene QC, summary, kept_samples | `01_preprocess_counts.R` | docker, cpu, memory |
| rnaseq_cluster / hvg_pca_gmm | logcpm_tsv | HVG/PCA/GMM/resource params | 8 TSV/TXT + 4 PNG/PDF | `02_hvg_pca_gmm.R` | docker, cpu, memory |
| rnaseq_cluster / bootstrap_stability | logcpm_tsv | bootstrap/PCA/GMM/resource params | 7 tables（含 Array[File]）+ 4 PNG/PDF | `03_bootstrap_stability.R` | docker, cpu, memory |
| survival / ExtractMutation | maf_file, clinical_file, metainfo_file | gene_symbol, docker_image | merged_data, summary | `extract_mutation.R` | docker, cpu, memory, disk |
| survival / LogRankTest | merged_data | docker_image | KM PNG/PDF, statistics | `survival_analysis.R` | docker, cpu, memory, disk |
| survival / CoxRegression | merged_data | docker_image | results, summary | `cox_regression.R` | docker, cpu, memory, disk |
| survival / SummarizeResults | mutation_summary, logrank_stats, cox_results, cox_summary | docker_image | summary_table | `summarize_results.R` | docker, cpu, memory, disk |
| tmb / PreparePatientTMB | maf_file, clinical_file, metainfo_file | capture/classes/resource defaults | TMB/mutation/mapping tables + summary JSON | `prepare_tmb_inputs.R` | docker, cpu, memory, disk |
| tmb / AnalyzeTMBSurvival | patient_tmb_tsv | output/min-group/resource defaults | survival/logrank/report + 6 PNG/PDF | `tmb_survival_analysis.R` | docker, cpu, memory, disk |
| maf_landscape / prepare_maf_for_landscape | maf_file | filters/resource defaults | prepared_maf, summary, class counts | `prepare_maf.R` | docker, cpu, memory, disk |
| maf_landscape / plot_top30_mutation_landscape | prepared_maf | top_n/prefix/resource defaults | 6 figures + 4 tables | `plot_maf_landscape.R` | docker, cpu, memory, disk |
| wes_pair / PreprocessSample | read1, read2, interval_list | ref_path, known_sites, IDs/resources | bam, bai, qc_files:Array[File] | fastp, FastQC, BWA, samtools sort/index/QC, GATK MarkDuplicates/BQSR | docker, cpu, memory, disk |
| wes_pair / Mutect2Pair | tumor_bam/bai, normal_bam/bai, interval_list | ref/resources/sample IDs | unfiltered/filtered VCF+index, F1R2/model/pileups/contamination/segments, qc_files | GATK Mutect2/filtering suite + bcftools index/stats/query | docker, cpu, memory, disk |
| wes_pair / PostprocessAndAnnotate | filtered_vcf/index | ref_path, SnpEff params/resources | PASS/normalized/annotated VCF+index, SnpEff HTML/CSV, qc_files | bcftools view/norm/index/stats/query + SnpEff ann | docker, cpu, memory, disk |
| wes_pair / MultiQC | tumor_qc, normal_qc, mutect_qc, postprocess_qc (all Array[File]) | pair_id, docker_image | multiqc_html | MultiQC | docker, cpu, memory, disk |
| wgcna / PrepareInputs | counts_tsv, clinical_xls, metainfo_xlsx | sample/filter/resource defaults | datExpr, traits, sample_info, background, QC, figure arrays, tar | `prepare_wgcna_input.R` | docker, cpu, memory |
| wgcna / RunWGCNA | datExpr, traits, sample_info, background_hvg | WGCNA/STRING/resource defaults | module/network/stability/hub outputs, figures, tar | `run_wgcna_analysis.R` | docker, cpu, memory |

## 4. 12 个已登记工具的接口差异

“目录”列来自 `data/csv/relations/tool_input_format.csv` 和 `tool_output_format.csv`；当前 `slot_name == artifact`。`req/opt` 来自同步器的 `OPTIONAL_INPUT_SLOTS`。

| tool_id | 目录输入 | WDL/command 实际输入 | 目录输出 | WDL/command 实际输出 | 差异与影响 |
|---|---|---|---|---|---|
| fastp | raw_fastq_read(req) | `PreprocessSample.read1/read2` | clean_fastq_read | command 产生 trimmed R1/R2 + HTML + JSON | 少 R2、双路 clean FASTQ 和两种报告；配对链无法精确传播 mate，报告无法 data-bind 到 MultiQC。 |
| fastqc | raw_fastq_read(opt), clean_fastq_read(opt) | `sample_r1/sample_r2?`；WES 中对两个 trimmed mate 运行 | quality_control_report | `fastqc_htmls:Array[File]`, `fastqc_zips:Array[File]`；WES 并入 `qc_files` | 少 R1/R2 和 HTML/ZIP 具名输出；不能表达原始/清洗四种变体。 |
| bwa | clean_fastq_read(req), genome_annotation(req) | WES command 同时使用 trimmed R1/R2 + `ref_path` | aligned_bam | BWA SAM 经 pipe 进 `samtools sort` | 少 clean R2；BWA 与 samtools 没有 task 边界，`aligned_bam` 是概念切分而非 WDL 输出。 |
| star | clean_fastq_read(req), genome_annotation(req) | `sample_r1/sample_r2?`经 Trim Galore；`rrna_star_index`, `star_genome_index` | clean_fastq_read, aligned_bam, transcriptome_bam | `unmapped_r1/r2?`, `genome_bam`, `transcript_bam` | 少 mate 输入/输出；`clean_fastq_read` 实为 rRNA STAR 的 unmapped/rRNA-depleted reads，语义过宽。 |
| samtools | aligned_bam(req) | RNA command 串含 sort/fixmate/markdup/index；WES 含 sort/index/flagstat/stats/idxstats | sorted_dedup_bam | `dedup_bam`, `dedup_bai`；WES `bam`, `bai`, 3 类 QC | 少 BAI 和报告输出；报告到 MultiQC 只能表达 order。 |
| gatk | sorted_dedup_bam(req), genome_annotation(req) | 单样本 BQSR 与配对 Mutect2 两套；配对明示 `tumor_bam/bai`, `normal_bam/bai` | sorted_dedup_bam, unfiltered_vcf | BQSR BAM/BAI；Mutect2 unfiltered/filtered VCF、索引及多个 QC 中间件 | 单槽折叠 tumor/normal，且单样本/配对条件必需无法表达；会阻断或错绑配对 WES。 |
| bcftools | unfiltered_vcf(req) | Mutect2 task 的 unfiltered/filtered VCF；Postprocess 的 filtered VCF+index+reference | filtered_vcf | filtered/PASS/normalized/annotated 各阶段 VCF+TBI，stats/query 报告 | 子命令和阶段被折叠；缺索引、normalized/PASS 和 QC 输出。 |
| snpeff | filtered_vcf(req), genome_annotation(req) | Postprocess 使用 normalized VCF，genome/config 为 String 参数 | annotated_vcf | annotated VCF+TBI, `snpeff_html`, `snpeff_csv` | 少索引与 HTML/CSV 报告；MultiQC 无 data 边。 |
| trim_galore | raw_fastq_read(req) | `sample_r1`, `sample_r2?`，由 `is_paired` 分支 | clean_fastq_read | `trimmed_r1`, `trimmed_r2?`；命令还会生成 trimming report，WDL 未声明 | 少 R2 和报告；配对链无法表达两路传播。 |
| rsem | transcriptome_bam(req), genome_annotation(req) | `transcript_bam`, `rsem_index` | expression_abundance_matrix | `rsem_genes`, `rsem_isoforms` | 两种粒度输出被折成一槽；下游无法指明 gene 或 isoform。 |
| featurecounts | sorted_dedup_bam(req), genome_annotation(req) | `dedup_bam`, `gtf_file` | expression_count_matrix | `featurecounts`, `featurecounts_summary` | 少 summary 报告；它不应通向要求 TPM/FPKM 的 limma。 |
| multiqc | quality_control_report(opt) | WES 为 `tumor_qc`, `normal_qc`, `mutect_qc`, `postprocess_qc` 四个 Array[File]；RNA task 扫描工作目录 | quality_control_report | `multiqc_html` / `multiqc_report` | 当前单槽既不能表达四路具名数组，也不能在 `tool-chain/v1` 中对一槽聚合多个上游。 |

## 5. 多实例维度

| 工具/边界 | 输入 | WDL 表达 | 目录表达 | 是否匹配 |
|---|---|---|---|---|
| fastp | raw FASTQ mates | `read1:File` + `read2:File` | 一个 `raw_fastq_read` | 否 |
| FastQC | raw/clean mates | `sample_r1:File` + `sample_r2:File?`；WES 两个 clean 文件 | raw/clean 各一槽 | 否 |
| Trim Galore | raw FASTQ mates | `sample_r1:File` + `sample_r2:File?` | 一个 `raw_fastq_read` | 否 |
| BWA | clean FASTQ mates | command 中两个具名位置参数 | 一个 `clean_fastq_read` | 否 |
| STAR | clean/rRNA-depleted mates | `sample_r1` + `sample_r2?`，命令传两 mate | 一个 `clean_fastq_read` | 否 |
| GATK Mutect2 | sample role | `tumor_bam/bai` + `normal_bam/bai` | 一个 `sorted_dedup_bam` | 否 |
| Cell Ranger | FASTQ mates | `fastq_file1:File` + `fastq_file2:File` | 工具未登记 | 否（缺目录） |
| FastqToSam | FASTQ mates | `fastq_1:File` + `fastq_2:File` | pipeline-level 语义一槽 | 否（原子化后必须拆槽） |
| MultiQC | producer groups | 4 个具名 `Array[File]` | 一个 optional File 槽 | 否 |
| 其他 task | 数组 | 多数是 `Array[String]` 参数或 `Array[File]` 图/报告输出 | 未登记 | 不适用/待拆解 |

命名并不统一：双端输入同时出现 `fastq_file1/2`、`fastq_1/2`、`sample_r1/r2`、`read1/2`和 workflow 级 `tumor_r1/r2`。因此“按 WDL 变量名对齐”不能理解为直接复制某一个局部名称，必须先定一个规范层并保留 WDL 映射。

## 6. 未原子化的 16 个概念工具

| 概念工具 | WDL 证据 | 独立 task 边界 | 结论 |
|---|---|---|---|
| cellranger | RunFullPipeline 明示 `cellranger count` | 是 | 可直接从 task 接口建槽 |
| limma | DiffExprGo/Kegg 脚本和镜像能力 | 否 | 与富集分析复合，待补独立边界 |
| clusterProfiler | DiffExprGo WDL meta 明示点名 | 否 | 待补 |
| ReactomePA | DiffExprKegg WDL meta 明示点名（流程名叫 Kegg） | 否 | 待补 |
| AnnotationDbi + org.Hs.eg.db | GO/Reactome WDL meta 点名 `org.Hs.eg.db`，未点名 AnnotationDbi | 否 | 待补；更像依赖包而非可编排 step |
| edgeR | WDL 未点名；只有 `preprocess_counts` 脚本语义 | 否 | 待补，不能由 WDL 确认软件边界 |
| mclust | WDL 未点名；只有 `hvg_pca_gmm/bootstrap` 脚本语义 | 否 | 待补，不能由 WDL 确认软件边界 |
| IOBR / CIBERSORT | RunImmuneInfiltration | 否（整个免疫流程一个 task） | 待补 |
| survival + survminer | survival/her2/tmb 分析 task 存在，WDL 未点名 R 包 | 否 | 待补 |
| dbscan | WDL 未点名；her2 只暴露复合分析 task | 否 | 待补 |
| maftools | WDL 未点名；MAF landscape 只暴露复合脚本 | 否 | 待补 |
| DESeq2 | WDL 未点名；WGCNA 只暴露复合脚本 | 否 | 待补 |
| WGCNA | RunWGCNA | 否（同 task 还含 STRINGdb/igraph 等） | 待补 |
| STRINGdb + igraph | WDL 未点名；`RunWGCNA` 是复合 task | 否 | 待补 |
| driver_gene_gender | analyze_driver_gene_gender | 是 | 可直接从 task 接口建槽 |
| tmb_calculation | PreparePatientTMB | 是 | 计算阶段可建槽；AnalyzeTMBSurvival 属后续生存分析 |

### 孤儿盘点

- **WDL 有证据、原子目录无登记**：上表 16 个概念工具都未作为 atomic tool 登记，但只有 3 个具有可直接采用的独立 task 边界。
- **原子目录有登记、无独立 WDL task**：12 个已登记工具中，除 WES 的 `MultiQC` 外，工具大多嵌在 `PreprocessSample`、`Mutect2Pair`、`PostprocessAndAnnotate` 或 `RNASeqAnalysis` 复合 task 中。这说明当前 atomic 边界是目录设计，不是 WDL task 边界的直接镜像。

## 7. 多子命令的实际组织

- **samtools**：没有独立 task。RNA 的单个 task 串行 sort → fixmate → sort → markdup → index；WES 的 PreprocessSample 串行 sort/index 与 flagstat/stats/idxstats。
- **GATK**：按流程阶段分在不同复合 task：PreprocessSample 包含 MarkDuplicates/BaseRecalibrator/ApplyBQSR，Mutect2Pair 包含 Mutect2/GetPileupSummaries/CalculateContamination/LearnReadOrientationModel/FilterMutectCalls，PairedFastQsToUnmappedBAM 使用 FastqToSam。
- **bcftools**：Mutect2Pair 中做 index/stats/query，PostprocessAndAnnotate 中做 view/norm/index/stats/query。
- **STAR**：`RNASeqAnalysis` 一个 task 内调用两次：先去 rRNA，再对基因组比对；不是一子命令一 task。

## 8. 判断

最出乎意料的差异不是 GATK 本身，而是“26 个 task 并不等于 28 个原子工具”：WDL 在不少地方刻意使用复合 task，与目录的原子边界不同。如果直接把软件名从 command 抽出就建节点，会创造 WDL 不存在的中间产物契约。

对多子命令工具，我倾向“一个稳定生物学阶段一节点，节点带 `operation/subcommand_profile`”，而不是每个 CLI 子命令一节点。理由是 WDL 中子命令之间往往没有声明输出，强拆会同时要求新的中间 artifact、容器和错误恢复边界。

1.5 节之外还有三个同类缺口：RSEM gene/isoform 输出被折叠；STAR 的 `clean_fastq_read` 其实是 rRNA-depleted/unmapped reads；MultiQC 需要固定四路 `Array[File]` 聚合，“具名槽”可以解决固定路数，但现有单绑定契约仍无法表达任意多上游聚合。

如果明天开始拆解，最先定的三件事是：（1）规范槽名与 WDL 局部变量的映射规则；（2）复合 task 的生物学边界和 operation/subcommand 表达；（3）variant 的选择、必需性和资产角色校验契约。
