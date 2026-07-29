# Round Report：MultiQC 退出 + NEXT 边迁移 + 目录补录提案

> 执行时间：2026-07-23
> 环境：`.venv`, Neo4j 在线
> 每完成一步均运行 `python -m unittest discover -s tests`

---

## 步骤 1：验证 pipeline_router.py:1035 FASTQ 过滤改动

### 结论

**这是修复，不是回归，保留。**

旧逻辑 `"fq" in format or "fastq" in files` 在当前 CSV 数据下会漏掉绝大多数 FASTQ：
- `T1.csv` 中 FASTQ 文件的 `format` 列为 `"Raw FASTQ"`（不含 `"fq"` 子串）
- 文件名多为 `.fq.gz`（不含 `"fastq"` 子串）

因此旧过滤对 `rnaseq_singletask` / `paired_fastq_to_unmapped_bam` / `cellranger_workflow` 的匹配结果为 **0 条 FASTQ**。

### 差异清单

| 流程 | 旧过滤命中数 | 新过滤命中数 | 差异 |
|---|---|---|---|
| `rnaseq_singletask` | 0 | 1000 | `.fq.gz` + `Raw FASTQ` 格式现在被正确识别 |
| `paired_fastq_to_unmapped_bam` | 0 | 1000 | 同上 |
| `cellranger_workflow` | 0 | 1000 | 同上 |
| `wes_somatic_pair` | 1000 | 1000 | 无差异（该流程命中的是 `.fastq.gz` 文件名，旧过滤也能识别） |

### 改动位置

- `pipeline_router.py:1035`：`wes_somatic_pair` 分支内使用 `_role_of_file(f) == "fastq"`
- `pipeline_router.py:1054`：`rnaseq_singletask` / `paired_fastq_to_unmapped_bam` / `cellranger_workflow` 共用分支使用 `_role_of_file(f) == "fastq"`

**测试结果（步骤 1 后）**：`Ran 63 tests in 18.569s, OK (skipped=3)`

---

## 步骤 2：实施 MultiQC 退出 NEXT 边集

### 改动

- `data/csv/relations/tool_relationship.csv`：删除目标为 `T12` 的 8 条关系，剩余 13 条
- `tests/test_workflow_composer.py`：`test_custom_mode_validates_complete_rnaseq_atomic_chain` 移除 `multiqc` 步骤，预期工具列表改为 6 个

### 验证

```bash
.venv/bin/python scripts/python/validate_csv.py --project-root .
# CSV validation passed.

.venv/bin/python -m unittest discover -s tests
# Ran 63 tests in 18.875s, OK (skipped=3)
```

### 注意

此时 CSV 已改但 Neo4j 未同步，运行时目录仍是 21 条边。步骤 3 执行 `--apply` 后统一变为 13 条。

---

## 步骤 3：NEXT 边迁移（data / order 二分 + output/input 属性）

### 3.1 改动的文件与行号

| 文件 | 行号 | 改动 |
|---|---|---|
| `data/csv/relations/tool_relationship.csv` | 全表 | 增加 `kind`、`output`、`input` 列；13 条边按 data/order 填表 |
| `scripts/python/validate_csv.py` | `133` | `tool_relationship.csv` 必填列增加 `"kind"` |
| `scripts/python/sync_neo4j_tool_catalog.py` | `361-367` | `expected_next` 增加 `kind`、`output`、`input` |
| `scripts/python/sync_neo4j_tool_catalog.py` | `427-430` | `MERGE NEXT` 后 `SET r.kind/output/input` |
| `neo4j_observability.py` | `59-66` | `TOOL_NEXT_QUERY` 返回 `edge.kind/output/input` |
| `neo4j_observability.py` | `351-358` | `tool_catalog()` 构造 `next_edges` 时包含 `kind/output/input` |
| `workflow_composer.py` | `168-175` | `RegisteredMethodCatalog` 新增 `data_edges: Set[Tuple[str,str,str,str]]` |
| `workflow_composer.py` | `62-64` | 删除 `ARTIFACT_COMPATIBILITY` 常量 |
| `workflow_composer.py` | `1470-1485` | 删除 artifact 相等校验块 |
| `workflow_composer.py` | `1487` | `from` 校验改为查 `data_edges` 四元组 |
| `workflow_composer.py` | `871-889` | `_method_menu_lines` 改为分列 `data_next` / `order_next` |
| `tests/test_workflow_composer.py` | `310-314` | `test_custom_mode_rejects_transcriptome_bam_as_genomic_aligned_bam` 断言字符串同步更新 |

### 3.2 13 条边最终表

| source | target | kind | output | input |
|---|---|---|---|---|
| fastp | fastqc | data | clean_fastq_read | clean_fastq_read |
| fastp | bwa | data | clean_fastq_read | clean_fastq_read |
| fastp | star | data | clean_fastq_read | clean_fastq_read |
| fastqc | bwa | order | — | — |
| fastqc | trim_galore | order | — | — |
| bwa | samtools | data | aligned_bam | aligned_bam |
| samtools | gatk | data | sorted_dedup_bam | sorted_dedup_bam |
| samtools | featurecounts | data | sorted_dedup_bam | sorted_dedup_bam |
| gatk | bcftools | data | unfiltered_vcf | unfiltered_vcf |
| bcftools | snpeff | data | filtered_vcf | filtered_vcf |
| trim_galore | star | data | clean_fastq_read | clean_fastq_read |
| star | rsem | data | transcriptome_bam | transcriptome_bam |
| star | samtools | data | aligned_bam | aligned_bam |

### 3.3 sync 过程

**备份**：

```bash
# 已生成
# docs/next_edges_backup_before_migration.json
# 内容：迁移前 Neo4j 中 21 条 NEXT 边（kind/output/input 因旧边不存在而为 null）
```

**dry-run**：

```bash
.venv/bin/python scripts/python/sync_neo4j_tool_catalog.py
```

输出显示 `next_count: 13`，13 条边均携带 `kind`/`output`/`input`。

**apply**：

```bash
.venv/bin/python scripts/python/sync_neo4j_tool_catalog.py --apply
```

结果：

```json
{
  "mode": "apply-next",
  "tool_count": 24,
  "atomic_tool_count": 12,
  "pipeline_tool_count": 12,
  "task_pipeline_count": 1,
  "next_count": 13,
  "database": {
    "catalog_tools": 24,
    "next_count": 13,
    "self_loops": 0
  }
}
```

**回滚命令**：

```bash
# 1. 还原 CSV（从 git 或备份取回 21 条旧表）
# 2. 重新执行 apply
git checkout data/csv/relations/tool_relationship.csv
.venv/bin/python scripts/python/sync_neo4j_tool_catalog.py --apply
```

### 3.4 菜单字符数变化

| 状态 | 字符数 | 变化 |
|---|---|---|
| 改前 | 3017 | — |
| 改后 | 3323 | **+306** |

增长来自：
- `data_next=[...]` 比原 `allowed_next_tool_ids=[...]` 多了 output→input 描述；
- 拆分后重复出现 target 名（如 `fastp` 的 data_next 列出 `bwa(...), fastqc(...), star(...)`）。

### 3.5 全量测试结果（步骤 3 后）

```bash
.venv/bin/python -m unittest discover -s tests
# Ran 63 tests in 17.313s, OK (skipped=3)
```

### 3.6 六条真实 LLM 查询结果

完整输出已保存至 `docs/round_llm_queries.json`。摘要：

| # | 查询 | mode | pipeline_ids | validation | orchestration_ready | 备注 |
|---|---|---|---|---|---|---|
| 1 | 肿瘤/正常配对 WES FASTQ，体细胞变异检测并注释 | custom | — | ❌ | ❌ | LLM 未产生有效步骤，报“原子化拆解未完成” |
| 2 | RNA-seq 上游把 trim_galore 换成 fastp，其他不变 | custom | — | ❌ | ❌ | LLM 返回空 steps；**手动验证见下方** |
| 3 | 双端 FASTQ 做 RNA-seq 上游分析 | standard | rnaseq_singletask | ✅ | ✅ | internal_steps 仍为 7 步（含 multiqc，因保留节点） |
| 4 | TPM 矩阵做无监督聚类 | standard | rnaseq_unsupervised_cluster | ✅ | ❌ | feasibility.status = missing_assets（符合预期） |
| 5 | 同时做 GO 和 KEGG 富集 | standard | diff_expr_go + diff_expr_kegg | ✅ | ✅ | — |
| 6 | 一个样本的 WES FASTQ，变异检测和注释 | custom | — | ✅ | ❌ | 6 步链：fastp→bwa→samtools→gatk→bcftools→snpeff，**无 multiqc 也通过校验** |

**关于查询 2 的手动补充验证**：

用户问“去掉 multiqc 后链还完整吗”。由于 LLM 对查询 2 返回了空 steps，我手动构造了“fastqc → fastp → star → rsem/samtools → featurecounts”链并调用 `_validate_custom_steps`：

```python
steps = [
    {"step_id": "qc", "tool_id": "fastqc", ...},
    {"step_id": "trim", "tool_id": "fastp", "depends_on": ["qc"], ...},
    {"step_id": "align", "tool_id": "star", "inputs": {"clean_fastq_read": {"from": {"step_id": "trim", "output": "clean_fastq_read"}}, ...}},
    {"step_id": "quant", "tool_id": "rsem", "inputs": {"transcriptome_bam": {"from": {"step_id": "align", "output": "transcriptome_bam"}}, ...}},
    {"step_id": "bam", "tool_id": "samtools", "inputs": {"aligned_bam": {"from": {"step_id": "align", "output": "aligned_bam"}}}},
    {"step_id": "count", "tool_id": "featurecounts", "inputs": {"sorted_dedup_bam": {"from": {"step_id": "bam", "output": "sorted_dedup_bam"}}, ...}},
]
```

结果：

```text
validation ok: False
errors:
  - 'NEXT 不允许: fastqc -> fastp (qc -> trim)'
  - '第 2 步（trim）未与前序输出衔接：非首步必须至少有一个 from 或 depends_on'
```

**结论**：去掉 multiqc 本身不影响链的完整性（查询 6 的 6 步 WES 链已证明）。但“把 trim_galore 换成 fastp”需要一条 **fastqc → fastp** 的 order 边（或 data 边）才能通过 `_validate_custom_steps`。当前 13 条边里没有这条边，因此该修改目前不被支持。

---

## 步骤 4：目录补录提案

已输出 `docs/catalog_gap_proposal.md`。

### 核心结论

12 个 atomic tool 中，有 4 个工具的 QC/报告类输出未在目录中注册，导致通向 multiqc 的边只能判为 order：

| 工具 | 漏抄的输出 slot | 补录后可升级的边 |
|---|---|---|
| fastp | `html_report`、`json_report` | fastp→multiqc |
| SAMtools | `alignment_metrics` / `alignment_stats` | samtools→multiqc |
| SnpEff | `annotation_report` | snpeff→multiqc |
| Trim Galore | `trim_report` | trim_galore→multiqc |

另有 2 处待目录负责人确认：
- BCFtools 的 `tbi_index` 是否独立成 slot；
- SAMtools 的 `bai_index` 是否独立成 slot。

---

## 判断与风险

### 风险最高的步骤

**步骤 3 的 `sync_neo4j_tool_catalog.py --apply`**。

原因：
1. 它直接改写了 Neo4j 中所有 `source='curated-next-csv'` 的 NEXT 边；
2. 一旦 apply，所有运行时实例（包括测试、LLM 查询、下游执行端）立即看到 13 条边；
3. 回滚虽然可行（还原 CSV + 重跑 `--apply`），但生产环境中若有其他服务同时读取，会存在短暂不一致窗口。

本次已按用户要求先备份、再 dry-run、最后 apply，风险可控。

### 漏掉的边界情况

1. **`test_custom_mode_rejects_next_edge_not_in_neo4j` 的断言语义变化**：
   - 当前 MultiQC 节点仍保留，该测试仍报 `"NEXT 不允许: trim_galore -> multiqc"`；
   - 若未来连 MultiQC 节点一起删除，错误会变成 `"未知 tool_id: multiqc"`，测试断言需要再次更新。

2. **data_edges 四元组暴露的问题**：
   - 当前 `(source_tool, output, target_tool, input)` 足以精确描述一条 data 边；
   - 但未来若同一 `(source, target)` 之间需要多条 data 边（例如 star→multiqc 的 `alignment_report` 和 `qc_report`），四元组天然支持；
   - 真正可能暴露问题的是 **目录补录**：若补录后产生新 data 边，必须同步更新 `tool_relationship.csv` 并重新 sync，否则 data_edges 与 next_edges 会不一致。

3. **查询 2 的 fastqc→fastp 缺口**：
   - 这不是 multiqc 移除造成的，而是“替换 trim_galore 为 fastp”这个新需求本身需要的边；
   - 如果这是业务上要支持的修改，需要在 NEXT 边集中新增一条 `fastqc → fastp` 的 order 边（或 data 边，如果 fastqc 的报告输出被注册）。

4. **HRA000021 / HRA001748 的数据缺口**：
   - HRA000021 有规则但零 FASTQ（全是 BAM），`wes_somatic_pair` 当前不支持 BAM 入口；
   - HRA001748 只有 scRNA-Seq，没有 WES，跨 study 配对在 WES 场景下无法验证；
   - 真正能跑的配对 combo 为 **1055 对**（HRA000873 1015 + HRA006499 40）。

### data_edges 设计在实施中有没有问题

**没有问题，但有一个实现细节需要注意**：

- `RegisteredMethodCatalog` 从 Neo4j payload 构建 `data_edges` 时，只把 `kind == "data"` 且 `output` 和 `input` 都非空的边加入；
- 这要求 sync 脚本对 order 边写空字符串而不是 NULL，否则 `edge.output` 在 Neo4j 查询中可能不存在；
- sync 脚本已按要求 `SET r.output = $output, r.input = $input`，order 边传入空字符串，因此一致性有保障。

---

## 附录：最终测试基线

```bash
.venv/bin/python -m unittest discover -s tests
```

结果：

```text
Ran 63 tests in 17.313s
OK (skipped=3)
```
