# Round 2 验证与补漏报告

> 生成时间：2026-07-23  
> 执行方式：只读探查 + 方案输出，未修改任何代码、CSV 或 Neo4j 数据，未运行 `sync_neo4j_tool_catalog.py --apply`。  
> 数据来源：`data/csv/entities/T1.csv`、`data/csv/T11.csv`、`data/csv/entities/T2.csv`、`pipeline_router.py` 实际代码。

---

## 任务 1：补跑查询 1（配对 WES 体细胞变异检测）

查询语句：

> 我有肿瘤和正常配对的 WES FASTQ，想做体细胞变异检测并注释

### 1.1 顶层状态

| 字段 | 值 |
|---|---|
| `workflow_mode` | `custom` |
| `selection_status` | `no_match` |
| `orchestration_status` | `no_match` |
| `execution_status` | `blocked_by_incomplete_method_decomposition` |
| `validation_ok` | `false` |
| `feasibility_status` | `ready` |

### 1.2 关键校验错误

```text
所需内部方法尚未完成原子化拆解，当前方法目录无法忠实表达该修改
自定义模式没有有效方法步骤
```

### 1.3 分解缺口（decomposition_gap）

```json
{
  "message": "配对样本汇合无法表达:gatk 在当前目录中只注册了 1 个 sorted_dedup_bam 输入槽,无法同时接收 tumor_bam, normal_bam。需要为该工具补充分样本输入槽。"
}
```

### 1.4 `agent_input.assets`（完整）

```json
[
  {
    "asset_id": "HRA000071-fastq_r1-1",
    "role": "fastq_r1",
    "path": "/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000071/HRR024685_f1.fq.gz",
    "format": "Raw FASTQ",
    "path_verified": false,
    "source": "T1",
    "individual_accession": "HRI023383",
    "sample_role": null
  },
  {
    "asset_id": "HRA000071-fastq_r2-2",
    "role": "fastq_r2",
    "path": "/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000071/HRR024685_r2.fq.gz",
    "format": "Raw FASTQ",
    "path_verified": false,
    "source": "T1",
    "individual_accession": "HRI023383",
    "sample_role": null
  }
]
```

### 1.5 判定

- **未回归为 ready**：顶层 `execution_status` 仍是 `blocked_by_incomplete_method_decomposition`，gatk 单 BAM 槽的限制仍然正确拦截双链汇合。
- **样本角色字段存在但为 null**：`individual_accession` 已透传，`sample_role` 字段存在，但 HRA000071 **没有**在 `STUDY_ROLE_RULES` 中登记角色规则，因此 `_sample_role` 返回 `None`。
- **匹配到了错误的 study**：查询的是“配对肿瘤/正常 WES”，系统却返回了 HRA000071（Glioma，无角色规则）而不是 HRA000873/HRA006499（有角色规则）。原因是 HRA000071 FASTQ 数量最多，LLM/排序阶段没有按“能否构成配对 somatic case”精排。
- **Feasibility 为 ready 是误导**：`feasibility.status=ready` 是因为 `paired_fastq_to_unmapped_bam` 只需要 2 个 FASTQ；但用户意图是体细胞变异检测，执行状态已被 block。

---

## 任务 2：三个“零覆盖”pipeline 是真没数据，还是角色识别失败？

### 2.1 `_role_of_file` 对 clinical / metainfo / expression 的判定规则

源码位置：`pipeline_router.py:468-490`

```python
if "clinical" in name:
    return "clinical"
if "metainfo" in name or "meta-info" in name:
    return "metainfo"
if any(x in name for x in ["counts", "count", "featurecounts", "htseq"]):
    return "expression_count"
if any(x in name for x in ["fpkm", "tpm", "rsem", "abundance"]):
    return "expression_abundance"
if "genes" in name:
    return "expression"
```

### 2.2 全库关键字扫描结果

扫描 `T1 + T11 + T2` 中文件名命中 clinical / metainfo / expression 关键字的文件，并给出 `_role_of_file` 实际判定：

| 角色 | 文件数 | 来源 | 样例文件名 |
|---|---|---|---|
| `clinical` | 2 | T2 | `HRA000071-Clinical-1.0.xlsx`、`HRA001272-Clinical-1.0.xls` |
| `metainfo` | 9 | T2 | `HRA000321-MetaInfo-1.0.xlsx`、`HRA001748-MetaInfo-1.0.xlsx`、`HRA005191-MetaInfo-1.0.xlsx`、`HRA000071-MetaInfo-1.0.xlsx`、`HRA000074-MetaInfo-1.0.xlsx`、`HRA001749-MetaInfo-1.0.xlsx`、`HRA003107-MetaInfo-1.0.xlsx`、`HRA006499-MetaInfo-1.0.xlsx`、`HRA007167-MetaInfo-1.0.xlsx` |
| `expression_count` | 4 | T2 | `HRA000074-Genes-counts-1.0.tsv`、`HRA001272-Genes-counts-1.0.tsv`、`HRA003107-Genes-counts-1.0.tsv`、`HRA007167-Genes-counts-1.0.tsv` |
| `expression_abundance` | 8 | T2 | `HRA000074-Genes-FPKM-1.0.tsv`、`HRA000074-Genes-TPM-1.0.tsv` 等 |

**结论：角色识别没有失败。** 这些文件都被 `_role_of_file` 正确分类；`expression_count` / `expression_abundance` 也能通过 `_role_satisfies` 满足 `expression` 需求。

### 2.3 为什么仍然零覆盖？

三个 pipeline（`wgcna`、`immune_infiltration_iobr`、`her2_pfs_survival`）的数据画像都是 `expression_clinical`：

```python
"expression_clinical": {
    "roles": ["expression", "clinical", "metainfo"],
    ...
}
```

需要同一 study **同时**具备 expression + clinical + metainfo。逐 study 核对：

| study | expression | clinical | metainfo | 三样齐全？ |
|---|---|---|---|---|
| HRA000071 | ❌ | ✅ | ✅ | ❌ |
| HRA000074 | ✅ | ❌ | ✅ | ❌ |
| HRA001272 | ✅ | ✅ | ❌ | ❌ |
| HRA003107 | ✅ | ❌ | ✅ | ❌ |
| HRA007167 | ✅ | ❌ | ✅ | ❌ |
| 其他 | 不全 | 不全 | 不全 | ❌ |

**结论：这三个 pipeline 是真没数据。** 没有任何一个 study 同时提供表达矩阵、临床表、样本信息表。

### 2.4 附带发现：`matcher.match()` 的 limit 会加剧零覆盖表象

用默认 `limit=10` 调用 `matcher._match_files()` 时，返回的 Top-50 文件常被 metainfo 文件占满，导致 `assess_feasibility` 报告“缺少 expression、clinical”；但即使把 limit 放开到无限，也**没有**任何一个 study 能凑齐三样。因此零覆盖结论成立，但机制是“数据缺失”而不是“角色误判”。

---

## 任务 3：全库 format / role 标注错误扫描

### 3.1 `format` 列 × 文件扩展名交叉表（T1 + T11 + T2）

| format | 扩展名 | 计数 | 备注 |
|---|---|---:|---|
| `Raw FASTQ` / `fastq.gz` | `.fastq.gz` | 18,212 | 一致 |
| `fq.gz` | `.fq.gz` | 5,362 | 一致 |
| `bam` | `.bam` | 1,016 | 一致 |
| `dir` | 无 | 34 | 目录条目，正常 |
| `tsv` | `.tsv` | 16 | 一致 |
| `xlsx` | `.xlsx` | 10 | 一致 |
| `xls` | `.xls` | 1 | 一致 |
| `maf` | `.maf` | 5 | 一致 |
| `maf` | 无 / 其他 | 4 | **矛盾** |
| `tsv` | `.maf` | 1 | **矛盾** |
| `tsv` | 无 / 其他 | 15 | 多为目录条目 |

### 3.2 明显矛盾项详情

| study | 文件名 | format 列 | 实际扩展名/内容 | 影响 |
|---|---|---|---|---|
| HRA000321 | `Matrix-h5` | `maf` | scRNA-seq h5 矩阵 | `wes_somatic_maf_landscape` 误判可行 |
| HRA001748 | `Matrix-h5` | `dir` | scRNA-seq h5 矩阵 | 被忽略，无法进入表达矩阵流程 |
| HRA005191 | `Matrix-h5` | `tsv` | scRNA-seq h5 矩阵 | 被当作 tsv，可能误入表达矩阵流程 |
| HRA000074 | `BAM` | `maf` | BAM 目录 | `wes_somatic_maf_landscape` 可能误判 |
| HRA000074 | `Fusion` | `maf` | 融合基因结果 | `wes_somatic_maf_landscape` 可能误判 |
| HRA000873 | `HRA000873-SomaticSNV-1.0.maf` | `tsv` | `.maf` | 格式列错标，但文件名含 maf，`_role_of_file` 仍判为 maf，影响较小 |
| HRA001272 | `Fusion` | `maf` | 融合基因结果 | `wes_somatic_maf_landscape` 可能误判 |
| HRA007169 | `BAM-files` | `tsv` | BAM 目录 | 可能被误判为表达/tsv 文件 |

### 3.3 影响最大的误判

- **HRA000321**：唯一一个 `format=maf` 的文件是 `Matrix-h5`，导致 `wes_somatic_maf_landscape` 被 assess 为可行，实际上该 study 没有 MAF。
- **HRA000074 / HRA001272 的 `Fusion`**：format=maf 但不是体细胞 SNV，进入 MAF 流程会产生语义错误。
- **三个 `Matrix-h5`**：格式标注混乱，导致 scRNA-seq 矩阵既可能误入 MAF 流程，也可能被表达矩阵流程遗漏。

---

## 任务 4：T1 / T11 / T2 三表关系盘点

### 4.1 三表定义

| 表 | 路径 | 行数 | 每行代表 | 关键列 |
|---|---|---:|---|---|
| T1 | `data/csv/entities/T1.csv` | 13,772 | 标准化后的数据实体（文件/Run 级） | `studyAccession`, `individualAccession`, `sampleAccession`, `runAccession`, `dataName`, `strategy` |
| T11 | `data/csv/T11.csv` | 15,484 | 遗留原始文件记录（物理路径、format、Read Pair） | `study_accession`, `files`, `format`, `file_path`, `data_level`, `Read Pair` |
| T2 | `data/csv/entities/T2.csv` | 86 | 处理后/聚合结果文件（表达矩阵、MAF、VCF 目录等） | `study_accession`, `files`, `format`, `file_path`, `size`, `data_level` |

### 4.2 `CsvKGDataMatcher` 实际加载逻辑

源码：`pipeline_router.py:628-634`

```python
legacy_t1 = _read_csv(csv_dir / "T11.csv") or _read_csv(csv_dir / "merge_metainfo.csv")
normalized_t1 = _read_csv(self.entity_dir / "T1.csv") if self.data_schema == "normalized-v2" else []
self.t1 = self._load_normalized_t1(normalized_t1, legacy_t1) if normalized_t1 else legacy_t1
if self.data_schema == "normalized-v2":
    self.t2 = _read_csv(self.entity_dir / "T2.csv")
```

- **T1 被加载**：以 `T1.csv` 为骨架，按文件名 join `T11.csv` 补充物理路径、format、Read Pair。
- **T11 仅作为 join 副表**：`T11.csv` 本身**不被直接消费**；只有那些文件名出现在 `T1.csv` 中的记录才会进入 `matcher.t1`。
- **T2 被完整加载**：所有 86 行都进入 `matcher.t2`。

### 4.3 各 study 在三表中的行数

| study | T1 | T11 | T2 |
|---|---|---:|---:|
| HRA000021 | 0 | 1,016 | 4 |
| HRA000071 | 1,144 | 1,144 | 8 |
| HRA000074 | 1,386 | 1,386 | 7 |
| HRA000122 | 0 | 696 | 0 |
| HRA000321 | 0 | 0 | 2 |
| HRA000873 | 4,060 | 4,060 | 7 |
| HRA001272 | 2,360 | 2,360 | 15 |
| HRA001748 | 320 | 320 | 2 |
| HRA001749 | 356 | 356 | 9 |
| HRA003107 | 1,152 | 1,152 | 7 |
| HRA005191 | 970 | 970 | 2 |
| HRA006499 | 1,526 | 1,526 | 8 |
| HRA007167 | 162 | 162 | 7 |
| HRA007169 | 336 | 336 | 8 |

### 4.4 系统“看不见”的数据

`T11.csv` 中文件名未在 `T1.csv` 出现的记录：**1,712 条**

| study | 类型 | 数量 | 说明 |
|---|---|---:|---|
| HRA000122 | FASTQ | 696 | 只在 T11，不在 T1 |
| HRA000021 | BAM | 1,016 | 只在 T11，不在 T1 |

### 4.5 若把 T11 也纳入匹配，哪些 study 会变化？

估算（不实施）：

| study | 当前系统可见 | 若 T11 全部纳入 | 新增可行 pipeline |
|---|---|---|---|
| HRA000122 | 0 文件 | 696 FASTQ | `cellranger_workflow`、`rnaseq_singletask`、`paired_fastq_to_unmapped_bam` |
| HRA000021 | 4 个 T2 目录条目 | 1,016 BAM + 4 目录 | 若 `wes_somatic_pair` 支持 BAM 入口，可能新增该流程；否则仅对 BAM 入口流程有意义 |

---

## 任务 5：fastqc → fastp 边改造方案（只出方案）

### 5.1 现状

当前 13 条 NEXT 边（MultiQC 8 条已移除）中：

- `fastp → fastqc` 是 **data 边**（`clean_fastq_read → clean_fastq_read`）
- `fastqc → trim_galore` 是 **order 边**

这意味着目录对“QC 与修剪的先后”有两种语义：

- fastp（修剪）→ fastqc（QC）：**先修剪，后 QC**
- fastqc → trim_galore：**先 QC，后修剪**

### 5.2 问题：查询 2 为什么返回空 steps？

查询 2：

> RNA-seq 上游流程里把 trim_galore 换成 fastp，其他不变

LLM 试图构造 `fastqc → fastp → star → ...` 的链，但当前边集里**没有 `fastqc → fastp`**，只有反向的 `fastp → fastqc`。因此无法通过 `_validate_custom_steps`。

### 5.3 方案选项

#### 选项 A：增加 `fastqc → fastp` order 边

- **kind**：`order`（fastqc 输出 `quality_control_report`，fastp 输入 `raw_fastq_read`，无数据槽对接）
- **output / input**：留空
- **效果**：支持 `fastqc → fastp → star` 的 RNA-seq 上游链。
- **风险**：与现有 `fastp → fastqc` data 边形成双向边。虽然 R4 禁止环，但菜单中同时存在 `fastp→fastqc` 和 `fastqc→fastp` 可能让 LLM 困惑。

#### 选项 B：把 `fastp → fastqc` 改为 `fastqc → fastp`

统一语义为“先 QC，后修剪/处理”。

- 符合 `fastqc → trim_galore` 的现有 order 语义。
- 但会改变现有标准 RNA-seq 链（当前 `rnaseq_singletask` 的 recipe 可能隐含 `fastp→fastqc`）。
- 需要确认 recipe 和测试是否依赖原方向。

#### 选项 C：保持现状，不新增边

继续由 LLM/执行端自行决定 QC 时机。查询 2 仍然失败，需要用户显式接受“fastp 替换 trim_galore”的语义变更。

### 5.4 倾向与理由

**倾向选项 A：新增 `fastqc → fastp` order 边，但同步审视 `fastp → fastqc` 是否应删除。**

理由：

1. 实际生信流程中，QC 既可以在修剪前（决定是否需要修）也可以在修剪后（评估修剪效果）。两种顺序都合理。
2. 但目录里同时存在 `fastp→fastqc`（data）和 `fastqc→fastp`（order）会让 LLM 把“先后”当成“任选”，可能导致非预期路径。
3. 如果目标是“支持查询 2 的替换语义（fastqc 在前、fastp 在后）”，最干净的方案是：
   - 加 `fastqc → fastp` order 边；
   - 同时把 `fastp → fastqc` 也改为 order 边（两边都不传数据，只表达顺序）；
   - 或者只保留一个主流方向。

**本轮不实施**，建议人工确认后再进 CSV。

---

## 任务 6：HRA000021 的 1016 个 BAM 处于哪个阶段？

### 6.1 T2 条目

```json
{
  "study_accession": "HRA000021",
  "files": "BAM-files",
  "file_type": "DIR",
  "format": "dir",
  "size": "104.10 TB",
  "size_bytes": "1.14455E+14",
  "file_path": "/hpcdisk1/cbb_group/data/analysis/HRA000021/BAM-files",
  "strategy": "genomic"
}
```

同 study 还有 3 个体细胞 VCF 目录条目，但大小均为 `0.00 B`：

- `SomaticIndel-VCF-files`
- `SomaticSNV-VCF-files`
- `SomaticSV-VCF-files`

### 6.2 T11 样例

| files | format | data_type | Read Pair | file_path |
|---|---|---|---|---|
| `HRR067347.bam` | `bam` | `WGS` | `R067347` | `/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000021/HRR067347.bam` |
| `HRR067348.bam` | `bam` | `WGS` | `R067348` | ... |
| ... | ... | ... | ... | ... |

文件名统一为 `HRRxxxxxx.bam`，路径中**无** `sorted`、`dedup`、`uBAM`、`aligned` 等关键字。

### 6.3 大小估算

- 1016 个 BAM，总大小 104.10 TB
- 平均每个 BAM：104.10 TB / 1016 ≈ **102 GB**

参考：

- 人全基因组原始比对 BAM（WGS）：约 80–150 GB/样本
- 排序去重后 BAM：约 70–120 GB/样本
- uBAM（未比对）：通常更小，约 30–60 GB/样本

### 6.4 判断

- **无法从元数据判定具体阶段**。102 GB 这个量级既可能是原始比对 BAM，也可能是排序去重后 BAM。
- T2 存在体细胞 VCF 目录条目（虽为 0 字节），暗示这些 BAM **可能**已经历过或计划经历体细胞变异检测流程。
- 未发现 README、md5 清单、文件命名标记等额外线索。

### 6.5 对“BAM 入口”提案的影响

在不能确认 BAM 阶段前，**不建议直接把 HRA000021 的 BAM 接入 `wes_somatic_pair`**。若执行端需要的是“已排序去重 BAM”，而实际是“原始比对 BAM”或“uBAM”，会直接导致流程失败。需要数据负责人补充以下信息：

1. BAM 是否已完成排序、去重、BQSR？
2. 是否有对应的 index（`.bai`）？
3. `Read Pair` 列的 `R067347` 等非标准值是否表示技术重复或 lane 拆分？

---

## 补上一轮遗漏

### A. `study_pipeline_inventory.md` 第一节完整 14 行表

> 注：以下“可行 pipeline”列是用 `pipeline_router.py` 实际代码跑出来的（调用 `assess_feasibility`），不是人工推的；但为避免 `matcher.match()` 默认 `limit=10` 造成的截断，这里使用**无限 limit** 下的全部文件做评估。

| study | tumor_type | project.data_types | T1 strategy | 格式分布（T1+T2，按 `_role_of_file`） | 可配对数 | 可行 pipeline 数 | 可行 pipeline 列表 |
|---|---|---|---|---:|---:|---|---|
| HRA000021 | Esophageal Cancer | Whole genome sequencing | — | bam:1, vcf:2, maf:1 | 0 | 1 | `wes_somatic_maf_landscape` |
| HRA000071 | Glioma | Transcriptome or Gene expression | WES:1144 | fastq:1144, bam:1, other:1, maf:2, vcf:2, clinical:1, metainfo:1 | 0 | 7 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam`, `survival_analysis`, `tmb_survival_analysis`, `wes_somatic_maf_landscape`, `driver_gene_gender_analysis` |
| HRA000074 | Glioma | Transcriptome or Gene expression | RNA-Seq:1386 | fastq:1386, maf:2, expression_count:1, expression_abundance:2, other:1, metainfo:1 | 0 | 7 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam`, `diff_expr_go`, `diff_expr_kegg`, `rnaseq_unsupervised_cluster`, `wes_somatic_maf_landscape` |
| HRA000122 | Leukemia | Exome， Transcriptome or Gene expression | — | — | 0 | 0 | — |
| HRA000321 | multiple cancers | Transcriptome or Gene expression、Raw sequence reads | — | maf:1, metainfo:1 | 0 | 1 | `wes_somatic_maf_landscape`（因 `Matrix-h5` 被错标为 maf） |
| HRA000873 | Colorectal Cancer | Exome， Raw sequence reads | WES:4060 | fastq:4060, bam:1, maf:4, other:1, vcf:1 | 1015 | 5 | `cellranger_workflow`, `rnaseq_singletask`, `wes_somatic_pair`, `paired_fastq_to_unmapped_bam`, `wes_somatic_maf_landscape` |
| HRA001272 | Liver Cancer | Exome， Transcriptome or Gene expression， Raw sequence reads | WES:1500, RNA-Seq:860 | fastq:2360, bam:2, maf:4, expression_count:1, expression_abundance:2, other:3, vcf:2, clinical:1 | 0 | 7 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam`, `diff_expr_go`, `diff_expr_kegg`, `rnaseq_unsupervised_cluster`, `wes_somatic_maf_landscape` |
| HRA001748 | Liver Cancer | Single cell sequencing, WES | scRNA-Seq:320 | fastq:320, other:1, metainfo:1 | 0 | 3 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam` |
| HRA001749 | Liver Cancer | Single cell sequencing, WES | WES:356 | fastq:356, bam:1, other:2, maf:3, vcf:2, metainfo:1 | 0 | 4 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam`, `wes_somatic_maf_landscape` |
| HRA003107 | Esophageal Cancer | Whole genome sequencing， Epigenomics， Transcriptome or Gene expression | WGS:532, RNA-Seq:620 | fastq:1152, bam:1, other:2, expression_count:1, expression_abundance:2, metainfo:1 | 0 | 6 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam`, `diff_expr_go`, `diff_expr_kegg`, `rnaseq_unsupervised_cluster` |
| HRA005191 | Lung Cancer | Transcriptome or Gene expression | scRNA-Seq:970 | fastq:970, other:1, metainfo:1 | 0 | 3 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam` |
| HRA006499 | Liver Cancer | Exome， Transcriptome or Gene expression | WES:1526 | fastq:1526, bam:2, maf:2, other:1, vcf:2, metainfo:1 | 13 | 5 | `cellranger_workflow`, `rnaseq_singletask`, `wes_somatic_pair`, `paired_fastq_to_unmapped_bam`, `wes_somatic_maf_landscape` |
| HRA007167 | Melanoma | Exome， Transcriptome or Gene expression， Single cell sequencing | RNA-Seq:162 | fastq:162, bam:1, other:2, expression_count:1, expression_abundance:2, metainfo:1 | 0 | 6 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam`, `diff_expr_go`, `diff_expr_kegg`, `rnaseq_unsupervised_cluster` |
| HRA007169 | Melanoma | Exome， Transcriptome or Gene expression， Single cell sequencing | WES:336 | fastq:336, bam:1, other:2, maf:3, vcf:2 | 0 | 4 | `cellranger_workflow`, `rnaseq_singletask`, `paired_fastq_to_unmapped_bam`, `wes_somatic_maf_landscape` |

### B. “1000 条”是真实匹配量还是 limit 截断？

上一轮“新过滤命中 1000 条”指的是 `wes_somatic_pair` 的 `data_combinations`。

实测：

| limit | file_candidates | data_combinations |
|---|---|---|
| 10 | 4 | 0 |
| 1000 | 4 | 1000 |
| 无限制 | 4 | **1028** |

**结论：1000 是 limit 截断，真实可配对数是 1028**（HRA000873 1015 + HRA006499 13）。

另外澄清 `T1.csv` FASTQ 总数：T1 共 13,772 行，按扩展名 `.fastq.gz` / `.fq.gz` 全部是 FASTQ 文件；按 `_role_of_file` 在 matcher 适配后也能全部识别为 fastq（因为 `T1_in_format.csv` 给所有 T1 文件标了 `Raw FASTQ`，其中含 `fq` 子串）。

---

## 综合判断

1. **最该优先处理的问题**：`matcher.match()` 默认 `limit=10` 导致 `file_candidates` 被截断到 50 条，这对需要多角色文件（expression + clinical + metainfo）的 pipeline 是致命的。即使数据齐全的 study，也可能因为 Top-50 被某种文件类型占满而误判为不可行。建议把 feasibility 评估改到“按 study 聚合全部文件”之后，而不是在截断后的列表上做。

2. **零覆盖 pipeline 是真的没数据**：`wgcna` / `immune_infiltration_iobr` / `her2_pfs_survival` 不是因为角色识别失败，而是因为 14 个 study 中没有任何一个同时提供表达矩阵 + 临床表 + 样本信息表。

3. **数据质量清单优先修**：`HRA000321 Matrix-h5` 被标为 `maf` 导致 `wes_somatic_maf_landscape` 误判，应优先纠正。多个 `Fusion`、`BAM` 目录被标为 `maf` 也是隐患。

4. **HRA000021 BAM 阶段仍不明**：平均 102 GB 的 WGS BAM 既可能是原始比对 BAM，也可能是排序去重后 BAM。在缺少 index、README 或命名标记前，不要基于“已排序去重”假设支持 BAM 入口。

5. **fastqc → fastp 边需要人工定语义**：加边技术上简单（order 边即可），但目录里已有 `fastp → fastqc` data 边，双向共存会误导 LLM。建议同时审视 QC/修剪的先后约定。

6. **一个我没问到但重要的边界**：`HRA000122` 的 696 个 FASTQ 完全在系统视野外（只在 T11）。这是比 HRA000021 BAM 更容易捡回来的数据——只要把 T11 中未被 T1 覆盖的 study 纳入匹配，立刻多一个 study 可跑 RNA-seq 上游流程。
