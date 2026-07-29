# LLM 识别逻辑重构交付报告

## 一、改动清单

### 1.1 代码改动（workflow_composer.py）

| 位置 | 改动内容 | 原因 |
|---|---|---|
| `_llm_decision` 构造 stage_two_user 处 | 把参考流程的 `internal_steps` 序列化后追加到 stage-two user prompt | 原 prompt 要求 LLM "列出参考流程全部步骤"，但 LLM 根本看不到步骤，导致替换类请求直接报 gap |
| `_standard_has_coverage_gap` (~L854) | 删除 `input_match == "mismatch"` 触发降级的分支 | 用户要求输入类型不匹配时仍走 standard，只在输出中标注 |
| `_custom_plan` (~L1339) | `decomposition_gaps` 同时接受 `str` 和 `dict`；字符串会被包装为 `{"message": ...}` | 新 prompt 要求 LLM 返回字符串 gap，原代码只保留 dict，导致 gap 被静默丢弃 |

### 1.2 Prompt 改动

#### stage-one（流程选择器，workflow_composer.py ~L383–L495）

主要新增/改写段落：

- **判定顺序第 2 条**：强调"组合多个 pipeline 是常态"。
- **pipeline_assessments 语义**：
  - 明确 `functional_coverage` 看是否完成核心任务，不因流程多做上游步骤而降级；
  - 明确 `output_match` 看产物是否包含用户目标产物；
  - 明确 `input_match = mismatch` 不单独触发降级。
- **常见组合示例**：对 GO+KEGG 组合加粗说明"不要纠结 diff_expr_kegg 内部用的是 Reactome 还是 KEGG 数据库"。
- **用户未明确数据类型**：判 `partial` 而非 `mismatch`。
- **输入类型不匹配**：仍放进 `pipeline_ids` 并诚实标注。

#### stage-two（组链器，workflow_composer.py ~L568–L694）

主要新增/改写段落：

- **无法组链时的处理**置顶：steps 为空时 gaps 必须非空。
- **以参考流程为基准**：
  - 告知参考流程原子步骤已附在用户消息末尾；
  - 要求尽量保持原顺序和连接，但若边缺失可合法调整相邻质控步骤顺序；
  - 所有分析步骤必须保留，不得省略。
- **样本维度**：配对流程硬性要求（单样本复制、同链传播、汇合点只一次、汇合槽不足则阻断）。
- **数据形态不可混淆**、**连接规则**、**decomposition_gaps**、**自检清单**等保留并细化。

---

## 二、stage-two 能否看到已匹配资产

**结论：不能。**

`_llm_decision` 传给 stage-two 的只有：

- 用户原始 `text`
- `reference_pipeline_ids`
- stage-one `reason`
- 参考流程的 `internal_steps`（本次新增）

`cohort_candidates` / `file_candidates` / `asset_id` 等资产匹配结果在 stage-two 不可见。因此样本链无法强制绑定不同 `asset_id`，只能依赖 `reason` 字段向执行端说明样本归属。

---

## 三、单元测试结果

```bash
.venv/bin/python -m unittest discover -s tests
```

结果：

```
Ran 63 tests in 15.987s
OK (skipped=3)
```

---

## 四、六条真实 LLM 查询验收结果

结果文件：`PROMPT_REWRITE_LLM_SAMPLES.json`

| 查询 | 期望 | 实际结果 | 达标 |
|---|---|---|---|
| 配对 WES 体细胞变异检测 | blocked + 非空 gaps | `custom` / `blocked_by_incomplete_method_decomposition`，`validation.decomposition_gaps` 指出 gatk 单 BAM 槽无法汇合 | ✅ |
| RNA-seq 上游 trim_galore 换 fastp | 完整链且校验通过 | `custom` / `draft_requires_pipeline_materialization`，7 步完整链，`validation.ok = True` | ✅ |
| 双端 FASTQ RNA-seq 上游 | standard / rnaseq_singletask | `standard` / `rnaseq_singletask`，`validation.ok = True` | ✅ |
| TPM 矩阵无监督聚类 | standard + input_match=mismatch | `standard` / `rnaseq_unsupervised_cluster`，`input_match: mismatch`，`functional_coverage: full` | ✅ |
| 同时 GO 和 KEGG 富集 | standard / [diff_expr_go, diff_expr_kegg] | `standard` / `[diff_expr_go, diff_expr_kegg]`，`validation.ok = True` | ✅ |
| 单样本 WES 变异检测 | 单链完整 draft | `custom` / `draft_requires_pipeline_materialization`，`validation.ok = True` | ✅ |

---

## 五、汇合工具输入槽表（用于讨论是否补槽）

| 工具 | 输入槽名 | artifact | required | 可接收数据形态 |
|---|---|---|---|---|
| **gatk** | genome_annotation | genome_annotation | 是 | bam/fasta/vcf |
| | sorted_dedup_bam | sorted_dedup_bam | 是 | vcf/fasta/bam |
| **bcftools** | unfiltered_vcf | unfiltered_vcf | 是 | vcf |
| **snpeff** | filtered_vcf | filtered_vcf | 是 | database/vcf |
| | genome_annotation | genome_annotation | 是 | database/vcf |

**结论**：`gatk` 只有一个 `sorted_dedup_bam` 输入槽，`bcftools` 只有一个 `unfiltered_vcf` 输入槽，`snpeff` 只有一个 `filtered_vcf` 输入槽。配对 tumor/normal WES 在 catalog 层面确实无法表达双样本汇合，必须走 honest block。

本次未改动 catalog。
