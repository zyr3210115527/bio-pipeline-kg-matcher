# 演示前紧急修复报告：assay 校验过度拦截

## 0. 问题概述

`docs/demo_facts.md` 此前报告 182 格真值表中只有 **5 格可行**、13 个 pipeline 零覆盖，并把它解释为“assay 校验生效后的期望去伪结果”。这个解释是错的——这是 **bug**。

三条证据：

1. 唯一“存活”的是 `paired_fastq_to_unmapped_bam`（允许 WES/WGS）。所有 RNA 类 pipeline 全灭。
2. 不可行理由里出现 `当前匹配到的 FASTQ 为 0, WES`。`0` 不在 T1 的 strategy 分布里，只出现在 `T11.csv` 的 `data_type` 列（1,650 条）。
3. `docs/demo_queries.json` 显示查询 3（RNA-seq 上游）返回 `standard/ready`，但同一份 `demo_facts.md` 却说 `rnaseq_singletask` 零覆盖——同一份演示材料自相矛盾。

根因：`scripts/gen_demo_facts.py` 的 `pipeline_coverage()` 直接读取原始 `T11.csv`，而 T11 的 assay 标注与 T1 不一致：

| 问题 | T1 (标准化后) | T11 (原始) |
|---|---|---|
| bulk RNA | `RNA-Seq` | `RNA-seq`（小写 s） |
| 单细胞 RNA | `scRNA-Seq` | `scRNA-seq`（小写 s） |
| 多值 | `WES` / `WGS` | `WES,RNA-seq`、`WGS,RNA-seq` |
| 垃圾值 | 无 | `0`、`#N/A` |

但真正的 bug 更简单：`scripts/gen_demo_facts.py` 的 `pipeline_coverage()` 直接读取原始 `T11.csv`，而 T11 的行缺少 `individual_accession`、`specimen_types` 等关键字段，且 assay 标注与 T1 不一致。这导致 `assess_feasibility` 拿到的是错误/不完整的数据，而不是运行时 `matcher.t1` 中的规范数据。

下文的验证（1.2、1.4）表明：**当前数据路径上归一化代码并未被触发**，它是一项防御性加固；真正让可行格从 5 恢复到 39 的改动是 `gen_demo_facts.py` 改用 `CsvKGDataMatcher.t1 + t2`。

| 问题 | T1 (标准化后) | T11 (原始) |
|---|---|---|
| bulk RNA | `RNA-Seq` | `RNA-seq`（小写 s） |
| 单细胞 RNA | `scRNA-Seq` | `scRNA-seq`（小写 s） |
| 多值 | `WES` / `WGS` | `WES,RNA-seq`、`WGS,RNA-seq` |
| 垃圾值 | 无 | `0`、`#N/A` |
| `individual_accession` | 有 | 无 |
| `specimen_types` | 有 | 无 |

---

## 任务 1：诊断

### 1.1 进入 `assess_feasibility` 之前的实际 strategy 分布

使用 `CsvKGDataMatcher` 合并后的记录（`matcher.t1 + matcher.t2`），FASTQ 文件的 assay 实际取值为：

| 原始值 | 数量 |
|---|---|
| `WES` | 8,922 |
| `RNA-Seq` | 3,028 |
| `scRNA-Seq` | 1,290 |
| `WGS` | 532 |

归一化后：

| 标准 token | 数量 |
|---|---|
| `wes` | 8,922 |
| `rnaseq` | 3,028 |
| `scrna` | 1,290 |
| `wgs` | 532 |

### 1.2 `_load_normalized_t1` 中 strategy 的来源

`pipeline_router.py:710/719`：

```python
"data_type": row.get("strategy") or legacy.get("data_type") or "",
...
"strategy": row.get("strategy") or legacy.get("data_type") or "",
```

- 优先取标准化 `T1.csv` 的 `strategy` 列。
- 当 T1 缺失时才回退到 T11 的 `data_type`。
- 因此运行时 `matcher.t1` 中的 assay 已经是 `RNA-Seq` / `scRNA-Seq` 等规范值；1.1 中归一化前后数量完全一致，说明当前路径上没有需要修正的 assay 词表。

### 1.3 各 FASTQ 类 pipeline 的允许集合

| pipeline | 允许 assay（原始） | 归一化 |
|---|---|---|
| `rnaseq_singletask` | `RNA-Seq` | `rnaseq` |
| `cellranger_workflow` | `scRNA-Seq` | `scrna` |
| `wes_somatic_pair` | `WES`, `WGS` | `wes`, `wgs` |
| `paired_fastq_to_unmapped_bam` | `WES`, `WGS` | `wes`, `wgs` |

### 1.4 允许集合 × 实际值 交叉表

| pipeline | 归一化允许 | 命中 token | 命中 FASTQ 数 |
|---|---|---|---|
| `rnaseq_singletask` | `rnaseq` | `rnaseq` | 3,028 |
| `cellranger_workflow` | `scrna` | `scrna` | 1,290 |
| `wes_somatic_pair` | `wes`, `wgs` | `wes`, `wgs` | 9,454 |
| `paired_fastq_to_unmapped_bam` | `wes`, `wgs` | `wes`, `wgs` | 9,454 |

交集全部非空。因此“5/182 可行”不是 `assess_feasibility` 本身在规范数据上判错了，而是 `gen_demo_facts.py` 喂给它的是原始 T11 数据。

---

## 任务 2：修复

### 2.1 修复原则

只修三类“表示不一致”，不放宽 assay 校验本意：

1. **归一化**：`RNA-Seq` / `RNA-seq` / `rnaseq` 视为同一；`scRNA-Seq` / `scRNA-seq` / `scrna` 视为同一。
2. **多值拆分**：`WES,RNA-seq` 拆成集合，任一命中即通过。
3. **垃圾值不计入**：`0`、`#N/A`、空串等视为“未标注”，按兼容处理；只有可识别且与允许集合冲突的值才触发 `assay_blocked`。

### 2.2 Diff

#### `pipeline_router.py`

- **新增归一化函数**：`pipeline_router.py:275-303`
  - `_ASSAY_SYNONYMS`
  - `_normalize_assay_tokens`
  - `_canonical_assay_set`

- **改造 `assess_feasibility` 的 assay 校验**：`pipeline_router.py:571-599`
  - 用 `_canonical_assay_set` 归一化允许集合。
  - 用 `_normalize_assay_tokens` 归一化每个 FASTQ 的 assay。
  - 支持多值交集判断。
  - `0` / `#N/A` / 空值按未知处理，不会导致误杀。

- **修复 `_match_files` 的 assay 错绑**：`pipeline_router.py:922-969`
  - 当请求带有 assay 策略且文件是 FASTQ 时，如果文件 assay 可识别但与允许集合无交集，直接排除。
  - 这样 RNA-seq 查询不会再把 `HRA000071` 的 WES FASTQ 当成候选。

- **配对查询优先选择有角色规则的 study**：`pipeline_router.py:923-924,969`
  - 对 `wes_somatic_pair` 或文本中明确含“配对/肿瘤+正常/paired tumor+normal”的查询，给可识别 `sample_role` 的文件额外 +2 分。
  - 这使“配对肿瘤正常 WES”查询从 `HRA000071` 改绑到 `HRA000873`。

### 2.3 关于 assay 归一化的实际效果

为验证“归一化代码是否真正修复了 5/182”，做了临时对照实验：

- **条件**：关闭归一化，用旧逻辑的逐字匹配，但输入改为 `matcher.t1 + matcher.t2`（规范数据）。
- **结果**：可行格数仍然是 **39/182**，与开启归一化一致。

结论：

1. 在当前数据路径上，assay 归一化是**防御性加固**，没有直接修复 5/182。
2. 真正修复 5/182 的是 `gen_demo_facts.py` 改用 `CsvKGDataMatcher` 提供的规范记录。
3. 归一化代码保留，因为一旦 T1 的 `strategy` 缺失并回退到 T11，它仍能避免大小写/多值/垃圾值导致的误杀。

- **移除 `_preferred_study_bonus`**：
  - 删除原 `pipeline_router.py:805-817` 的方法定义。
  - 删除原 `pipeline_router.py:949-952` 在 `_match_files` 中的调用。

#### `workflow_composer.py`

- **把 `decomposition_gaps` 暴露到 plan 顶层**：`workflow_composer.py:1558`
  - `_custom_plan` 返回的 `workflow_plan` 现在直接包含 `decomposition_gaps` 字段。
  - 解决此前 `plan.decomposition_gaps` 为 `None`、但 `plan.validation.decomposition_gaps` 有内容的矛盾。

#### `scripts/gen_demo_facts.py`

- **改用 `CsvKGDataMatcher` 合并后的记录**：`scripts/gen_demo_facts.py:119-127`
  - 原脚本直接读 `T11.csv`，丢失了 `individual_accession`、`specimen_types` 等由 `_load_normalized_t1` 补全的字段。
  - 现改为 `list(matcher.t1) + list(matcher.t2)`，wes_somatic_pair 等配对流程的可行性才被正确统计。

---

## 任务 3：`wes_somatic_pair` 零可行的根因

### 3.1 定位

修复前 `gen_demo_facts.py` 直接喂给 `assess_feasibility` 的是原始 T11 行，关键字段缺失：

| 字段 | T11 原始行 | 后果 |
|---|---|---|
| `individual_accession` | 不存在 | `_assess_wes_somatic_cases` 无法按个体分组 |
| `specimen_types` | 不存在 | `_sample_role` 对 `specimen_types` 规则的 study 全返回 `None` |

因此即使 `HRA000873` 有 4,060 个 WES FASTQ，也被判断为“无法推断肿瘤/正常角色”，导致 `wes_somatic_pair` 在全表上 0 可行。

### 3.2 修复后验证

| study | FASTQ 数 | 两侧都有角色的 individual 数 | 合格 case 数（单侧恰好 1 对） | `assess_feasibility` 结果 |
|---|---|---|---|---|
| `HRA000873` | 4,060 | 1,015 | 1,015 | ✅ 可行 |
| `HRA006499` | 1,526 | 42 | 13 | ✅ 可行 |
| `HRA000071` | 1,144 | 0 | 0 | ❌ 未登记角色规则 |
| `HRA001272` | 2,360 | 0 | 0 | ❌ 未登记角色规则 |

> 注：`HRA006499` 当前口径：42 个 individual 同时具有 tumor/normal 侧样本，经 `_paired_fastq_groups` 同源键聚合后，最终合格 case 为 **13**。演示材料中只引用 **13**。

---

## 任务 4：移除 `_preferred_study_bonus`

### 4.1 改动

- 删除 `pipeline_router.py` 中 `_preferred_study_bonus` 方法及其调用（见 2.2）。
- 全量 unittest 63 用例零回归（skipped=3）。

### 4.2 移除前后七条查询的 study 绑定

| 查询 | 移除前 study（旧 `demo_queries.json`） | 移除后 study（新 `demo_queries.json`） | 是否 assay 匹配 |
|---|---|---|---|
| 配对肿瘤正常 WES | `HRA000071`（WES） | `HRA000873`（WES） | ✅ |
| trim_to_fastp | `HRA000071`（WES） | `HRA000074`（RNA-Seq） | ✅ |
| 双端 FASTQ RNA-seq 上游 | `HRA000071`（WES） | `HRA000074`（RNA-Seq） | ✅ |
| TPM 聚类 | `HRA000074` | `HRA000074` | ✅ |
| GO+KEGG 富集 | `HRA000074` | `HRA000074` | ✅ |
| 单样本 WES FASTQ | `HRA000071` | `HRA000071` | ✅（但 study 元数据自相矛盾，仍建议避免演示） |
| MAF 能力 | N/A | N/A | N/A |

移除 `_preferred_study_bonus` 同时解决了两个问题：

1. 查询 1 从黑名单中移除，现在能稳定绑定到有角色规则的 `HRA000873`。
2. RNA-seq 类查询不再因为硬编码加分而错绑到 WES study。

---

## 任务 5：复测与交叉验证

### 5.1 全量测试

```bash
python -m unittest discover -s tests
```

结果：63 OK, skipped=3。零回归。

新增回归测试：`tests/test_workflow_composer.py:test_paired_wes_query_prefers_study_with_role_rules`，锁定“配对 WES 查询应绑定到已登记角色规则且有合格 case 的 study”这一行为（不锁具体分数）。

### 5.2 三个状态的 `demo_facts.md` 对照

三列用同一个脚本口径跑出：

- **① Round 3 assay 校验前**：`feasibility_truth_table.md` 的基线，当时 assay 校验尚未实施，系统靠角色/拓扑判断，存在 20 个 assay 假阳性。
- **② 本轮修复前**：`scripts/gen_demo_facts.py` 直接读原始 `T11.csv` + 旧版 `assess_feasibility` 逐字匹配，得到 5/182。
- **③ 本轮修复后**：`gen_demo_facts.py` 改用 `matcher.t1 + matcher.t2`，并保留 assay 归一化，得到 39/182。

| pipeline | ① Round 3 前 | ② 本轮修复前 | ③ 本轮修复后 | 说明 |
|---|---|---|---|---|
| `cellranger_workflow` | 11 | 0 | 2 | ② 中 T11 的 `scRNA-seq` 被逐字匹配误杀；③ 用 T1 规范值后恢复 |
| `rnaseq_singletask` | 11 | 0 | 4 | ② 中 T11 的 `RNA-seq` 被逐字匹配误杀；③ 用 T1 规范值后恢复 |
| `wes_somatic_pair` | 2 | 0 | 2 | ② 中 T11 缺少 `individual_accession` / `specimen_types`，配对无法计算 |
| `paired_fastq_to_unmapped_bam` | 11 | 5 | 7 | ② 中多值 `WES,RNA-seq` 等无法命中；③ 用 T1 规范值/归一化后恢复 |
| `wes_somatic_maf_landscape` | 9 | 0 | 9 | ② 中 T11 没有 MAF 等 T2 文件 |
| `diff_expr_go` | 4 | 0 | 4 | ② 中 T11 没有表达矩阵等 T2 文件 |
| `diff_expr_kegg` | 4 | 0 | 4 | 同上 |
| `rnaseq_unsupervised_cluster` | 4 | 0 | 4 | 同上 |
| `survival_analysis` | 1 | 0 | 1 | 同上 |
| `tmb_survival_analysis` | 1 | 0 | 1 | 同上 |
| `driver_gene_gender_analysis` | 1 | 0 | 1 | 同上 |
| `her2_pfs_survival` | 0 | 0 | 0 | 真无数据 |
| `immune_infiltration_iobr` | 0 | 0 | 0 | 真无数据 |
| `wgcna` | 0 | 0 | 0 | 真无数据 |
| **合计** | **59** | **5** | **39** | ①→② 是 bug，②→③ 是修复 |

**结论**：标题“5 → 39”指的是 **②→③**；① 的 59 是 assay 校验实施前的过宽基线，不是同一口径。

### 5.3 `demo_queries.json` 与 `demo_facts.md` 交叉验证

| 查询 | workflow_mode | 绑定 study | study strategy | 与 `demo_facts` 覆盖率是否一致 |
|---|---|---|---|---|
| 配对肿瘤正常 WES | custom | `HRA000873` | WES | ✅ `wes_somatic_pair` 可行 |
| trim_to_fastp | custom | `HRA000074` | RNA-Seq | ✅ `rnaseq_singletask` 可行 |
| 双端 FASTQ RNA-seq 上游 | standard | `HRA000074` | RNA-Seq | ✅ `rnaseq_singletask` 可行 |
| TPM 聚类 | standard | `HRA000074` | transcriptomic | ✅ `rnaseq_unsupervised_cluster` 可行 |
| GO+KEGG 富集 | standard | `HRA000074` | transcriptomic | ✅ `diff_expr_go/kegg` 可行 |
| 单样本 WES FASTQ | custom | `HRA000071` | WES | ✅ `paired_fastq_to_unmapped_bam` 可行，但 study 元数据冲突 |
| MAF 能力 | capability | N/A | N/A | ✅ |

此前矛盾（查询 3 ready 但 `rnaseq_singletask` 零覆盖）已消除。

### 5.4 回放验证

```bash
python scripts/a4_verify_replay.py
```

结果：7/7 全部回放成功。

---

## 6. 判断：除 assay 外，还有哪些“词表不一致”风险

### 6.1 `format` 列

- `T11.format` 与 `T2.format` 是同一语义，但 T2 把目录条目标为 `dir`，T11 没有目录条目。
- 已知问题：`HRA000321 Matrix-h5` 被标为 `format=maf`，导致 `wes_somatic_maf_landscape` 误判；`HRA000074 BAM` 目录也被标为 `format=maf`。
- 这类问题已经在 `docs/round2_report.md` 中扫描过，属于 CSV 数据质量问题，**未在代码层自动拦截**。

### 6.2 `specimen_types`

- `sample.csv` 与 Neo4j `sample.specimen_types` 取值完全一致：`Patient Solid Tissue`、`Peritumoral`、`Blood`、`Organoid`、`Bone Marrow`。
- 没有发现大小写或多值不一致。

### 6.3 `sample_type`

- 存在多值混用分号：`Metastatic;Primary`、`Metastatic;Primary;Recurrent`、`Primary;Recurrent`。
- 当前代码未使用 `sample_type` 做角色判定，因此不是本轮风险。若未来要用，需先做多值拆分和归一化。

### 6.4 `tumor_type`

- 部分 study 的 `tumor_type` 与 query 中的癌种表述存在同义词问题（如 `Glioma` vs `胶质瘤`），已有 `DISEASE_ALIASES` 处理，不在本轮范围。

### 6.5 建议

最该优先处理的同类风险是 **format 标注错误**：它直接导致 MAF/突变类 pipeline 的假阳性，而且当前 `_role_of_file` 完全信任 `format` 列。可在代码层加一个轻量一致性检查（扩展名 vs format），但会改变匹配行为，需要人工确认后再实施。

### 6.5 `T2.strategy`

`T2.csv` 的 `strategy` 列取值分布：

| strategy | 数量 | 备注 |
|---|---|---|
| `genomic` | 48 | 多为 WES/WGS 相关的目录/MAF/VCF |
| `transcriptomic` | 24 | 多为表达矩阵（TPM/FPKM/counts） |
| `single-cell transcriptomic` | 3 | 单细胞表达相关 |
| `clinical` | 2 | 临床表型文件 |
| `HRA001748`、`HRA005191`、… | 各 1 | 明显是填错列的 study accession，共 7 条 |

当前 `T2.strategy` 仅用于 `_match_files` 的 substring 加分，**不参与 assay 校验**（assay 校验只看 FASTQ，而 T2 没有 FASTQ）。因此第五套词表暂时不会导致假阳性/假阴性，但若未来把 T2 矩阵也纳入 assay 校验，需要先清理这 7 条错填值并对 `genomic/transcriptomic` 做映射。

### 6.6 `sample_type`

- 存在多值混用分号：`Metastatic;Primary`、`Metastatic;Primary;Recurrent`、`Primary;Recurrent`。
- 当前代码未使用 `sample_type` 做角色判定，因此不是本轮风险。若未来要用，需先做多值拆分和归一化。

---

## 7. 改动清单速查

| 文件 | 行号 | 改动 |
|---|---|---|
| `pipeline_router.py` | 275-303 | 新增 assay 归一化辅助函数 |
| `pipeline_router.py` | 571-599 | `assess_feasibility` 改为归一化/多值/垃圾值兼容的 assay 校验 |
| `pipeline_router.py` | 922-969 | `_match_files` 增加 FASTQ assay 错绑过滤和配对查询角色加分 |
| `pipeline_router.py` | （原 805-817 / 949-952） | 删除 `_preferred_study_bonus` 方法及调用 |
| `workflow_composer.py` | 1558 | `_custom_plan` 的 plan 增加 `decomposition_gaps` 字段 |
| `scripts/gen_demo_facts.py` | 119-127 | `pipeline_coverage` 改用 `CsvKGDataMatcher.t1 + t2` |
| `docs/demo_facts.md` | 全量 | 重新生成，39/182 可行 |
| `docs/demo_queries.json` | 全量 | 重新录制，study 绑定与 assay 一致 |
| `demo/cassettes/` | 新增/覆盖 | 12 条有效磁带，回放 7/7 |
| `docs/demo_readiness_full.md` | D9/D10/D11 | 更新数字、黑名单、bonus 移除说明 |
