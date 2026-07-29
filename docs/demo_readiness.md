# 演示前修复报告

## 任务 1：配对 WES 阻断理由稳定性

### 诊断

查询："我有肿瘤和正常配对的 WES FASTQ，想做体细胞变异检测并注释"

修复前连续运行 10 次（检查字段为 `workflow_plan.validation.decomposition_gaps`）:

| 运行 | gaps 数量 | 状态 | 说明 |
|------|----------|------|------|
| 1 | 1 | no_match/no_match | LLM 生成 gap |
| 2 | 1 | no_match/no_match | LLM 生成 gap |
| 3 | 1 | no_match/no_match | LLM 生成 gap |
| 4 | 2 | no_match/no_match | LLM 生成 2 个 gap |
| 5 | 1 | no_match/no_match | LLM 生成 gap |
| 6 | 1 | no_match/no_match | LLM 生成 gap |
| 7 | 1 | no_match/no_match | LLM 生成 gap |
| 8 | 1 | no_match/no_match | LLM 生成 gap |
| 9 | 1 | no_match/no_match | LLM 生成 gap |
| 10 | 1 | no_match/no_match | LLM 生成 gap |

**结论：10/10 非空。** 之前观察到 `decomposition_gaps` 为空是因为检查的是 `workflow_plan.decomposition_gaps`（该字段不存在，始终为空），实际值存储在 `workflow_plan.validation.decomposition_gaps` 中。

### 修复方案

在 `workflow_composer.py` 中增加代码层兜底：

- `workflow_composer.py:803-823`：当 stage-two 返回 `steps == []` 且 `decomposition_gaps == []` 时，先重试一次 stage-two；若仍为空，则基于目录事实生成 gap。
- `workflow_composer.py:845-918`：新增 `_request_implies_pairing` 和 `_generate_fallback_gaps`。
  - 不硬编码具体工具名。
  - 先从参考 recipe 中检测汇合步骤；无 recipe 时，扫描 atomic tools 中可能是配对汇合点的工具（通过 description/name 中的变异/体细胞等关键词）。
  - 对只有一个样本级输入槽的候选工具生成："配对样本汇合无法表达:<tool_id> 在当前目录中只注册了 1 个 <slot> 输入槽,无法同时接收 tumor_<slot>, normal_<slot>。需要为该工具补充分样本输入槽。"

### 修复后 10 次结果

10/10 有非空 `validation.decomposition_gaps`，状态稳定为 `no_match/no_match`。

波动点：LLM 有时自己生成 1 个 gap，有时生成 2 个 gap；当 LLM 未生成时由代码兜底生成 1 个。核心信息（gatk 输入槽不足）始终存在。

---

## 任务 2：端到端 assay 校验核对

### 方法

重新运行六条查询，检查 `agent_input.study_accession` 和 asset 的 `strategy` 字段。由于当前 asset 结构未透传 `strategy`，改为同时检查 `router.route` 原始返回的 feasibility 与 `composer.plan` 最终返回的 feasibility。

### 核对表

| 查询 | 模式 | 绑定 study | study 实际 strategy | 期望 assay | composer feasibility | router feasibility | 是否符合 |
|------|------|-----------|---------------------|-----------|----------------------|--------------------|----------|
| 配对 WES | custom | HRA000071 | WES | WES | ready | ready | 数据 assay 符合，但目录结构阻断 |
| trim_to_fastp | custom | HRA000071 | WES | RNA-Seq | ready | ready | ❌ assay 不符 |
| RNA-seq 上游 | standard | HRA000071 | WES | RNA-Seq | ready | partial | ❌ assay 不符，composer 覆盖了 router 的 partial |
| TPM 聚类 | standard | HRA000074 | RNA-Seq | N/A | missing_assets | missing_assets | 类型不匹配（TPM vs count） |
| GO+KEGG | standard | HRA000074 | RNA-Seq | N/A | ready/不稳定 | ready/不稳定 | 矩阵类型符合 |
| 单样本 WES | custom | HRA000071 | WES | WES | ready | ready | 数据 assay 符合，但目录结构阻断 |

### 关键发现

**assay 校验没有端到端覆盖 composer 路径。**

- `pipeline_router.assess_feasibility` 已按 `DATA_PROFILE_TEMPLATES[pipeline].strategies` 校验 strategy；当 FASTQ strategy 不在允许集合内时，router 返回 `feasibility.status = 'partial'`，消息为"需要 RNA-Seq 测序数据，当前匹配到的 FASTQ 为 WES，无法直接使用"。
- 但 `WorkflowComposer._apply_agent_contract`（`workflow_composer.py:1837`）会重新计算 feasibility，只检查 `tool_chain` 是否完整、`missing_assets` 是否为空，**不继承 router 的 assay_blocked 状态**。
- 因此 RNA-seq 类查询（trim_to_fastp、rnaseq_upstream）虽然匹配到 WES 数据，最终仍报 `ready`。

### 影响

- 演示查询 2/3 目前绑定 HRA000071（WES），这是 assay 错配。
- 若现场演示，需说明："当前系统选中了 WES 数据来跑 RNA-seq 流程，这是已知缺口；router 层已识别为 partial，但 composer 层未透传。"

---

## 任务 3：查询 7 修复（MultiQC 退出 + fastqc→fastp 边）

### 改动 diff

1. `data/csv/relations/tool_relationship.csv:15`
   - 新增：`T02,T01,order,,`（fastqc → fastp，order 边）
2. `workflow_composer.py:736-740`
   - stage-two prompt 增加 MultiQC 说明：MultiQC 不在原子工具菜单中，由执行端无条件运行，不要出现在 steps 里。
3. `workflow_composer.py:1024-1027`
   - `_method_menu_lines` 中跳过 `tool_id == "multiqc"`，LLM 在 custom 组链时看不见 multiqc。
4. `workflow_composer.py:845-918`
   - 新增 `_request_implies_pairing` 和 `_generate_fallback_gaps`（任务 1 共用）。

### CSV 校验

```text
CSV validation passed. All files, columns, and relations are consistent.
```

### Neo4j sync

#### dry-run 输出摘要

```json
{
  "mode": "dry-run",
  "next_count": 14,
  "next": [
    ...,
    {"from_catalog_id": "T02", "to_catalog_id": "T01", "kind": "order", "output": "", "input": ""}
  ]
}
```

即：在原有 13 条边基础上新增 `fastqc → fastp` order 边。

#### 备份

- 文件：`docs/next_edges_backup_before_query7_fix.json`
- 备份时边数：13 条

#### apply 输出

```json
{
  "mode": "apply-next",
  "next_count": 14,
  "database": {
    "catalog_tools": 24,
    "next_count": 14,
    "self_loops": 0
  }
}
```

#### 回滚命令

```bash
cd /Users/zhouyiran/Documents/可选/bio-pipeline-kg-matcher
# 1. 还原 CSV（从备份或 git 检出 tool_relationship.csv 中 T02,T01,order,, 之前的状态）
# 2. 重新 apply
.venv/bin/python scripts/python/sync_neo4j_tool_catalog.py --apply
```

该脚本只增删 `source='curated-next-csv'` 的 `NEXT` 边，不碰工具节点和其他关系。

### 测试结果

```text
Ran 63 tests in 16.927s
OK (skipped=3)
```

### fastp ↔ fastqc 双向边评估

当前边集同时存在：
- `fastp → fastqc`（data 边）：修剪后 reads 给 FastQC 做质控。
- `fastqc → fastp`（order 边）：先 QC 再修剪。

这两条边方向相反但语义不矛盾：前者传数据，后者只表达顺序。菜单中同时出现双向边可能让 LLM 困惑，建议在人工确认后选择一种统一语义：
- 若坚持"先 QC 后修剪"：保留 `fastqc → fastp` order，把 `fastp → fastqc` 也改成 order 或删除。
- 若坚持"修剪后 QC"：保留 `fastp → fastqc` data，删除 `fastqc → fastp`。

本轮按用户授权只新增了 `fastqc → fastp` order，未动原有 `fastp → fastqc` data。

---

## 任务 4：演示物料

文件：`docs/demo_queries.json`

每条查询运行 3 次，记录完整输出并标注不稳定字段。

### 七条查询结果摘要

| 查询 | 模式 | 3 次状态 | 绑定 study | 不稳定字段 | 说明 |
|------|------|---------|-----------|-----------|------|
| 配对 WES | custom | no_match/no_match ×3 | HRA000071 | 无 | 目录结构阻断，gaps 稳定 |
| trim_to_fastp | custom | draft/draft ×3 | HRA000071 | 无 | 自定义链可组出 |
| RNA-seq 上游 | standard | ready/ready ×3 | HRA000071 | 无 | **assay 错配**（WES 当 RNA-Seq） |
| TPM 聚类 | standard | missing_assets/missing_data ×3 | HRA000074 | 无 | 类型不匹配，稳定阻断 |
| GO+KEGG | standard | ready/ready ×2, no_match/no_match ×1 | HRA000074 | selection_status, orchestration_status | LLM 对标准/自定义判断不稳定 |
| 单样本 WES | custom | draft/draft ×3 | HRA000071 | 无 | 自定义链可组出 |
| MAF 能力 | capability | information/information ×3 | N/A | 无 | 稳定 |

### 最不适合现场演示的查询

**GO+KEGG。**

原因：
- 3 次运行中有 1 次从 `ready` 变成 `no_match`。
- 根因是 LLM stage-one 对"想同时做 GO 和 KEGG 富集"的意图判断不稳定：有时认为标准 pipeline `diff_expr_go` 可以覆盖，有时认为需要自定义组链（因目录中缺少差异表达/富集原子工具而 gaps 非空）。
- 该波动来自 LLM 自身，不是数据或代码能完全消除的（除非改 prompt 或强制规则）。

建议：若演示 GO+KEGG，使用录制好的前两次 `ready` 输出，不要现场跑。

---

## 综合判断

1. **任务 1 基本达标**：阻断理由 10/10 非空，但内容仍有轻微 LLM 波动。兜底逻辑确保了核心信息不丢失。
2. **任务 2 暴露真实缺口**：assay 校验在 composer 层被覆盖，导致 RNA-seq 类查询绑定 WES 数据仍报 ready。这是演示时最大的科学准确性风险，建议在演示词中主动说明。
3. **任务 3 有效**：trim_to_fastp 从空 steps 变为稳定 draft；MultiQC 不再出现在 custom 菜单中。
4. **整体风险最高点**：`WorkflowComposer._apply_agent_contract` 重新计算 feasibility 时丢弃了 router 的 assay_blocked 状态。修复它需要把 router 的 feasibility 状态（或至少 assay_blocked 标志）透传到 contract 层，但这是行为变更，超出本轮"只读验证"范围，需单独一轮实施。
