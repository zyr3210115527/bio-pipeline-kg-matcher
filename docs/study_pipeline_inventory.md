# Study-Pipeline 库存盘点

> 生成方式：代码直接跑 `assess_feasibility` + 文件元数据统计。

> 数据来源：`T1.csv`（标准化）+ `T2.csv`（处理后）+ `T11.csv`（遗留原始）。

## 一、每个 study 能跑哪些流程

| study | tumor_type | project.data_types | T1 strategy | 格式分布（T1+T2+T11） | 可配对数 | 可行 pipeline |
|---|---|---|---|---|---|---|
| HRA000071 | Glioma | Transcriptome or Gene expression | WES: 1144 | FASTQ: 2288<br>BAM: 1<br>other: 1<br>MAF: 1<br>VCF: 3<br>clinical: 1<br>metainfo: 1 | 0 | `driver_gene_gender_analysis`<br>`paired_fastq_to_unmapped_bam`<br>`rnaseq_singletask`<br>`survival_analysis`<br>`tmb_survival_analysis`<br>`wes_somatic_maf_landscape` |
| HRA000074 | Glioma | Transcriptome or Gene expression | RNA-Seq: 1386 | FASTQ: 2772<br>other: 3<br>expr_matrix: 3<br>metainfo: 1 | 0 | `diff_expr_go`<br>`diff_expr_kegg`<br>`rnaseq_singletask`<br>`rnaseq_unsupervised_cluster`<br>`wes_somatic_maf_landscape` |
| HRA007167 | Melanoma | Exome， Transcriptome or Gene expression， Single cell sequencing | RNA-Seq: 162 | FASTQ: 324<br>BAM: 1<br>dir: 1<br>expr_matrix: 3<br>other: 1<br>metainfo: 1 | 0 | `diff_expr_go`<br>`diff_expr_kegg`<br>`rnaseq_singletask`<br>`rnaseq_unsupervised_cluster` |
| HRA007169 | Melanoma | Exome， Transcriptome or Gene expression， Single cell sequencing | WES: 336 | FASTQ: 672<br>BAM: 1<br>other: 1<br>MAF: 1<br>dir: 2<br>VCF: 3 | 0 | `wes_somatic_maf_landscape` |
| HRA001272 | Liver Cancer | Exome， Transcriptome or Gene expression， Raw sequence reads | WES: 1500<br>RNA-Seq: 860 | FASTQ: 4720<br>BAM: 2<br>other: 2<br>expr_matrix: 3<br>MAF: 1<br>dir: 3<br>VCF: 3<br>clinical: 1 | 0 | `diff_expr_go`<br>`diff_expr_kegg`<br>`paired_fastq_to_unmapped_bam`<br>`rnaseq_singletask`<br>`rnaseq_unsupervised_cluster`<br>`wes_somatic_maf_landscape` |
| HRA000122 | Leukemia | Exome， Transcriptome or Gene expression | — | FASTQ: 696 | 0 | — |
| HRA005191 | Lung Cancer | Transcriptome or Gene expression | scRNA-Seq: 970 | FASTQ: 1940<br>other: 1<br>metainfo: 1 | 0 | `rnaseq_singletask` |
| HRA001748 | Liver Cancer | Single cell sequencing, WES | scRNA-Seq: 320 | FASTQ: 640<br>dir: 1<br>metainfo: 1 | 0 | `paired_fastq_to_unmapped_bam`<br>`rnaseq_singletask` |
| HRA001749 | Liver Cancer | Single cell sequencing, WES | WES: 356 | FASTQ: 712<br>BAM: 1<br>other: 1<br>MAF: 1<br>dir: 2<br>VCF: 3<br>metainfo: 1 | 0 | `paired_fastq_to_unmapped_bam`<br>`rnaseq_singletask`<br>`wes_somatic_maf_landscape` |
| HRA006499 | Liver Cancer | Exome， Transcriptome or Gene expression | WES: 1526 | FASTQ: 3052<br>BAM: 2<br>dir: 2<br>VCF: 3<br>metainfo: 1 | 13 | `paired_fastq_to_unmapped_bam`<br>`wes_somatic_maf_landscape` |
| HRA003107 | Esophageal Cancer | Whole genome sequencing， Epigenomics， Transcriptome or Gene expression | WGS: 532<br>RNA-Seq: 620 | FASTQ: 2304<br>BAM: 1<br>dir: 1<br>expr_matrix: 3<br>other: 1<br>metainfo: 1 | 0 | `diff_expr_go`<br>`diff_expr_kegg`<br>`paired_fastq_to_unmapped_bam`<br>`rnaseq_singletask`<br>`rnaseq_unsupervised_cluster` |
| HRA000021 | Esophageal Cancer | Whole genome sequencing | — | BAM: 1017<br>VCF: 3 | 0 | `wes_somatic_maf_landscape` |
| HRA000873 | Colorectal Cancer | Exome， Raw sequence reads | WES: 4060 | FASTQ: 8120<br>BAM: 1<br>MAF: 1<br>other: 3<br>VCF: 2 | 1015 | `paired_fastq_to_unmapped_bam`<br>`rnaseq_singletask`<br>`wes_somatic_maf_landscape` |
| HRA000321 | multiple cancers | Transcriptome or Gene expression、Raw sequence reads | — | other: 1<br>metainfo: 1 | 0 | `wes_somatic_maf_landscape` |

## 二、反向覆盖率：每个 pipeline 能被多少 study 喂饱

| pipeline | 可行 study 数 | 涉及 individual 数 | 零覆盖 |
|---|---|---|---|
| `diff_expr_go` | 4 | 1039 | ✅ 有覆盖 |
| `diff_expr_kegg` | 4 | 1039 | ✅ 有覆盖 |
| `driver_gene_gender_analysis` | 1 | 572 | ✅ 有覆盖 |
| `her2_pfs_survival` | 0 | 0 | ❌ 零覆盖 |
| `immune_infiltration_iobr` | 0 | 0 | ❌ 零覆盖 |
| `paired_fastq_to_unmapped_bam` | 7 | 2269 | ✅ 有覆盖 |
| `rnaseq_singletask` | 9 | 3077 | ✅ 有覆盖 |
| `rnaseq_unsupervised_cluster` | 4 | 1039 | ✅ 有覆盖 |
| `survival_analysis` | 1 | 572 | ✅ 有覆盖 |
| `tmb_survival_analysis` | 1 | 572 | ✅ 有覆盖 |
| `wes_somatic_maf_landscape` | 9 | 2090 | ✅ 有覆盖 |
| `wgcna` | 0 | 0 | ❌ 零覆盖 |

## 三、MAF 和表达矩阵来源

### MAF 文件

| study | MAF 文件数 | 样例文件名 | 来源 | 该 study 有原始 FASTQ? |
|---|---|---|---|---|
| HRA000071 | 1 | HRA000071-SomaticSNV-1.0.maf | T2 | 是 |
| HRA000873 | 1 | HRA000873-SomaticSNV-1.0.full.maf | T2 | 是 |
| HRA001272 | 1 | HRA001272-SomaticSNV-1.0.maf | T2 | 是 |
| HRA001749 | 1 | HRA001749-SomaticSNV-1.0.maf | T2 | 是 |
| HRA007169 | 1 | HRA007169-SomaticSNV-1.0.maf | T2 | 是 |

### 表达矩阵文件

| study | 矩阵文件数 | 样例文件名 | 来源 | 该 study 有原始 FASTQ? |
|---|---|---|---|---|
| HRA000074 | 3 | HRA000074-Genes-counts-1.0.tsv | T2 | 是 |
| HRA001272 | 3 | HRA001272-Genes-counts-1.0.tsv | T2 | 是 |
| HRA003107 | 3 | HRA003107-Genes-counts-1.0.tsv | T2 | 是 |
| HRA007167 | 3 | HRA007167-Genes-counts-1.0.tsv | T2 | 是 |

### HRA000074 count 矩阵来源

- `[T2] HRA000074-Genes-counts-1.0.tsv` → path: `/hpcdisk1/cbb_group/data/analysis/HRA000074/HRA000074-Genes-counts-1.0.tsv`
- `[T2] HRA000074-Genes-FPKM-1.0.tsv` → path: `/hpcdisk1/cbb_group/data/analysis/HRA000074/HRA000074-Genes-FPKM-1.0.tsv`
- `[T2] HRA000074-Genes-TPM-1.0.tsv` → path: `/hpcdisk1/cbb_group/data/analysis/HRA000074/HRA000074-Genes-TPM-1.0.tsv`

HRA000074 同时有 RNA-Seq FASTQ（T1）和 `HRA000074-Genes-counts/TPM/FPKM-1.0.tsv`（T2）。矩阵文件名带 `Genes-` 和版本号 `1.0`，是 study-level 汇总结果，应由上游 RNA-seq 流程（STAR/featureCounts 或 RSEM）产出后导入。

## 四、HRA000021 的 BAM 详情

HRA000021 共有 BAM 文件 **1016** 个（来自 `T11.csv` 遗留表；`T1.csv` 中无此 study 数据）。

| 样例文件名 | format | data_type | file_path | 命名线索 |
|---|---|---|---|---|
| HRR067347.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067347.bam | 无明确标记 |
| HRR067348.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067348.bam | 无明确标记 |
| HRR067349.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067349.bam | 无明确标记 |
| HRR067350.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067350.bam | 无明确标记 |
| HRR067351.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067351.bam | 无明确标记 |
| HRR067352.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067352.bam | 无明确标记 |
| HRR067353.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067353.bam | 无明确标记 |
| HRR067354.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067354.bam | 无明确标记 |
| HRR067355.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067355.bam | 无明确标记 |
| HRR067356.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067356.bam | 无明确标记 |
| HRR067357.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067357.bam | 无明确标记 |
| HRR067358.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067358.bam | 无明确标记 |
| HRR067359.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067359.bam | 无明确标记 |
| HRR067360.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067360.bam | 无明确标记 |
| HRR067361.bam | bam | WGS | /mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067361.bam | 无明确标记 |

### 路径关键词统计

- 1016 个 BAM 路径中均未出现 sorted / dedup / uBAM / aligned 等关键字。

### 判断

- 文件名统一为 `HRRxxxxxx.bam`，路径为 `/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRRxxxxxx.bam`，**无 sorted/dedup/uBAM/aligned 等关键字**。
- `T2.csv` 中存在 `BAM-files`（104.10 TB）、`SomaticSNV-VCF-files`、`SomaticIndel-VCF-files`、`SomaticSV-VCF-files` 等目录条目，暗示这些 BAM 可能已用于体细胞变异检测流程。
- 但 `data_type` 均为 `WGS`，且 `Read Pair` 列为 `R067347` 等非标准值，说明遗留表的信息质量不足以判定 BAM 具体阶段。
- **建议**：若要在 `wes_somatic_pair` 中支持 BAM 入口，需先确认这些 BAM 是“已排序去重”还是“uBAM/原始比对 BAM”，否则执行端无法正确使用。

## 五、单侧多样本 5% 的具体形态

定义：按 `STUDY_ROLE_RULES` 能判定为 tumor/normal 的个体中，任一侧存在 ≥2 个 R1+R2 完整对，因而被 `_pair_wes_somatic_cases` 丢弃的个体。

被丢弃个体总数：**29**

| study | individual | tumor 对数 | normal 对数 | tumor sample_name | normal sample_name |
|---|---|---|---|---|---|
| HRA006499 | HRI783931 | 4 | 1 | P3C1_T, P3C2_T, P3C3_T, P3C4_T | P3_N |
| HRA006499 | HRI783932 | 3 | 1 | P4C1_T, P4C2_T, P4C3_T | P4_N |
| HRA006499 | HRI783934 | 5 | 1 | P6C1_T, P6C2_T, P6C3_T, P6C4_T, P6C5_T | P6_N |
| HRA006499 | HRI783936 | 3 | 1 | P8C1_T, P8C2_T, P8C3_T | P8_N |
| HRA006499 | HRI783937 | 2 | 1 | P9C1_T, P9C2_T | P9_N |
| HRA006499 | HRI783940 | 3 | 1 | P12C1_T, P12C2_T, P12C3_T | P12_N |
| HRA006499 | HRI783946 | 3 | 1 | P18C1_T, P18C2_T, P18C3_T | P18_N |
| HRA006499 | HRI783947 | 3 | 1 | P19C1_T, P19C2_T, P19C3_T | P19_N |
| HRA006499 | HRI783948 | 4 | 1 | P20C1_T, P20C2_T, P20C3_T, P20C4_T | P20_N |
| HRA006499 | HRI783949 | 4 | 1 | P21C1_T, P21C2_T, P21C3_T, P21C4_T | P21_N |
| HRA006499 | HRI783950 | 3 | 1 | P22C1_T, P22C2_T, P22C3_T | P22_N |
| HRA006499 | HRI783951 | 3 | 1 | P23C1_T, P23C2_T, P23C3_T | P23_N |
| HRA006499 | HRI783952 | 2 | 1 | P24C1_T, P24C2_T | P24_N |
| HRA006499 | HRI783953 | 5 | 1 | P25C1_T, P25C2_T, P25C3_T, P25C4_T, P25C5_T | P25_N |
| HRA006499 | HRI783954 | 5 | 1 | P26C1_T, P26C2_T, P26C3_T, P26C4_T, P26C5_T | P26_N |
| HRA006499 | HRI783955 | 3 | 1 | P27C1_T, P27C2_T, P27C3_T | P27_N |
| HRA006499 | HRI783956 | 4 | 1 | P28C1_T, P28C2_T, P28C3_T, P28C4_T | P28_N |
| HRA006499 | HRI783957 | 3 | 1 | P29C1_T, P29C2_T, P29C3_T | P29_N |
| HRA006499 | HRI783958 | 4 | 1 | P30C1_T, P30C2_T, P30C3_T, P30C4_T | P30_N |
| HRA006499 | HRI783959 | 2 | 1 | P31C1_T, P31C2_T | P31_N |
| HRA006499 | HRI783960 | 2 | 1 | P32C1_T, P32C2_T | P32_N |
| HRA006499 | HRI783964 | 2 | 1 | P36C2_T, P36C4_T | P36_N |
| HRA006499 | HRI783970 | 2 | 1 | P42C1_T, P42C2_T | P42_N |
| HRA006499 | HRI783979 | 2 | 1 | P60C2_T, P60C3_T | P60_N |
| HRA006499 | HRI783985 | 3 | 1 | P66C1_T, P66C2_T, P66C3_T | P66_N |
| HRA006499 | HRI783997 | 3 | 1 | P85C1_T, P85C2_T, P85C3_T | P85_N |
| HRA006499 | HRI784000 | 3 | 1 | P89C1_T, P89C2_T, P89C4_T | P89_N |
| HRA006499 | HRI784001 | 4 | 1 | P90C1_T, P90C2_T, P90C3_T, P90C4_T | P90_N |
| HRA006499 | HRI784003 | 3 | 1 | P92C1_T, P92C2_T, P92C3_T | P92_N |

### 形态总结

- `tumor=3, normal=1`: 13 个个体
- `tumor=2, normal=1`: 7 个个体
- `tumor=4, normal=1`: 6 个个体
- `tumor=5, normal=1`: 3 个个体

### 判断

- HRA006499 的肿瘤侧 sample_name 呈现 `P3C1_T`, `P3C2_T`, `P3C3_T` 等多区域模式（C1/C2/C3...），**强烈提示多区域取样（multi-region）**，不是技术重复。
- 这种情况下“取第一个”会丢失生物学信息，当前丢弃策略合理。
- HRA000873 未见明显多区域命名（样本少），被丢弃个体主要是单侧多样本的数学结果。

---

## 六、数据质量与口径说明

1. **HRA000122 有遗留 FASTQ 但系统不可见**
   - `T11.csv` 遗留表中有 696 条 HRA000122 FASTQ 记录，但 `T1.csv` 标准化表中无此 study。
   - 当前 `CsvKGDataMatcher` 以 `T1.csv` 为基准，仅通过文件名 join `T11.csv`，因此 HRA000122 的 FASTQ 未被加载到 `matcher.t1`。
   - 结果：表一中 HRA000122 显示 `FASTQ: 696`，但可行 pipeline 为 0（系统层面实际看不到）。

2. **HRA000321 的 `wes_somatic_maf_landscape` 可行性来自数据标注错误**
   - 表一显示 HRA000321 可行 pipeline 为 `wes_somatic_maf_landscape`。
   - 但 MAF 清单中无 HRA000321，因为它唯一的 `format=maf` 文件是 `Matrix-h5`（scRNA-seq 矩阵），`T2.csv` 把其格式错标为 `maf`。
   - `_role_of_file` 据此判定为 MAF，导致 `assess_feasibility` 误判。这是数据质量问题，不是目录问题。

3. **HRA000021 BAM 不在系统匹配范围内**
   - HRA000021 的 1016 个 BAM 仅存在于 `T11.csv`，不在 `T1.csv`。
   - 因此当前 `wes_somatic_pair` / `paired_fastq_to_unmapped_bam` 等流程不会匹配到这些 BAM。
   - 若要支持，需先把 T11 数据同步进 T1，或扩展 matcher 读取 T11 中未被 T1 覆盖的 study。

4. **FASTQ 计数口径**
   - 表一中 FASTQ 数量是文件级（R1 和 R2 分开计）。例如 HRA000873 的 `FASTQ: 8120` = 4060 对 × 2。
   - “可配对数”是按个体级 R1+R2 完整对计算，已去重。