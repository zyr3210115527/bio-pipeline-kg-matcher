# Demo 开关 + MultiQC 孤儿修复报告

## 任务 1：暴露 `force_custom` 到接口层

### 改动清单

| 文件 | 行号 | 改动内容 |
|------|------|----------|
| `app.py` | 201-202 | 读取 `FORCE_CUSTOM` 环境变量，并从请求体解析 `force_custom`（bool，默认随环境变量） |
| `app.py` | 210-211 | 调用 `route_pipeline_request(..., force_custom=force_custom)`，并把值写回 `raw` |
| `app.py` | 140 | `_shape_case` 返回 `"force_custom": bool(raw.get("force_custom", False))`，供前端展示 |
| `server.py` | 168 | MCP `route_pipeline_request` 从 `arguments` 读取 `force_custom` |
| `server.py` | 169-174 | 透传给 `route_pipeline_request(..., force_custom)`，并写回结果 |
| `demo.html` | 525 | Vue `setup()` 中新增 `forceCustom` ref，默认 `false` |
| `demo.html` | 501 | 输入框旁增加 checkbox："强制自定义组链（跳过标准流程）" |
| `demo.html` | 623 | `submit()` 提交时携带 `{query, top_k:5, force_custom: forceCustom.value}` |
| `demo.html` | 338 | 结果卡片上增加 `<el-tag type="danger">强制 custom</el-tag>`，与 `workflow_mode` 标签并列 |

### demo.html 关键片段

输入框旁 checkbox（`demo.html:501`）：

```html
<div class="composer-note">
  <el-checkbox v-model="forceCustom" size="small">强制自定义组链（跳过标准流程）</el-checkbox>
  <span style="margin-left: 12px; color: #8a94a5;">标准流程保持 Neo4j 锁定 recipe 不变；自定义方法链必须通过 tool、slot 与 NEXT 校验。</span>
</div>
```

提交时携带参数（`demo.html:623`）：

```javascript
const response = await fetch('/api/ask', {
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({query:text, top_k:5, force_custom: forceCustom.value})
});
```

结果卡片标签（`demo.html:338`）：

```html
<el-tag size="small" type="danger" effect="plain" v-if="result.force_custom">强制 custom</el-tag>
```

### 说明

- 环境变量 `FORCE_CUSTOM=1/true/on` 可作为全局默认，行为与现有 `FORCE_RULE` 一致。
- HTTP、MCP、环境变量三处的默认值链：`req.force_custom` → `FORCE_CUSTOM` → `False`。
- `WorkflowComposer.plan(..., force_custom=bool)` 本身已存在并有测试锁定，本次只做了参数透传，未改动 `plan()` 内部逻辑。

---

## 任务 2：`force_custom=True` 的实际行为

### 2.1 stage-one 是否被完全跳过？

是。`_llm_decision` 在 `force_custom=True` 时直接构造 stage_one，不调用 LLM：

```python
# workflow_composer.py:508-522
if force_custom:
    stage_one = {
        "mode": "custom",
        "reason": "强制自助餐测试：跳过标准 pipeline 选择。",
        "pipeline_ids": [],
        "reference_pipeline_ids": [],
    }
    stage_one_metadata = {
        "used": True,
        "status": "ok",
        "model": None,
        "calls": 0,
        "stages": [],
        "force_custom": True,
    }
```

因此：
- `_pipeline_menu_lines()`（标准流程菜单）不会被喂给 stage-one LLM；
- stage-one LLM 不会被调用；
- `planner_metadata.calls` 在 stage-one 阶段为 `0`。

### 2.2 stage-two 收到的 `reference_pipeline_ids` 和 `reason` 是什么？

`reference_pipeline_ids` 为空列表 `[]`，`reason` 为 `"强制自助餐测试：跳过标准 pipeline 选择。"`。

### 2.3 "参考流程 internal_steps" 在 `force_custom` 下是否还会带上？

不会。`_custom_plan` 使用 `reference_pipeline_ids = stage_one.get("reference_pipeline_ids") or ...`。由于 force_custom 下该字段为 `[]`，`reference_recipes` 为空字典，传给 stage-two user prompt 的"参考流程原子步骤"也是 `[]`。

也就是说：force_custom 路径下，LLM 不会收到任何标准 recipe 作为基线，完全从零组链。

### 2.4 `test_force_custom_skips_standard_selection_call` 断言

```python
# tests/test_workflow_composer.py:686-705
self.assertEqual(call_llm.call_count, 1)
self.assertEqual(decision["mode"], "custom")
self.assertTrue(metadata["force_custom"])
self.assertEqual(metadata["calls"], 1)
```

该测试验证：
- 总共只发生 1 次 LLM 调用（stage-two 一次，stage-one 被跳过）；
- 决策模式为 `custom`；
- metadata 中 `force_custom=True`；
- metadata `calls` 为 1。

---

## 任务 3：改动前 10 次实测（`force_custom=True`，RNA-seq 上游查询）

### 查询

> 我有双端 FASTQ 想做 RNA-seq 上游分析,需要表达矩阵和基因计数

### 统计结果

| 指标 | 数值 |
|------|------|
| 总运行次数 | 10 |
| `validation_ok=True` | 10/10 |
| 包含 `multiqc` 步骤 | 0/10 |
| 状态 | 全部为 `draft/draft` |
| 步骤数分布 | 5 步（6 次）、6 步（1 次）、7 步（3 次） |

### 原始 10 次步骤列表

```json
[
  ["fastp","fastp"],["star","star"],["samtools","samtools"],["rsem","rsem"],["featurecounts","featurecounts"],
  ["fastp_trim","fastp"],["star_align","star"],["samtools_sort","samtools"],["featurecounts_count","featurecounts"],["rsem_quant","rsem"],
  ["fastqc_raw","fastqc"],["fastp","fastp"],["fastqc_clean","fastqc"],["star","star"],["rsem","rsem"],["samtools","samtools"],["featurecounts","featurecounts"],
  ["fastqc_raw","fastqc"],["fastp","fastp"],["fastqc_clean","fastqc"],["star","star"],["samtools","samtools"],["featurecounts","featurecounts"],["rsem","rsem"],
  ["fastp_step","fastp"],["star_step","star"],["rsem_step","rsem"],["samtools_step","samtools"],["featurecounts_step","featurecounts"],["fastqc_step","fastqc"],
  ["fastp","fastp"],["star","star"],["rsem","rsem"],["samtools","samtools"],["featurecounts","featurecounts"],
  ["step1_fastp","fastp"],["step2_star","star"],["step3_samtools","samtools"],["step4_rsem","rsem"],["step5_featurecounts","featurecounts"],
  ["step1_fastp","fastp"],["step2_star","star"],["step3_samtools","samtools"],["step4_rsem","rsem"],["step5_featurecounts","featurecounts"],
  ["fastp","fastp"],["star","star"],["samtools","samtools"],["rsem","rsem"],["featurecounts","featurecounts"],
  ["fastp","fastp"],["star","star"],["samtools","samtools"],["rsem","rsem"],["featurecounts","featurecounts"]
]
```

### 关键观察

**所有 10 次均通过校验，且没有一次生成 `multiqc`。**

> 基线验证方法：该进程在 `workflow_composer.py` 修改前（文件 mtime `21:21:48`，进程启动 `21:20:51`）已启动，因此读取的是修复前的代码版本。

这与直觉相反：改动前 `_method_menu_lines` 仍把 `multiqc` 列在菜单里，为什么 LLM 不选它？

原因是 `force_custom=True` 跳过了 stage-one，导致 stage-two **收不到任何参考流程**（`reference_pipeline_ids=[]`）。没有参考 recipe 的约束，LLM 从零组链，只需覆盖"表达矩阵 + 基因计数"目标产物即可；`multiqc` 本身不产生矩阵/计数，也没有下游工具消费它的输出，因此 LLM 没有动机把它加入主链。

**结论**：
- 对于"从零组链"型的 force_custom 查询，MultiQC 孤儿问题**并未暴露**；
- MultiQC 孤儿的阻塞场景是：stage-one 给出参考 recipe → recipe 里含 multiqc → prompt 要求"其余步骤原样保留" → LLM 被迫保留 multiqc → 边集又禁止 multiqc 入边 → 校验失败。
- `force_custom=True` 因为跳过 stage-one，反而绕过了这个死结。

---

## 任务 4：MultiQC 孤儿修复

### 改动清单

| 文件 | 行号 | 改动内容 |
|------|------|----------|
| `workflow_composer.py` | 1034-1037 | `_method_menu_lines()` 中跳过 `tool_id == "multiqc"`，stage-two 原子工具菜单从 12 个降到 11 个 |
| `workflow_composer.py` | 758-765 | 构造 `reference_recipes` 时过滤掉 `tool_id == "multiqc"` 的步骤 |
| `workflow_composer.py` | 622-627 | stage-two prompt 新增"MultiQC 与参考流程"小节，明确：MultiQC 由执行端无条件运行，不要出现在 steps 里；参考流程里的 multiqc 可直接跳过 |
| `workflow_composer.py` | 635-641 | 正确示例（trim_galore 换 fastp）中也去掉了 multiqc，并注释"MultiQC 报告由执行端自动产出" |

### 代码片段

**菜单过滤（`workflow_composer.py:1034-1037`）**：

```python
for method in self.registered_methods.capabilities():
    tool_id = method["tool_id"]
    # MultiQC is managed by the execution runtime as a final aggregation
    # step; it does not participate in custom chain composition.
    if tool_id == "multiqc":
        continue
```

**参考 recipe 过滤（`workflow_composer.py:758-765`）**：

```python
reference_recipes = {
    pipeline_id: [
        step for step in self._neo4j_pipeline_steps(pipeline_id)
        if step.get("tool_id") != "multiqc"
    ]
    for pipeline_id in reference_pipeline_ids
    if pipeline_id in self.registered_methods.pipeline_methods
}
```

**Prompt 约束（`workflow_composer.py:622-627`）**：

```markdown
### MultiQC 与参考流程

MultiQC 由执行端在流程结束时无条件运行,不需要编排。
**不要在 steps 里生成 multiqc 步骤**,也不要为它建立任何 from 或 depends_on。
如果参考流程的步骤列表里出现 multiqc,直接跳过它,这不算"改动了其他步骤"。
最终产物中的 MultiQC 报告由执行端自动产出,你只需组出到目标产物的主链。
```

### 设计说明

- **保留 multiqc 工具节点**：standard 模式的 7 步 `rnaseq_singletask` recipe 不变，`test_standard_rnaseq_recipe_uses_only_neo4j_tools` 不受影响（该测试验证的是标准 pipeline 的 HAS_STEP，不是 stage-two 菜单）。
- **只影响 custom 路径**：菜单过滤和参考 recipe 过滤只在 `_custom_plan` / `_method_menu_lines` 生效，standard 流程仍能看到 multiqc。
- **三处一起改**：只过滤菜单，LLM 仍可能从常识里加 multiqc；只改 prompt，LLM 仍可能从参考 recipe 里被迫保留；只过滤参考 recipe，菜单里还有 multiqc 会被选用。三处互相补强。

---

## 任务 5：复测与对照表

### 5.1 改动后 10 次实测（`force_custom=True`，同一 RNA-seq 查询）

| 指标 | 数值 |
|------|------|
| 总运行次数 | 10 |
| `validation_ok=True` | 9/10 |
| 包含 `multiqc` 步骤 | 0/10 |
| 状态 | 9 次 `draft/draft`，1 次 `no_match/no_match` |
| 步骤数分布 | 5 步（4 次）、6 步（5 次）、10 步（1 次，失败） |

**唯一失败（run 9）**：LLM 把"双端 FASTQ"误解为"两个样本"，生成了两条平行的 5 步链（fastp→star→samtools→featurecounts→rsem 各两份）。第 6 步（第二条链的首步）没有 `from`/`depends_on`，触发校验错误：

```
第 6 步（fastp_sample_2）未与前序输出衔接：非首步必须至少有一个 from 或 depends_on
```

这不是 MultiQC 修复引入的新问题，而是 force_custom 路径下 LLM 对"双端（paired-end）" vs "两个样本"理解的固有波动。

### 5.2 四条查询对照表

| 查询 | force_custom=False | force_custom=True |
|------|-------------------|-------------------|
| 双端 FASTQ RNA-seq 上游 | `ready/ready`，standard，`rnaseq_singletask` | `draft/draft`，custom，5 步（fastp→star→samtools→rsem→featurecounts），validation_ok |
| GO+KEGG 富集 | `ready/ready`，standard，`diff_expr_go + diff_expr_kegg` | `no_match/no_match`，custom，0 步，gaps: "缺少功能富集分析工具" |
| 单样本 WES FASTQ | `draft/draft`，custom，6 步（fastp→bwa→samtools→gatk→bcftools→snpeff），validation_ok | `missing_assets/missing_data`，custom，同上 6 步链，validation_ok 但无匹配数据 |
| 配对肿瘤正常 WES | `no_match/no_match`，custom，gap: gatk 单槽无法汇合 | `no_match/no_match`，custom，gap: gatk 单槽无法汇合 |

### 5.3 改动前后对比（同一 RNA-seq 查询）

| 指标 | 改动前（修复前代码） | 改动后（当前代码） |
|------|---------------------|---------------------|
| validation_ok | 10/10 | 9/10 |
| 含 multiqc | 0/10 | 0/10 |
| 失败原因 | 无 | LLM 误把"双端"理解为"两个样本"（与 MultiQC 无关） |

### 5.4 全量单元测试结果

```
.venv/bin/python -m unittest discover -s tests
Ran 63 tests in 17.244s
OK (skipped=3)
```

关键测试确认通过：
- `test_force_custom_skips_standard_selection_call`
- `test_capability_question_lists_atomic_tools_separately`
- `test_standard_rnaseq_recipe_uses_only_neo4j_tools`
- `test_standard_llm_stage_does_not_include_method_catalog`

---

## 任务 6：强制 custom 下"看起来能跑但其实不该跑"的场景

基于当前实现，以下查询在 force_custom=True 下可能给出形式上通过校验、但实质上不应该这样跑的链：

1. **GO/KEGG 富集类查询**
   - 原子工具目录中没有富集分析工具（go、kegg、clusterProfiler 等均未注册）。
   - 预期应返回 `decomposition_gaps` 说明"目录中无富集分析工具"。
   - 风险：LLM 可能强行把表达矩阵接到某个不相关的原子工具上，凑出一条形式上合法但语义错误的链。

2. **单样本 WES 想做"变异检测和注释"**
   - 目录中 GATK 只有一个 `sorted_dedup_bam` 输入槽，无法表达 tumor/normal 配对。
   - 单样本场景下 LLM 可能生成 `fastp→bwa→samtools→gatk→bcftools→snpeff` 的 6 步链并通过校验。
   - 风险：这条链在工具连接层面合法，但 GATK 的 Mutect2 实际上需要配对样本才能做体细胞变异检测；单样本做 germline calling 与用户的"变异检测和注释"预期可能不一致。

3. **配对肿瘤正常 WES**
   - 这是正确场景：应被 GATK 单槽限制阻断，返回 `decomposition_gaps`。
   - 风险：如果 LLM 未遵守"配对样本汇合"约束，可能生成两条独立单样本链（tumor 一条、normal 一条），都通过校验但没有真正汇合，执行端无法知道哪两个文件是配对。

4. **要求修改 recipe 的查询（如"把 trim_galore 换成 fastp"）**
   - force_custom=True 跳过 stage-one，因此不会携带 `rnaseq_singletask` 参考 recipe。
   - LLM 可能从零组出一条完全不同的链，而不是在标准 recipe 基础上做最小改动。
   - 这改变了用户意图：用户想"换一步"，系统给了一条新链。

5. **任何需要多 pipeline 组合的查询**
   - standard 模式允许组合多个 pipeline（如 GO + KEGG）。
   - force_custom=True 只能生成单条原子链，无法组合多个标准 pipeline。
   - 风险：用户要"差异表达 + 富集"，force_custom 可能只给出差异表达链，漏掉富集。

### 建议

Demo 现场：
- **适合点 force_custom**：明确的单链原子工具需求（RNA-seq 上游、单样本 WES 预处理）。
- **不适合点 force_custom**：需要组合多个标准 pipeline、需要修改现有 recipe、或原子目录本来就无法覆盖的需求。

---

## 备注

- 任务 3 的基线进程在 `workflow_composer.py` 修改前已启动，因此读取的是修复前的代码版本；其 10/10 通过的结果说明：MultiQC 孤儿问题在"从零组链"的 force_custom 路径上并未触发。
- 由于 `bio-pipeline-kg-matcher/` 目录在父级 git 仓库中为 untracked 状态，本次未提供 git diff，改用"文件:行号"方式记录改动。
