# 生信 Pipeline 仓库 Bug 审查报告

- **审查对象**：`incoming/bio_pipelines_repo/pipelines/` 下 14 个 pipeline
- **审查方式**：纯静态代码审查（阅读 + 推理），**全程只读，未修改任何文件**
- **审查日期**：2026-07-15
- **审查范围**：每个 pipeline 的 `.wdl` / `.R` / `input.json` / `example_inputs.json` / `option.json` / `knowledge_card.yaml` / `README.md` 全部文件

> ⚠️ 本报告仅供修复参考，**未对任何文件做改动**（同目录有 codex 在并行工作）。所有修复方案均为建议，落地前请结合实际镜像内的工具版本确认。

---

## 目录

1. [执行摘要](#执行摘要)
2. [严重程度分级说明](#严重程度分级说明)
3. [Bug 总表](#bug-总表)
4. [致命 / 严重 Bug 详解（含修复）](#致命--严重-bug-详解含修复)
5. [中等 Bug 详解（含修复）](#中等-bug-详解含修复)
6. [轻微 Bug 与文档漂移](#轻微-bug-与文档漂移)
7. [体检合格的 Pipeline](#体检合格的-pipeline)
8. [审查盲区与前置确认项](#审查盲区与前置确认项)
9. [推荐修复优先级](#推荐修复优先级)

---

## 执行摘要

一句话结论：**没有任何一个流程被埋了"方向反了"的暗雷**——上下调方向、log2FC 符号、Cox HR 方向、KM 分组、卡方列联表行列、Top N 排序、Tumor/Normal 接线，这些生信流程里最容易翻车的地方**全部正确**。

真正的问题集中在三类：

| 类别 | 数量 | 特征 |
|------|------|------|
| **一跑就废 / 静默污染** | 3 | 命令行参数过时、示例数据填错，会导致任务直接失败或产出错误数据且不报错 |
| **"优雅降级"反而崩溃** | 3 | 边界分支想温柔退场，却漏写 WDL 声明的必需输出文件，触发即 task 失败 |
| **科学口径悄悄错** | 7 | 不报错，但会让统计/生物学结论偏移（未校正 p、Silent 未过滤、事件解析顺序、阈值过松等） |

另有一批**镜像 tag / 文档 / 占位符**层面的不一致（几乎每个流程都有），不影响功能但影响可维护性。

**5 个流程逻辑层面零缺陷**：`rnaseq_unsupervised_cluster`、`wgcna`、`immune_infiltration_iobr`（核心逻辑）、`wes_somatic_maf_landscape`、`driver_gene_gender_analysis`。

---

## 严重程度分级说明

| 级别 | 含义 | 判定标准 |
|------|------|----------|
| 🔴 **致命** | 流程无法运行 | 每次运行必然失败，产不出结果 |
| 🟠 **严重** | 特定条件下失败 / 静默产出错误数据 | 某类输入下崩溃，或结果错误但不报错 |
| 🟡 **中等** | 结果偏移 / 科学口径存疑 | 能跑通，但统计或生物学结论可能不可靠 |
| ⚪ **轻微** | 健壮性 / 文档 / 可复现性 | 不影响当前正确性，影响可维护性或边缘场景 |

---

## Bug 总表

| # | Pipeline | 文件:行 | 级别 | 一句话 |
|---|----------|---------|------|--------|
| 1 | cellranger_workflow | `cellranger_workflow.wdl:132` | 🔴 致命 | `--create-bam=true` 硬编码，与版本 & `--no-bam` 分支冲突 |
| 2 | wes_somatic_pair | `wes_somatic_pair.wdl:258` | 🔴 致命 | Mutect2 用了 GATK 4.1 已移除的 `--tumor-sample` |
| 3 | paired_fastq_to_unmapped_bam | `example_inputs.json:5` | 🟠 严重 | 示例 `fastq_2` 填成 R1 路径，生成错误配对 uBAM |
| 4 | rnaseq_singletask | `rnaseq_singletask.wdl:122,249` | 🟠 严重 | 单端 Trim Galore 输出名匹配错，单端功能已损坏 |
| 5 | rnaseq_singletask | `rnaseq_singletask.wdl:148-158` | 🟠 严重 | `UNMAPPED_R2` 无条件赋值使 `:+` 守卫失效（单端） |
| 6 | survival_analysis | `cox_regression.R:91-131` | 🟠 严重 | 退化分支漏写 `cox_results_summary.txt`，连累下游 |
| 7 | survival_analysis | `summarize_results.R:47` | 🟠 严重 | `if(P_value < 0.05)` 遇 `NA` 直接崩溃 |
| 8 | her2_pfs_survival | `her2_pfs_survival.R:460-481` | 🟠 严重 | 单组分支漏写 summary/qc 三件套输出 |
| 9 | rnaseq_singletask | `rnaseq_singletask.wdl:243` | 🟡 中等 | `continueOnReturnCode: true` 掩盖所有命令失败 |
| 10 | diff_expr_go / kegg | `diff_expr_*.R` | 🟡 中等 | 默认用未校正原始 p 值筛差异基因 |
| 11 | diff_expr_kegg | `diff_expr_kegg.R:247` | 🟡 中等 | 名为 KEGG 实为 Reactome |
| 12 | survival_analysis | `extract_mutation.R:134` | 🟡 中等 | 突变判定不过滤 Variant_Classification（Silent 也算） |
| 13 | her2_pfs_survival | `her2_pfs_survival.R:137-144` | 🟡 中等 | 事件解析顺序错，"non-progression" 被判为事件 |
| 14 | tmb_survival_analysis | `tmb_survival_analysis.wdl:9` | 🟡 中等 | SNV 过滤与 indel 类别互斥，indel 静默漏计 |
| 15 | immune_infiltration_iobr | `immune_infiltration_iobr.R:933` | 🟡 中等 | CIBERSORT 可靠性阈值 `p<0.3` 过松（常规 0.05） |
| 16 | survival_analysis | `survival_analysis.R:34-63` | 🟡 中等 | 时间/状态列灵活匹配可能选到 OS 却标注 PFS |
| 17 | cellranger_workflow | `cellranger_workflow.wdl:192` | 🟡 中等 | BAM 输出名在 8.0 下不符（条件性） |
| 18+ | 多个 | 见下文 | ⚪ 轻微 | 镜像 tag / 文档漂移 / 占位符 / 可复现性等 |

---

## 致命 / 严重 Bug 详解（含修复）

### 🔴 Bug 1 — cellranger `--create-bam` 硬编码，与版本及 `--no-bam` 三者冲突

- **位置**：`cellranger_workflow/cellranger_workflow.wdl:132`（与 `:148-150`、`:60`、README 声明的 7.1.0 冲突）
- **级别**：🔴 致命（按声明的 7.1.0）/ 🟠 严重（若镜像实为 8.0）

**现象**：
```bash
CMD="cellranger count \
    --id=~{sample_id} \
    --create-bam=true \        # ← :132 硬编码写死
    ...
if [ "~{no_bam}" == "true" ]; then
    CMD="${CMD} --no-bam"      # ← :148-150 又追加 --no-bam
fi
```

**根因**：`--create-bam` 是 **Cell Ranger 8.0** 才引入并强制的参数；7.x 用的是 `--no-bam`（默认产 BAM）。两套参数体系被混在一起，且流程 `:60` 声明 `pipeline_version="7.1.0"`。

**影响**：
- 若镜像确为 **7.1.0**：`cellranger count` 遇到未知参数 `--create-bam` **每次运行都直接报错**，一个细胞都数不出来。
- 若镜像实为 **8.0**：`--create-bam=true` 恒为真，使 `no_bam` 输入**完全失效**（永远产 BAM）；且 `no_bam=true` 时追加的 `--no-bam` 在 8.0 又是未知参数，反而报错。

**修复方案**（二选一，取决于镜像真实版本）：

*方案 A — 镜像是 7.x*：删除 `:132` 的 `--create-bam=true` 行，保留 `:148-150` 的 `--no-bam` 分支即可：
```bash
CMD="cellranger count \
    --id=~{sample_id} \
    --fastqs=fastq_files \
    ...
# --no-bam 分支保持不变
```

*方案 B — 镜像是 8.0*：删除 `:148-150` 的 `--no-bam` 分支，把 `--create-bam` 改为受 `no_bam` 控制：
```bash
CREATE_BAM=true
if [ "~{no_bam}" == "true" ]; then CREATE_BAM=false; fi
CMD="cellranger count \
    --id=~{sample_id} \
    --create-bam=${CREATE_BAM} \
    ..."
```
并同步修复 Bug 17（BAM 输出名）。

---

### 🔴 Bug 2 — Mutect2 使用 GATK 4.1 已移除的 `--tumor-sample`

- **位置**：`wes_somatic_pair/wes_somatic_pair.wdl:258`
- **级别**：🔴 致命

**现象**：
```bash
gatk ... Mutect2 \
    -R ~{ref_path} \
    -I tumor.bam \
    -I normal.bam \
    --tumor-sample ~{tumor_id} \      # ← :258 该参数 GATK 4.1 起已删除
    --normal-sample ~{normal_id} \
    ...
```

**根因**：`--tumor-sample` 在 GATK 4.1 起被移除（Mutect2 会自动从 BAM 的 `@RG SM` 推断 tumor sample，只需显式指定 normal）。而 README 声明镜像为 GATK **4.5.0.0**。

**影响**：Barclay 命令行解析器会直接拒绝未知参数，报 `Invalid argument '--tumor-sample'` 并退出，**整个变异检测步骤失败，产不出任何 VCF**。

**✅ 好消息**：tumor/normal 的赋值本身**完全正确**，没有接反——`--normal-sample` 传的是 `normal_id`，normal BAM 的 `@RG SM` 标签在 PreprocessNormal 里正是 `normal_id`（`:44-46`、`:163` 的 `SM:~{sample_id}`），两者匹配。R1/R2 顺序、PoN/germline/interval、GetPileupSummaries → CalculateContamination → FilterMutectCalls 的接线（`:274-312`）全部正确。

**修复方案**：删除 `:258` 一行即可，其余不动：
```bash
gatk ... Mutect2 \
    -R ~{ref_path} \
    -I tumor.bam \
    -I normal.bam \
    --normal-sample ~{normal_id} \    # 只保留 normal，tumor 自动推断
    -L ~{interval_list} \
    ...
```

---

### 🟠 Bug 3 — 示例 `fastq_2` 指向 R1 文件，生成错误配对 uBAM

- **位置**：`paired_fastq_to_unmapped_bam/example_inputs.json:5`
- **级别**：🟠 严重

**现象**：
```json
"fastq_1": ".../NVM0598_R1.clean.clean.fastq.gz",
"fastq_2": ".../NVM0598_R1.clean.clean.fastq.gz",   // ← 应为 _R2
```

**根因**：`fastq_2` 复制粘贴了 `fastq_1` 的 R1 路径，未替换为 R2。（另外 `.clean.clean` 双后缀也可疑，疑似重复处理。）

**影响**：FastqToSam 会把 R1 同时当 read1 和 read2（因读名/读数一致**不会报错**），生成的 uBAM 中 read2 序列等于 read1——**静默数据污染**。用户照搬此示例会得到错误的配对数据，且下游比对无从察觉。

**修复方案**：把 `fastq_2` 改为真实的 R2 路径：
```json
"fastq_1": ".../NVM0598_R1.clean.fastq.gz",
"fastq_2": ".../NVM0598_R2.clean.fastq.gz",
```
（WDL 本体是成熟的 Broad 标准流程，FastqToSam 的 `--FASTQ`/`--FASTQ2`/`READ_GROUP_NAME`/`SAMPLE_NAME` 等参数齐全正确，无需改动。）

---

### 🟠 Bug 4 — 单端 Trim Galore 输出名匹配错，单端功能已损坏

- **位置**：`rnaseq_singletask/rnaseq_singletask.wdl:122`（另见 `:249`、`:250`）
- **级别**：🟠 严重（对单端输入为致命）

**现象**：
```bash
# :114-118 单端走 else 分支，不带 --paired
else
    $TRIM_CMD ... ~{sample_r1} >> $LOG 2>&1
fi
# :122-123 却只按双端命名抓文件
TRIMMED_R1=$(ls trimmed/*_val_1.fq.gz 2>/dev/null | head -1)
TRIMMED_R2=$(ls trimmed/*_val_2.fq.gz 2>/dev/null | head -1)
```

**根因**：Trim Galore 双端模式产出 `*_val_1.fq.gz` / `*_val_2.fq.gz`，但**单端模式**（不带 `--paired`）产出的是 `<base>_trimmed.fq.gz`。WDL 全程只按双端命名抓取，单端时 `_val_1` 通配符匹配为空 → `TRIMMED_R1` 为空字符串。

**影响**：
- `:132` STAR `--readFilesIn $TRIMMED_R1` 变成空输入 → STAR 报错。
- `:249` `File trimmed_r1 = glob("trimmed/*_val_1.fq.gz")[0]` 对空数组取 `[0]` 抛 index out of bounds → 输出收集阶段失败。
- README / knowledge_card 均宣称"支持单端/双端自动识别"，**但单端实际会崩溃**，功能与文档不符。双端路径不受影响。

**修复方案**：单端分支补充 `*_trimmed.fq.gz` 探测：
```bash
if ~{is_paired}; then
    TRIMMED_R1=$(ls trimmed/*_val_1.fq.gz 2>/dev/null | head -1)
    TRIMMED_R2=$(ls trimmed/*_val_2.fq.gz 2>/dev/null | head -1)
else
    TRIMMED_R1=$(ls trimmed/*_trimmed.fq.gz 2>/dev/null | head -1)
    TRIMMED_R2=""
fi
```
输出声明 `:249-250` 也需按 `is_paired` 条件化（或改用可选输出）。

---

### 🟠 Bug 5 — `UNMAPPED_R2` 无条件赋值，`:+` 守卫失效（单端）

- **位置**：`rnaseq_singletask/rnaseq_singletask.wdl:148-149`（触发点 `:158`）
- **级别**：🟠 严重（对单端为致命）

**现象**：
```bash
# :141-144 只有双端才真正生成 R2 文件
if [ -f "rrna_removed/star_rrna_Unmapped.out.mate2" ]; then
    gzip -c ... > rrna_removed/unmapped.R2.fastq.gz
fi
# :148-149 却无条件赋值
UNMAPPED_R1="rrna_removed/unmapped.R1.fastq.gz"
UNMAPPED_R2="rrna_removed/unmapped.R2.fastq.gz"   # ← 恒非空
# :158 守卫因此恒展开
STAR ... --readFilesIn $UNMAPPED_R1 ${UNMAPPED_R2:+$UNMAPPED_R2} ...
```

**根因**：`UNMAPPED_R2` 被赋成非空字面量，使 `${UNMAPPED_R2:+...}` 恒展开。对比 `:132` 的 `${TRIMMED_R2:+...}`（`TRIMMED_R2` 来自 `ls` 可为空）逻辑是对的，`:158` 却因变量恒非空而失效。

**影响**：即便修好 Bug 4，单端在 Step 4 基因组比对仍会因传入不存在的第二个 mate 文件而失败。

**修复方案**：按文件是否存在条件赋值：
```bash
UNMAPPED_R1="rrna_removed/unmapped.R1.fastq.gz"
if [ -f "rrna_removed/unmapped.R2.fastq.gz" ]; then
    UNMAPPED_R2="rrna_removed/unmapped.R2.fastq.gz"
else
    UNMAPPED_R2=""
fi
```

---

### 🟠 Bug 6 — Cox 退化分支漏写 summary 文件，连累下游 task

- **位置**：`survival_analysis/cox_regression.R:91-106` 与 `:118-131`（配合 `survival_analysis.wdl:162-165`）
- **级别**：🟠 严重

**现象**：当只有单一 EGFR 组或模型不收敛时，脚本只写 `cox_results.txt` 就 `quit()`：
```r
write.table(results_empty, output_file, ...)   # 只写 cox_results.txt
quit(save="no", status=0)                        # 直接退出
# cox_results_summary.txt 只在正常路径 :194-195 才生成
```
而 WDL `:162-165` 声明 `File summary = "cox_results_summary.txt"` 是**必需输出**。

**影响**：Cromwell 收集 `CoxRegression.summary` 时文件不存在 → CoxRegression task 失败；下游 `SummarizeResults`（依赖该文件）也无法运行。本意"优雅处理边界情况"的分支反而让工作流崩溃。

**修复方案**：退化分支在 `quit()` 前补写占位 summary 文件：
```r
# 在两处 quit() 之前补上
writeLines(
  c("Cox regression skipped: insufficient groups or non-convergence.",
    "No hazard ratio estimated."),
  "cox_results_summary.txt"
)
quit(save="no", status=0)
```

---

### 🟠 Bug 7 — `summarize_results.R` 在 P 值为 NA 时崩溃

- **位置**：`survival_analysis/summarize_results.R:47`
- **级别**：🟠 严重

**现象**：
```r
if (logrank_data$P_value < 0.05) { ... }   # P_value 为 NA 时 → if(NA) 报错
```
`survival_analysis.R:102-108` 在单组时写出 `P_value = NA`，但 summarize 未做 `is.na()` 保护。

**影响**：`if(NA)` 直接抛 "missing value where TRUE/FALSE needed"，单组/退化队列下 `SummarizeResults` 失败，`final_summary.txt` 不生成。

**修复方案**：
```r
if (!is.na(logrank_data$P_value) && logrank_data$P_value < 0.05) {
    ...
} else {
    # NA 或不显著的处理分支
}
```

---

### 🟠 Bug 8 — her2 单组分支漏写多个 WDL 必需输出

- **位置**：`her2_pfs_survival/her2_pfs_survival.R:460-481`（配合 `her2_pfs_survival.wdl:64-66`）
- **级别**：🟠 严重

**现象**：当中位数分组后只剩一组（`n_groups < 2`）时，脚本只写 `logrank_statistics.tsv`（`:468`）+ KM 图就 `quit()`，**没写** `results_summary.txt`、`results_summary.json`、`qc_summary.tsv`（这些只在正常路径 `:620-637` 生成）。而 WDL `:64-66` 把它们声明为非 glob 的必需 `File` 输出。

**根因**：单组分支没有走 `write_warning_and_quit()`（后者才会写全套占位文件）。

**影响**：一旦命中单组分支，Cromwell 解析 `summary_txt` 等输出时文件缺失 → task 失败。又一个坏掉的"优雅降级"分支。

**修复方案**：让单组分支复用 `write_warning_and_quit()`，或在 `quit()` 前补齐三个占位文件：
```r
writeLines("HER2 PFS analysis skipped: only one group after median split.",
           "results_summary.txt")
jsonlite::write_json(list(status="skipped", reason="single_group"),
                     "results_summary.json", auto_unbox=TRUE)
write.table(qc_placeholder, "qc_summary.tsv", sep="\t", row.names=FALSE)
quit(save="no", status=0)
```

---

## 中等 Bug 详解（含修复）

### 🟡 Bug 9 — `continueOnReturnCode: true` 掩盖所有命令失败

- **位置**：`rnaseq_singletask/rnaseq_singletask.wdl:243`
- **级别**：🟡 中等

**现象**：任务对任何非零退出码都视为成功，只有当声明的 output 文件缺失时才失败。虽然命令块开头有 `set -e`，但 `continueOnReturnCode: true` 让 Cromwell 忽略非零码继续收集输出。

**影响**：STAR / RSEM / featureCounts 任一步失败都不会给出直观错误，只会以"缺输出"报错，且可能产出"看似成功实则不完整"的截断结果，排障困难。

**修复方案**：移除该行（恢复默认 `continueOnReturnCode: false`），或明确只允许特定退出码：
```
runtime {
    # 删除 continueOnReturnCode: true
    # 或改为 continueOnReturnCode: [0]
}
```

---

### 🟡 Bug 10 — diff_expr 默认用未校正原始 p 值筛差异基因

- **位置**：`diff_expr_go/diff_expr_go.R:18,22,160`、`diff_expr_kegg/diff_expr_kegg.R:156`
- **级别**：🟡 中等（已在 README 声明为有意）

**现象**：
```r
significant_mask <- differential_results$p_value < opt$alpha   # 用原始 p
# adjusted_p_value 已算出但默认不用于筛选
```
且 `--alpha` 的帮助文本写的是 "Adjusted p-value cutoff"，与实际作用于原始 p 的行为**自相矛盾**。go 版可通过 `--significance-column` 切换，但 WDL 未暴露该参数，实跑恒为原始 p；kegg 版则硬编码。

**影响**：在 4 vs 18 这类小样本比较下用未校正 `p<0.05` 选 DEG，假阳性偏高，进而污染 GO/Reactome 富集的输入基因集。

**修复方案**（若确实希望默认走多重校正）：
```r
# 默认改用 adjusted p
significant_mask <- differential_results$adjusted_p_value < opt$alpha
```
并同步修正 `--alpha` 帮助文本，或在 WDL 暴露 `significance-column` 供用户选择。

---

### 🟡 Bug 11 — diff_expr_kegg 名为 KEGG，实为 Reactome

- **位置**：`diff_expr_kegg/diff_expr_kegg.R:247`
- **级别**：🟡 中等（README 已声明为有意保留历史命名）

**现象**：
```r
enrichPathway(..., organism="human", readable=TRUE)   # ReactomePA，不是 KEGG
```
pipeline id / 文件名 / workflow 名均为 kegg，实际调用 `ReactomePA::enrichPathway`（Reactome 通路），而非 `clusterProfiler::enrichKEGG`。Dockerfile 里还装着从未使用的 clusterProfiler。

**影响**：若交付目标确实是 **KEGG 通路富集**，则产出的是 Reactome 通路，功能不符预期。（基因 ID 类型没问题，enrichPathway 需 Entrez，脚本已做 Ensembl→Entrez。）

**修复方案**：
- 若要 Reactome：把 pipeline 改名 / 更新文档，消除 KEGG 字样，移除无用的 clusterProfiler 依赖。
- 若要 KEGG：改用 `clusterProfiler::enrichKEGG(gene, organism="hsa", keyType="kegg")`，注意 KEGG 需要 Entrez ID。

---

### 🟡 Bug 12 — 突变判定不过滤 Variant_Classification，Silent 也算 Mutant

- **位置**：`survival_analysis/extract_mutation.R:134-139,169-172`
- **级别**：🟡 中等（生物学上偏严重）

**现象**：
```bash
awk '$1=="EGFR"{print}'    # 只按 Hugo_Symbol==EGFR，不看 Variant_Classification
```
随后 `distinct(Run_Accession) %>% mutate(EGFR_Status="Mutant")`，无分类过滤。任何 EGFR 行（含 Silent、Intron、3'/5'UTR、IGR、RNA）都会把样本标记为 Mutant。

**影响**：只带同义/非编码 EGFR 变异的样本被误判为 Mutant，污染突变组，使 KM/Cox 的组间比较产生偏倚。

**修复方案**：过滤掉 Silent 及非编码类别，只保留功能性突变：
```bash
awk -F'\t' '$1=="EGFR" && $9 != "Silent" && \
    $9 !~ /Intron|UTR|IGR|RNA|Flank/ {print}'
# 注意确认 Variant_Classification 的实际列号（这里假设为 $9）
```

---

### 🟡 Bug 13 — her2 事件解析顺序错，"non-progression" 被判为事件

- **位置**：`her2_pfs_survival/her2_pfs_survival.R:137-144`
- **级别**：🟡 中等

**现象**：
```r
# :139 先检 event（含 "progress"、"pd"）
if (any(grepl(pattern, tolower(x), fixed=TRUE))) return(1)   # event_terms
# :142 后检 censored（含 "non"）
if (...) return(0)                                            # censored_terms
```
对 "non-progression"、"Non-PD"、"no progression" 这类**删失**取值，`grepl("progress"/"pd", ...)` 会先命中并返回 1（事件），永远到不了删失判断。

**影响**：删失被反标成事件，log-rank / KM 的事件数与曲线失真。典型"删失当事件"错误。

**修复方案**：调整判定顺序——先排除删失关键词，再判事件；或用更精确的正则：
```r
xl <- tolower(x)
# 先判删失（更具体的否定形式优先）
if (grepl("non|no[ -]?prog|censor|alive|stable|complete|partial", xl)) return(0)
if (grepl("progress|relaps|recurr|\\bpd\\b|death|dead|event", xl)) return(1)
return(NA)
```

---

### 🟡 Bug 14 — TMB 的 SNV 过滤与 indel 类别互斥，indel 静默漏计

- **位置**：`tmb_survival_analysis/tmb_survival_analysis.wdl:9,106`；README 53-70 行
- **级别**：🟡 中等（需对照真实脚本确认，见盲区说明）

**现象**：默认 `nonsynonymous_classes_csv` 含 `Frame_Shift_Del/Ins`、`In_Frame_Del/Ins`（都是 indel），但 README 明确同时要求 `VARIANT_CLASS == "SNV"`。indel 行的 VARIANT_CLASS 不是 "SNV"，两条件相与 → 这 4 个 indel 类别**永远匹配不到**。

**影响**：TMB 只计 SNV 类的 Missense/Nonsense/Splice_Site 等，**系统性漏计所有 indel**，低估突变负荷；配置里列出的 indel 类别是"死规则"，具有误导性。

**修复方案**：明确 TMB 定义后二选一——
- 若 TMB 只算 SNV：从 `nonsynonymous_classes_csv` 删除 4 个 indel 类别，消除误导。
- 若 TMB 应含 indel：放宽 `VARIANT_CLASS` 条件（改为 `SNV, insertion, deletion` 或不限制），使 indel 类别生效。

> ⚠️ 注意：该流程核心 R 脚本未进仓库（见[盲区](#审查盲区与前置确认项)），此项基于 WDL + README 推断，需对照镜像内脚本确认。

---

### 🟡 Bug 15 — CIBERSORT 可靠性阈值 `p<0.3` 过松

- **位置**：`immune_infiltration_iobr/immune_infiltration_iobr.R:933`
- **级别**：🟡 中等（建议人工确认是否有意）

**现象**：
```r
reliable_sample = usable_for_analysis & !is.na(cibersort_p_value) &
                  cibersort_p_value < 0.3        # 常规应为 < 0.05
```

**影响**：CIBERSORT 经验 p 值 `<0.05` 才代表去卷积统计显著/可靠；`0.3` 会把 `p∈[0.05,0.3)` 的"拟合不显著"样本也判为可靠，稀释 reliable 样本集，进而影响 `immune_fraction_reliable`、堆叠图 / 箱线图 / 热图 / 相关性图，以及性别 Wilcoxon 的样本构成与结论。方向是对的（留低 p），只是尺子松了 6 倍。

**修复方案**：
```r
cibersort_p_value < 0.05   # 恢复常规阈值；或参数化让用户可配
```

---

### 🟡 Bug 16 — 时间/状态列灵活匹配可能选到 OS 却标注 PFS

- **位置**：`survival_analysis/survival_analysis.R:34-63`、`cox_regression.R:30-59`
- **级别**：🟡 中等

**现象**：候选名单里同时含 PFS / OS / DFS 及裸名 `Time` / `Status`。若临床表缺 PFS 列，会自动改用 `OS Time` / `OS Status`（甚至任意名为 `Status`/`Time` 的列），但所有图表标题 / 轴标签硬编码为 "PFS / Progression-Free Survival"（`:166-167`）。

**影响**：分析的实际终点与报告标注不一致（可能拿 OS 当 PFS 报告），且可能选中非生存含义的同名列。

**修复方案**：收紧候选名单优先级并记录实际选中的列；或把图表标题改为动态反映实际列名：
```r
# 记录并显示实际使用的列
message("Using time column: ", time_col, " | status column: ", status_col)
plot_title <- paste0("Survival by EGFR status (", time_col, ")")
```

---

### 🟡 Bug 17 — cellranger BAM 输出名在 8.0 下不符

- **位置**：`cellranger_workflow/cellranger_workflow.wdl:192`
- **级别**：🟡 中等（条件性，与 Bug 1 联动）

**现象**：
```
File? bam_file = "possorted_genome_bam.bam"
```
Cell Ranger 8.0 已将 BAM 更名为 `sample_alignments.bam`（7.x 才是 `possorted_genome_bam.bam`）。

**影响**：若镜像为 8.0，即便生成了 BAM，`bam_file` 也会因路径不存在而变为 null（`File?` 不报错，但**输出静默丢失**）。7.x 下正常。

**修复方案**：与 Bug 1 一并按版本确定。8.0 时改为：
```
File? bam_file = "sample_alignments.bam"
```

---

## 轻微 Bug 与文档漂移

这些不影响当前功能正确性，但影响可维护性、可复现性或边缘场景：

| Pipeline | 位置 | 问题 |
|----------|------|------|
| rnaseq_singletask | `.wdl:168` | `logs/` 目录在 `:176` 才创建，但 `:168` 已向其 `mv` 日志（被 `\|\| true` 吞掉，日志实际没移动） |
| rnaseq_singletask | `.wdl:72-75` | 目录型索引（STAR/RSEM index）声明为 `File`，在会真实拷贝的后端（云/容器）会失效 |
| rnaseq_singletask | `.wdl:20,214-216` | 镜像 `:latest` 未固定版本；featureCounts `-p` 语义在 subread 2.0.2+ 变化，计数可能静默翻倍 |
| rnaseq_unsupervised_cluster | `.wdl:14` vs `03_bootstrap_stability.R:292` | `min_samples_after_filter=3`，但 bootstrap 硬性要求 ≥5 样本，极小数据集会崩 |
| wgcna | `run_wgcna_analysis.R:443,522,529` | 二值性状 Gender 用 `bicor`，统计上不稳健（官方建议 Pearson） |
| immune_infiltration_iobr | `.R:739-752` | 三次 `left_join` 后未 `distinct`，1:多映射会重复计样本 |
| immune_infiltration_iobr | `.R:703-704` | 硬编码 sheet 名，命名稍异即被 tryCatch 静默捕获产出空结果 |
| immune_infiltration_iobr | 全脚本 | CIBERSORT perm 无 `set.seed`，配合 `p<0.3` 阈值使临界样本 reliable 状态在重复运行间翻转 |
| diff_expr_go | `.R:207` vs kegg `:193` | 背景基因阈值一个用 `>=` 一个用 `>`，两同源流程不统一 |
| survival_analysis | `her2_pfs_survival.R:173,203-204` | `missing_samples` 是恒为空的死代码 |
| her2_pfs_survival | `.R:137-138` | 事件词表缺 `deceased/died/expired/living/surviv`，相关患者被解析为 NA 丢弃 |
| wes_somatic_maf_landscape | `plot_maf_landscape.R:140-151` | oncoplot 传的 `titleText`/`sortByMutation`/`gene_mar` 依赖 maftools 版本，旧版可能报 unused argument |
| driver_gene_gender | 图表 `:391-396` | 显著性星号用原始 p（README 已声明，建议看 adj_p） |
| driver_gene_gender | `.R` | ~700 个 COSMIC 基因全进 BH 校正（含 p=1 的未突变基因），使 adj_p 偏保守 |
| paired_fastq_to_unmapped_bam | `example_inputs.json:12` | `make_fofn: "true"` 用字符串而非布尔 `true`，严格解析器可能失败 |
| paired_fastq_to_unmapped_bam | `option.json:8-11` | 输出目录为占位符 `"xxx"`，未替换直接跑会写到字面目录 |
| cellranger_workflow | `.wdl:148` | `[ ]` 内用 `==`（bash 可，POSIX sh 应为 `=`） |
| **镜像 tag 普遍漂移** | 多个 | `input.json` / `example_inputs.json` / `knowledge_card` / README 的 docker tag 几乎都对不齐（如 wes_somatic 5.5 vs 6.5、wgcna 1.0 vs 15.0、diff_expr_go 1.0 vs 3.0、cellranger、immune、driver_gender 等均有） |
| driver_gene_gender | `input.json` | 使用 Windows 路径 `d:\...` |

---

## 体检合格的 Pipeline

以下流程**核心逻辑经逐条核对，未发现会导致结果错误的 bug**（点名核对的"经典坑"全部正确）：

| Pipeline | 核对通过的关键点 |
|----------|------------------|
| **rnaseq_unsupervised_cluster** | HVG 选高变（非反选）、PCA 前标准化、BIC 取最小、bootstrap 重采样样本（非基因）、置换 p 值方向、随机种子齐全 |
| **wgcna** | 软阈值 signed R²、networkType/TOMType 一致、表达矩阵方向自动判定、模块颜色↔基因对应、hub 用 kME、模块-性状矩阵行列、去离群阈值方向 |
| **immune_infiltration_iobr** | TPM 线性值喂 CIBERSORT（无 log）、`arrays=FALSE→QN=FALSE`、perm 透传、输出列名健壮检测、join 链正确（唯一隐患是 Bug 15 的阈值） |
| **wes_somatic_maf_landscape** | 过滤方向、Top N `order(-MutFreq)` 降序、Silent 正确排除、列名一致 |
| **driver_gene_gender_analysis** | 卡方列联表 `byrow=TRUE` 行列对应、性别映射、突变率分母、`pivot_wider` 列名、方向符号、BH 校正、join 键链 |

此外，**所有流程的生存分析方向性均正确**：Cox HR 方向（`exp(coef)`，参考组设置）、KM 分组/事件计数/配色/图例、log-rank p 值（`1-pchisq`）、中位数分组方向、Winsorizing 边界——凡能读到源码的，全部核对无误，无 0/1 反转或高低组反了的硬错误。

---

## 审查盲区与前置确认项

修复落地前，以下几处**必须先确认**，因为结论依赖仓库外的信息：

1. **`tmb_survival_analysis` 的两个核心 R 脚本未进仓库**
   WDL 调用 `/opt/workflow/scripts/prepare_tmb_inputs.R` 与 `tmb_survival_analysis.R`，全仓库找不到，只存在于 Docker 镜像内。**TMB 的核心逻辑（SNV/非同义过滤、病人级去重、TMB=count/Mb、中位数分组方向、Vital Status→event 解析）无法静态审查**。Bug 14 基于 WDL + README 推断。→ **建议先把脚本纳入版本库再复审。**

2. **Cell Ranger 真实版本号**
   Bug 1、17 的修复方向完全取决于镜像内 Cell Ranger 是 7.x 还是 8.0。→ **先 `cellranger --version` 确认。**

3. **maftools 版本**
   `wes_somatic_maf_landscape` 的 oncoplot 参数是否被接受依赖版本。→ 对照镜像内 maftools 版本。

4. **subread 版本**
   `rnaseq_singletask` 的 featureCounts `-p` 语义在 2.0.2 前后不同。→ 因用 `:latest` 需确认实际拉取版本。

5. **SnpEff 染色体命名**（wes_somatic_pair）
   `GRCh38.105`（Ensembl 命名）vs 参考的 `chr1` 风格——SnpEff 5.2 会自动剥离 `chr` 前缀，**很可能非真 bug**，但建议实跑验证注释非空。

---

## 推荐修复优先级

### P0 — 阻断运行，必须先修
1. **Bug 1** cellranger `--create-bam` 三角冲突（先确认版本）
2. **Bug 2** wes_somatic_pair 删除 `--tumor-sample`（删一行即通）

### P1 — 特定输入下失败 / 静默污染
3. **Bug 3** paired_fastq 示例 `fastq_2` 改为 R2
4. **Bug 4 + 5** rnaseq_singletask 单端支持（若确实需要单端）
5. **Bug 6 + 7 + 8** 三个生存流程的"降级分支补齐输出 / NA 保护"

### P2 — 科学口径，影响结论可靠性
6. **Bug 12** survival EGFR 突变过滤 Silent
7. **Bug 13** her2 事件解析顺序
8. **Bug 14** TMB indel 漏计（需先入库脚本）
9. **Bug 15** immune CIBERSORT 阈值 `p<0.3`
10. **Bug 10 / 11 / 16** diff_expr 未校正 p / KEGG 命名 / 生存列匹配

### P3 — 健壮性 / 文档
11. **Bug 9** 移除 `continueOnReturnCode: true`
12. 统一各流程镜像 tag、清理占位符、修死代码

---

*报告完 — 全程只读审查，未改动 `bio_pipelines_repo` 内任何文件。*
