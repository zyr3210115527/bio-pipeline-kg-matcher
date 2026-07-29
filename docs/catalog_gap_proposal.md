# Atomic Tool 目录补录提案

> 状态：只读提案，不改任何目录数据。
> 背景：NEXT 边改造过程中发现，多个工具的 QC/报告类输出未在 Neo4j 目录中注册，导致这些连接只能被归类为 order 边。

## 核对方法

- **Neo4j 当前注册**：从 `RegisteredMethodCatalog` 实际读取的 `inputs` / `outputs` slot（slot_name + artifact + formats）。
- **文档/CSV 记载**：`data/csv/entities/tool.csv` 中的“语义输入格式 / 语义输出格式”与“输入格式 / 输出格式”。
- **差异判定**：
  - 漏抄：CSV 明确列出、但目录未注册的输入/输出；补录后可能产生新的 data 边。
  - 有意简化：CSV 中只是格式描述，不应单独成 slot；保持现状。
  - 待确认：无法从现有信息判断是漏抄还是简化。

---

## 逐工具核对

### T01 fastp

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `raw_fastq_read` | Raw FASTQ | 一致 |
| outputs | `clean_fastq_read` | Clean FASTQ, **HTML**, **JSON** | 漏抄 `html_report`、`json_report` 两个输出 slot |

**补录后能新增的连接**：fastp→multiqc 可从 order 升级为 data（`html_report` / `json_report` → multiqc 的 `quality_control_report`）。

---

### T02 FastQC

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `clean_fastq_read`(optional), `raw_fastq_read`(optional) | Raw FASTQ, Clean FASTQ | 一致 |
| outputs | `quality_control_report` | Quality Control Report | 一致 |

无差异。fastqc→multiqc 已经是 data 边。

---

### T03 BWA

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `clean_fastq_read`, `genome_annotation` | Clean FASTQ, Genome Annotation | 一致 |
| outputs | `aligned_bam` | Aligned SAM/BAM | 一致 |

无差异。

---

### T04 SAMtools

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `aligned_bam` | Aligned SAM/BAM | 一致 |
| outputs | `sorted_dedup_bam` | Sorted/Dedup BAM, **BAI**, **TXT** | 漏抄 `bai_index`、`alignment_metrics/txt` 两类输出；当前把 `txt,bai,bam` 都挂在 `sorted_dedup_bam` 的 formats 上，混淆了主 BAM 与辅助文件 |

**补录后能新增的连接**：samtools→multiqc 可从 order 升级为 data（`alignment_metrics` → multiqc 的 `quality_control_report`）。

---

### T05 GATK

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `genome_annotation`, `sorted_dedup_bam` | Sorted/Dedup BAM, Genome Annotation | 一致 |
| outputs | `sorted_dedup_bam`, `unfiltered_vcf` | Sorted/Dedup BAM, Unfiltered VCF | 一致 |

无差异（GATK 实际还有很多中间输出，但 CSV 只列了这两个主输出）。

---

### T06 BCFtools

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `unfiltered_vcf` | Unfiltered VCF | 一致 |
| outputs | `filtered_vcf` | Filtered (PASS) VCF, **TBI** | 漏抄 `tbi_index` 输出；当前把 `tbi` 挂在 `filtered_vcf` 的 formats 上 |

**补录影响**：tbi 通常作为 `filtered_vcf` 的伴随文件，是否独立成 slot 取决于目录规范。建议待确认。

---

### T07 SnpEff

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `filtered_vcf`, `genome_annotation` | Filtered (PASS) VCF, Genome Annotation | 一致 |
| outputs | `annotated_vcf` | Annotated VCF, **HTML/TXT** | 漏抄 `annotation_report`（HTML/TXT 统计报告）输出 |

**补录后能新增的连接**：snpeff→multiqc 可从 order 升级为 data（`annotation_report` → multiqc 的 `quality_control_report`）。

---

### T08 Trim Galore

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `raw_fastq_read` | Raw FASTQ | 一致 |
| outputs | `clean_fastq_read` | Clean FASTQ, **TXT/HTML** | 漏抄 `trim_report` 输出；当前把 `txt/html` 挂在 `clean_fastq_read` 的 formats 上 |

**补录后能新增的连接**：trim_galore→multiqc 可从 order 升级为 data（`trim_report` → multiqc 的 `quality_control_report`）。

---

### T09 STAR

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `clean_fastq_read`, `genome_annotation` | Clean FASTQ, Genome Annotation | 一致 |
| outputs | `aligned_bam`, `clean_fastq_read`, `transcriptome_bam` | Clean FASTQ, Aligned SAM/BAM, Transcriptome BAM | 一致 |

无差异。

---

### T10 RSEM

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `genome_annotation`, `transcriptome_bam` | Transcriptome BAM, Genome Annotation | 一致 |
| outputs | `expression_abundance_matrix` | TPM / FPKM | 一致 |

无差异。

---

### T11 featureCounts

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `genome_annotation`, `sorted_dedup_bam` | Sorted/Dedup BAM, Genome Annotation | 一致 |
| outputs | `expression_count_matrix` | Raw Counts | 一致 |

无差异。

---

### T12 MultiQC

| 维度 | 当前目录注册 | CSV / 文档记载 | 差异 |
|---|---|---|---|
| inputs | `quality_control_report`(optional) | Quality Control Report, 各类日志 | 一致（`quality_control_report` 已足够概括） |
| outputs | `quality_control_report` | Quality Control Report | 一致 |

无差异。

---

## 汇总

### 明确漏抄（建议补录）

| 工具 | 建议补录的 slot | 可升级的数据边 |
|---|---|---|
| fastp | `html_report`, `json_report` | fastp→multiqc |
| SAMtools | `alignment_metrics` / `alignment_stats` | samtools→multiqc |
| SnpEff | `annotation_report` | snpeff→multiqc |
| Trim Galore | `trim_report` | trim_galore→multiqc |

### 待确认

| 工具 | 问题 |
|---|---|
| BCFtools | `tbi_index` 是否应作为 `filtered_vcf` 的独立 slot，还是继续作为 format 伴随？ |
| SAMtools | `bai_index` 是否应独立成 slot？当前与 `sorted_dedup_bam` 混在一起。 |

### 无差异

fastqc、bwa、gatk、star、rsem、featurecounts、multiqc。

---

## 建议

1. **先补录 4 个明确漏抄的报告类输出**：fastp HTML/JSON report、SAMtools alignment metrics、SnpEff annotation report、Trim Galore trim report。
2. **补录后重新判定 multiqc 入边**：上述 4 条边可从 order 升级为 data；其余 multiqc 入边（rsem、featurecounts、star、gatk）仍保持 order，因为它们的主输出与 `quality_control_report` artifact 不同。
3. **BCFtools / SAMtools 的索引类输出待目录负责人确认**：是否独立成 slot 取决于目录是否想把“索引文件”纳入编排决策。若纳入，可新增 `tbi_index`、`bai_index` slot；若不纳入，维持当前作为 formats 伴随即可。
