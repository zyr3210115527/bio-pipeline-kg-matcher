# Round 3 报告：匹配层正确性基准 + assay 校验

> 生成时间：2026-07-23
> 仓库：`bio-pipeline-kg-matcher`
> 测试命令：`python -m unittest discover -s tests`

## 0. 说明

- 本报告对应用户 Round 3 的 7 项任务。
- 任务 1/2/4/6/7 为只读或只出方案；任务 3/5 已实施。
- 每完成一项代码改动均跑了全量测试，结果见对应小节。
- 真值表已写入 `docs/feasibility_truth_table.md`（196 格，14 study × 14 pipeline）。
- 六条 LLM 查询的完整输出写入 `docs/six_queries_round3_full.json`。

---

## 任务 1：assess_feasibility 与 assay 相关逻辑（只读）

### 1.1 `assess_feasibility` 完整逻辑

文件：`pipeline_router.py:493`

判定步骤：

1. 取 pipeline 的 `DATA_PROFILE_TEMPLATES` 角色要求（`required_roles`）。
2. 对 `file_records` 逐个调用 `_role_of_file`，去重得到 `present_roles`。
3. 用 `_role_satisfies` 检查每个 required role 是否被满足。
4. 用 `_REQUIRED_FILE_COUNT` 检查文件数量。
5. 若 required_roles == `["fastq"]` 且数量满足：
   - `wes_somatic_pair`：调用 `_assess_wes_somatic_cases` 检查同个体 tumor/normal 配对。
   - 其它 FASTQ 流程：调用 `_paired_fastq_groups` 检查同源 R1/R2 对数。
6. 返回 `ok` + 可读 message。

**结论：`strategy`/`data_type` 字段完全没有出现在可行性判定里。**
`DATA_PROFILE_TEMPLATES` 虽然每个 profile 都带了 `strategies` 字段，但 `assess_feasibility` 不读它；`_data_profile` 里针对每个 FASTQ 流程重置了 `strategies`，也仅用于 `_match_files` 的打分 hints。

### 1.2 strategy 字段分布

T1 全表：

| strategy | 计数 |
| --- | --- |
| WES | 8922 |
| RNA-Seq | 3028 |
| scRNA-Seq | 1290 |
| WGS | 532 |

T11：

| data_type | 计数 |
| --- | --- |
| WGS | 5076 |
| WES | 2712 |
| WES,RNA-seq | 2360 |
| 0 | 1650 |
| RNA-seq | 1446 |
| WGS,RNA-seq | 1152 |
| scRNA-seq | 1068 |
| #N/A | 20 |

T2：

- 行数：86
- 主要 `format`：dir(34)、tsv(32)、xlsx(10)、maf(9)、xls(1)
- `strategy` 列 mostly `genomic`

### 1.3 其它可表达测序类型的字段

| 表 | 字段名 | 说明 |
| --- | --- | --- |
| T1 | `strategy` | 主字段，取值干净 |
| T1 | `Platform` | 仪器平台，不区分 bulk/scRNA |
| T11 | `data_type` | 原始/脏，多值和空值多 |
| T2 | `strategy` | 基本都是 `genomic`，无判别力 |

**判定：唯一可用的 assay 字段是 T1 的 `strategy`。**

---

## 任务 2：可行性真值表（只读）

已写入 `docs/feasibility_truth_table.md`。

### 2.1 规模说明

用户原需求写“14 study × 12 pipeline = 168 格”，但代码中 `PIPELINE_DATA_PROFILE_KEYS` 实际有 **14 个 pipeline**，因此真值表为 **196 格**。未私自删减 pipeline。

### 2.2 判定规则

一个组合 genuinely feasible 需同时满足：

- A. 数据角色齐全（`DATA_PROFILE_TEMPLATES` 要求的角色 study 都有）
- B. assay 匹配（仅 FASTQ 类流程）
- C. 样本拓扑满足（wes_somatic_pair 需同个体 tumor/normal 各一侧；其它 FASTQ 需 ≥1 对；矩阵/MAF 类不限）

| pipeline | 可接受 assay |
| --- | --- |
| cellranger_workflow | scRNA-Seq |
| rnaseq_singletask | RNA-Seq |
| wes_somatic_pair | WES |
| paired_fastq_to_unmapped_bam | WES / WGS |
| 其它 | assay 不适用 |

### 2.3 汇总（改造前，即当前系统判定）

| 类型 | 数量 | 占比 |
| --- | --- | --- |
| 一致 | 176 | 89.8% |
| 假阳性 | 20 | 10.2% |
| 假阴性 | 0 | 0.0% |

### 2.4 各 pipeline 假阳性率

| pipeline | 一致 | 假阳性 | 假阴性 | 假阳性率 |
| --- | --- | --- | --- | --- |
| cellranger_workflow | 5 | 9 | 0 | 64.3% |
| rnaseq_singletask | 7 | 7 | 0 | 50.0% |
| paired_fastq_to_unmapped_bam | 10 | 4 | 0 | 28.6% |
| 其它 | 14 | 0 | 0 | 0.0% |

**20 个假阳性全部集中在 4 个 FASTQ 流程，且原因全部是 assay 不匹配**（WES/scRNA-Seq 数据被当成 bulk RNA-seq / 10x 可用）。

---

## 任务 3：实施 assay 校验

### 3.1 改动

文件：`pipeline_router.py`

1. `pipeline_router.py:278-280`：修正 `cellranger_workflow` 的 assay 声明
   - 旧：`profile["strategies"] = ["RNA-Seq"]`
   - 新：`profile["strategies"] = ["scRNA-Seq"]`

2. `pipeline_router.py:526-555`：在 `assess_feasibility` 的 FASTQ 分支加入 assay 过滤
   - 用 `_data_profile(pid)` 的 `strategies` 作为允许 assay 集合。
   - 若存在非空 strategy 标注但都不在允许集合内，则 `assay_blocked=True`。
   - 若全部 FASTQ 都为空 strategy（单元测试的合成记录），按兼容处理，避免误杀。
   - assay 不通过时 message 示例：
     - `「rnaseq_singletask」需要 RNA-Seq 测序数据，当前匹配到的 FASTQ 为 WES，无法直接使用。`

3. `pipeline_router.py:571`：新增 `elif assay_blocked` 分支输出 assay_message。

### 3.2 测试结果

```text
Ran 63 tests in 17.621s
OK (skipped=3)
```

### 3.3 改造前后假阳性对比

| 阶段 | 假阳性 | 假阴性 |
| --- | --- | --- |
| 改造前 | 20 | 0 |
| 改造后 | 0 | 0 |

| pipeline | 改造前 FP | 改造后 FP |
| --- | --- | --- |
| cellranger_workflow | 9 | 0 |
| rnaseq_singletask | 7 | 0 |
| paired_fastq_to_unmapped_bam | 4 | 0 |
| wes_somatic_pair | 0 | 0 |
| 其它 | 0 | 0 |

---

## 任务 4：查询 1 选错 study 根因 + HRA006499 数量核对

### 4.1 查询 1 实际行为（改动后重跑）

```json
{
  "query": "我有肿瘤和正常配对的 WES FASTQ，想做体细胞变异检测并注释",
  "workflow_mode": "custom",
  "selection_status": "no_match",
  "orchestration_status": "no_match",
  "pipeline_ids": ["paired_fastq_to_unmapped_bam", "wes_somatic_maf_landscape"],
  "study_accession": "HRA000071",
  "feasibility_status": "ready",
  "feasibility_message": "流程所需的用户样本数据已匹配。",
  "assets_count": 2,
  "tool_chain_step_ids": []
}
```

### 4.2 根因

**不是 `_preferred_study_bonus` 里的 HRA 硬编码加分。**

真实链路：

1. LLM stage-one（`_llm_decision`）判定为 `custom`：
   - 理由：菜单里没有任何 pipeline 能覆盖“WES FASTQ → 体细胞变异检测并注释”完整流程。
   - `pipeline_ids: []`
   - `reference_pipeline_ids: ["paired_fastq_to_unmapped_bam", "wes_somatic_maf_landscape"]`
2. `_custom_plan` 调用 `router.route(text, ..., selected_pipeline_ids=reference_ids)`。
3. `PipelineRouter.route` 以 `paired_fastq_to_unmapped_bam` 为 primary pipeline 调用 `matcher.match`。
4. 对该 pipeline，`_match_files` 给 HRA000071 的 `.fq.gz` 文件打了同样的高分（格式匹配 + strategy 匹配），按文件名字母序排第一，于是文件候选为 HRA000071。

因此 **HRA000071 的出现是 LLM 自定义分解选择了错误的参考 pipeline + 文件打分按字母序 tie-break 的结果**，与 `wes_somatic_pair` 的 `+28` 加分无关（该 pipeline 根本没被 LLM 选为参考）。

### 4.3 `_preferred_study_bonus` 审计

代码：`pipeline_router.py:778-790`

```python
def _preferred_study_bonus(self, pipeline_id, study_accession, file_name, query_text):
    ...
    if pipeline_id == "wes_somatic_pair":
        if study_accession == "HRA001272" and any(x in file_name for x in ["HRR365660", "HRR365661"]):
            return 28
        if study_accession == "HRA001749":
            return -18
    ...
```

- 加分表里**没有 HRA000071**。
- 对 `wes_somatic_pair` 的直接影响：HRA001272 的 4 个文件会 +28 冲到 file candidates 最前面；但它们没有角色规则，配不出 case，组合阶段会被跳过。
- 移除方案：直接删掉该函数及 `_match_files` 中的调用（line 893-897）。影响面：仅 `wes_somatic_pair` 和 `wes_somatic_maf_landscape` 两个 pipeline 的排序；当前无测试直接覆盖，需新增回归测试。

### 4.4 排序阶段是否考虑“能否构成合格 somatic case”

**没有。** `_match_files` 只按文本/格式/strategy 打分，完全不调用 `_sample_role` 或 `_assess_wes_somatic_cases`。一个有角色规则且能配成 tumor/normal 的 study（如 HRA000873）并不会因此排前。这是设计缺口。

### 4.5 HRA006499 数量核对

按**全部** HRA006499 FASTQ 重新统计：

| 指标 | 数值 |
| --- | --- |
| FASTQ 文件数 | 1526 |
| 能推断角色的个体数 | 94 |
| 单侧多样本（multi） | 43 |
| 只有单侧（one-sided） | 38 |
| 合格配对 case | **13** |

上一轮“40 个配对个体 / 29 个因多区域丢弃 → 应剩 11，实际跑出 13”的差异来源：

- “40”大概率来自**截断后的文件列表**，只看到了部分个体；
- 实际 94 个有角色的个体中，43 个是多区域/多样本，38 个只有单侧，剩 13 个是干净的 1 tumor + 1 normal。

---

## 任务 5：limit 截断修复

### 5.1 机制

`CsvKGDataMatcher.match`（`pipeline_router.py:748`）原实现：

```python
files = self._match_files(..., limit=limit * 5, intent=intent)
combos = self._build_combinations(pipeline_ids, files, limit=limit)
```

即组合/可行性判断是在截断到 `limit*5` 的文件列表上做的。对 `wes_somatic_pair` 默认 `limit=10` 时只取 50 条文件，而这 50 条恰好全是 HRA000873 的 normal 文件（同分后按文件名字母序排前），导致配不出 tumor/normal case。

### 5.2 改动

`pipeline_router.py:759-761`

```python
# 组合/可行性判断需要在全部候选文件上做，不能在截断后的列表上做；
# 截断只影响展示给用户的 file_candidates。
files = self._match_files(..., limit=None, intent=intent)
```

`_match_files` 返回全部有正分的文件；`file_candidates` / `data_combinations` 仍在返回时 `[:limit]` 截断。

### 5.3 测试结果

```text
Ran 63 tests in 16.353s
OK (skipped=3)
```

### 5.4 对查询 1 的直接影响

直接调用 `matcher.match(..., pipeline_ids=["wes_somatic_pair"])` 现在能正确产出 HRA000873 的配对组合：

```text
files 4 combos 5
combo HRA000873 HRI104775 ['tumor','tumor','normal','normal']
combo HRA000873 HRI104776 ['tumor','tumor','normal','normal']
...
```

**但 Composer 层面的查询 1 仍返回 HRA000071/no_match**，因为 LLM 阶段就没有选 `wes_somatic_pair`。这是 task 4 已经指出的根因。

---

## 任务 6：format 标注错误的代码层拦截（只出方案）

### 6.1 现状扫描

T1/T11 基本干净；问题集中在 **T2.csv**：

| 问题 | 计数 | 涉及 study |
| --- | --- | --- |
| `file_type=DIR` 但 `format` 标成 tsv/maf | 19 | HRA000021/071/074/087/127/169/191/321/748/749 等 |
| 目录/矩阵名称含 `h5`/`matrix` 但 `format=maf` | 1 | HRA000321 Matrix-h5 |

具体矛盾记录（节选）：

- `HRA000074/BAM` `file_type=DIR` `format=maf` → 被 `_role_of_file` 判为 `maf`
- `HRA000074/Fusion` `file_type=DIR` `format=maf` → 被 `_role_of_file` 判为 `maf`
- `HRA000321/Matrix-h5` `file_type=DIR` `format=maf` → 被 `_role_of_file` 判为 `maf`
- `HRA001272/Fusion` `file_type=DIR` `format=maf` → 被 `_role_of_file` 判为 `maf`

### 6.2 方案：`_format_consistency_check(record)`

建议在 `_role_of_file` 之前做一次一致性降级：

```python
def _format_consistency_check(record: Dict[str, Any]) -> Optional[str]:
    """
    若 format/文件名明显矛盾，返回修正后的 role；否则返回 None，由 _role_of_file 正常推断。
    """
    name = (record.get("files") or record.get("file") or "").lower()
    fmt = (record.get("format") or "").lower()
    file_type = (record.get("file_type") or "").lower()

    # 规则 1：目录条目不应被当作数据文件
    if file_type == "dir" or name.endswith(("-files", "files")):
        return "dir"

    # 规则 2：matrix/h5 条目不应被当作 maf
    if fmt == "maf" and ("matrix" in name or "h5" in name):
        return "other"

    return None
```

在 `assess_feasibility` 和 `_role_of_file` 的入口先调用它：

```python
role = _format_consistency_check(f) or _role_of_file(f)
```

### 6.3 规则表

| 矛盾类型 | 判定规则 | 处理 |
| --- | --- | --- |
| 目录条目标非 dir 格式 | `file_type == "DIR"` 或名称以 `-files`/`files` 结尾 | role → `dir`，不计入任何 pipeline |
| h5/matrix 标成 maf | `format == "maf"` 且名称含 `matrix`/`h5` | role → `other` |
| 扩展名与 format 冲突（如 `.bam` 标 tsv） | 可后续扩展 | 记 warning，暂不影响 |

### 6.4 影响面评估

若加上述两条规则，当前系统判定会变化的真值表格子：

| study | pipeline | 当前系统判定 | 加检查后的真值 |
| --- | --- | --- | --- |
| HRA000021 | wes_somatic_maf_landscape | ✓ | ✗ |
| HRA000074 | wes_somatic_maf_landscape | ✓ | ✗ |
| HRA000321 | wes_somatic_maf_landscape | ✓ | ✗ |
| HRA006499 | wes_somatic_maf_landscape | ✓ | ✗ |

即 **4 个假阳性会被纠正**，全部属于 `wes_somatic_maf_landscape` 因 T2 目录/名称被误判为 MAF。

### 6.5 风险

- T2 中 `BAM-files`、`SomaticSNV-VCF-files` 等目录可能确实包含对应数据，但目前只存了目录。降级后这些 study 会暂时失去该 pipeline 的可行性，直到目录被展开为具体文件。
- 规则应放在数据层还是匹配层需再确认：更干净的做法是修正 `data/csv/entities/T2.csv`，但用户明确本轮不改 CSV。

---

## 任务 7：T11 纳入方案（只出方案）

### 7.1 现状

- T1 行数：13772
- T11 行数：15484
- **T11-only（文件名未进入 T1）**：1712 条
- T11-only 全属于两个 study：
  - `HRA000122`：696 条 FASTQ（WES）
  - `HRA000021`：1016 条 BAM（WGS）

### 7.2 T11-only 字段可用性

T11 本身包含：

| 字段 | 非空率 |
| --- | --- |
| study/sample/run accession | 100% |
| data_type / strategy | 100% |
| Read Pair | 100% |
| files / file_path / format | 100% |
| Platform / Experiment | 100% |

缺少但可补的字段：

| 字段 | 补齐方式 |
| --- | --- |
| `individual_accession` | 通过 `sample_in_individual.csv` + `sample.csv` 的 `individual_accession` 列 |
| `individual_name` | `sample.csv` 的 `individual_name` |
| `sample_name` | `sample.csv` 的 `sample_name` |
| `specimen_types` | `sample.csv` 的 `specimen_types` |
| `gender` | 可留空或从 `individual.csv` 取 |

### 7.3 需要改动的位置

`pipeline_router.py:630-701` 的 `_load_normalized_t1` / `__init__`：

```python
# 现有逻辑：T1 为骨架，T11 只用于补齐 path/format
# 新增逻辑：把 T11 中未被 T1 覆盖的行也转成 file record 并 append 到 self.t1

t1_names = {self._clean_data_name(r.get("files") or "") for r in normalized_rows}
sample_by_acc = {r["sample_accession"]: r for r in self.sample if r.get("sample_accession")}
run_to_sample = {r["run_accession"]: r["sample_accession"] for r in _read_csv(self.relation_dir / "run_in_sample.csv")}

for row in legacy_rows:
    name = self._clean_data_name(row.get("files") or "")
    if name in t1_names:
        continue
    sample_acc = row.get("sample_accession") or run_to_sample.get(row.get("run_accession"), "")
    sample_row = sample_by_acc.get(sample_acc, {})
    adapted.append({
        "study_accession": row.get("study_accession"),
        "sample_accession": sample_acc,
        "run_accession": row.get("run_accession"),
        "data_type": row.get("data_type"),
        "Read Pair": row.get("Read Pair") or self._guess_read_pair(name),
        "files": name,
        "format": row.get("format") or self._infer_format(name),
        "file_path": row.get("file_path") or name,
        "file_description": row.get("file_description") or "",
        "Experiment": row.get("Experiment"),
        "Platform": row.get("Platform"),
        "data_level": row.get("data_level") or "1",
        "strategy": row.get("data_type") or "",
        "individual_accession": sample_row.get("individual_accession") or "",
        "individual_name": sample_row.get("individual_name") or "",
        "sample_name": sample_row.get("sample_name") or "",
        "specimen_types": sample_row.get("specimen_types") or "",
        "gender": "",
    })
```

### 7.4 影响估算

用上述补齐逻辑模拟后，可行性变化仅 1 格：

| study | pipeline | 纳入 T11 前 | 纳入 T11 后 |
| --- | --- | --- | --- |
| HRA000122 | paired_fastq_to_unmapped_bam | ✗ | ✓ |

`HRA000122` 是 WES FASTQ（白血病），没有登记 `STUDY_ROLE_RULES`，因此 `wes_somatic_pair` 仍不可行。

`HRA000021` 的 1016 条是 BAM（WGS），当前菜单没有纯 BAM 入口流程，因此不增加任何可行性格子。

### 7.5 风险

- T1 是“标准化后”的实体表，T11 是“遗留原始”表。1712 条未被 T1 覆盖是否是有意过滤（如质量不合格、去重）？
- 目前**没有证据**能判断；建议标 **“待确认”**，不要直接纳入生产。
- 若纳入，需同步检查 `T1_in_format.csv`、`T1_in_level.csv` 等关系表是否也需要补录，否则 format/level 可能走 legacy 推断路径。

---

## 8. 六条 LLM 查询输出（改动后）

完整 JSON 见 `docs/six_queries_round3_full.json`。下面是关键字段摘要：

| # | 查询 | mode | selection_status | study | 关键结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | 配对 WES FASTQ → 体细胞变异检测并注释 | custom | no_match | HRA000071 | LLM 认为没有标准 pipeline 能覆盖完整流程；根因见 task 4 |
| 2 | RNA-seq 上游把 trim_galore 换 fastp | custom | no_match | HRA000071 | MultiQC 相关 NEXT 错误已消失；但仍无有效 custom 步骤 |
| 3 | 双端 FASTQ → RNA-seq 上游 | standard | ready | HRA000074 | 流程与数据均匹配 |
| 4 | TPM 矩阵 → 无监督聚类 | standard | missing_assets | HRA000074 | 正确识别为 count/TPM 类型不匹配 |
| 5 | 同时做 GO 和 KEGG 富集 | standard | ready | HRA000074 | 两个流程组合可行 |
| 6 | 单个 WES FASTQ → 变异检测和注释 | custom | draft | HRA000071 | 自定义方法链草案：fastp → bwa → samtools → gatk → bcftools → snpeff |

说明：

- 查询 1 没有回归成 `ready`，因为 gatk 单 BAM 槽限制仍在，LLM 仍判 custom。这是预期行为。
- 查询 2 的 validation errors 已不再包含 multiqc 入边错误（MultiQC 已移除），但 custom 步骤仍为空，所以仍是 no_match。

---

## 9. 代码改动 diff（文件:行号）

### assay 校验

- `pipeline_router.py:278-280`：`cellranger_workflow` 的 `strategies` 从 `RNA-Seq` 改为 `scRNA-Seq`
- `pipeline_router.py:526-555`：新增 assay 过滤逻辑
- `pipeline_router.py:571`：新增 `elif assay_blocked` 分支

### limit 截断修复

- `pipeline_router.py:759-761`：`match()` 中 `_match_files` 的 `limit` 从 `limit * 5` 改为 `None`

---

## 10. 判断与建议

### 10.1 本轮最重要的发现

1. **assay 错配是 20/20 假阳性的唯一原因**，一个字段加校验即可清零。这个改动优先级最高，已经做了。
2. **limit 截断是隐藏杀手**。即使 assay 正确，默认 `limit=10` 也会把 wes_somatic_pair 的 tumor 文件全部截掉。也已经修复。
3. **查询 1 仍不 ready 的根因在上层 LLM 规划器**，不在匹配层。LLM 因为 `wes_somatic_pair` 的质量门 / 已知 blocker 而不选它，转去自定义分解，导致失败。这需要产品决策：是否让 LLM 信任 `wes_somatic_pair` 作为标准流程。
4. **format 一致性错误虽然数量少（4 条记录影响 4 个格子），但都是“有目录无真实 MAF”的假阳性**，容易误导。

### 10.2 还没问到的边界情况

- `_role_of_file` 对 `bam`/`vcf` 的判定顺序在 `maf` 之后。T2 中一些 `format=maf` 的 BAM 目录已经被 assay 校验隔离（它们不是 FASTQ），但仍可能污染 MAF 类流程的匹配。建议 format 检查尽快落地。
- `HRA000021` 的 1016 个 WGS BAM 目前完全不可见。如果未来支持 BAM 入口，这是最大的一块可捡数据。
- `HRA001748/1749` 跨 study 配对已确认死亡：一个是 scRNA-Seq，一个是 WES。即使 individual_accession 相同，assay 也不同，不能配成 somatic WES。

### 10.3 如果只能再改一处

**把 format 一致性检查落地**（task 6）。

理由：assay 校验已经把 FASTQ 流程的假阳性清零，但 `wes_somatic_maf_landscape` 仍靠 T2 中错标的目录撑着 4 个假阳性。format 检查规则简单、影响面清晰，且不需要改 CSV，是性价比最高的一步。

---

*报告结束。*
