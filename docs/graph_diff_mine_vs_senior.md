# 数据图 Diff：我的活图 vs 昨天CSV 全量数据

> 审计日期：2026-07-29
> 我方基准：当前活图（= `docs/mcp_delivery/neo4j/datagraph-staging.dump`）
> 对方基准：师姐 `import/` 全量 CSV（entities + reference + relations）
> 说明：本报告**不含**悬空 sample 议题（那是她 CSV 内部断链，另行处理）。

---

## 0. 一句话结论

- **血缘层（study / individual / sample / t1 / t2）**：她 19 个 study 的**每一个主键**都与我逐个对齐——不是计数相同，是 key 集合完全一致。我另有 1 个独有 study（`HRA000321`，刻意保留）。
- **我图是她数据的一个"做了减法"的投影**：我额外合成了 `run` 层和 `io_slot / builder_param` 工具可观测层；同时**主动没导入**她的 T1↔T2 溯源、format/modal/level 分类边、工具语义链。
- **要她动的**：仅工具层若要同步须先加稳定 `tool_key`。其余"缺口"都是**我方设计取舍**，是否补由产品决定，非她的 bug。

---

## 1. 血缘层：逐 study 主键对齐（决定性证据）

对她 19 个 study，逐个比对 4 类实体的**主键集合**（individual 按 `IN_STUDY` 边计，规避共享 individual 的属性 last-write-wins）：

| study 范围 | individual | sample | t1（文件名） | t2 |
|---|---|---|---|---|
| 师姐 19 个 study | ✅ 全一致 | ✅ 全一致 | ✅ 全一致 | ✅ 全一致 |
| `HRA000321`（我独有） | 我 +65 | — | 我 +904 | 我 +2 |

**没有任何偷换 / 错位 / 遗漏。** 计数相等背后确是同一批主键。

---

## 2. 节点层对照

| 概念 | 我（活图标签） | 计数 | 她（CSV 实体） | 计数 | 说明 |
|---|---|---|---|---|---|
| 研究 | `study` | 20 | study | 19 | 我 +1 = `HRA000321` |
| 项目 | `project` | 18 | project | 17 | 同上带出 |
| 个体 | `individual` | 5400 | individual | 5335 唯一 | 我 +65 = `HRA000321`；她 5494 行含 159 跨 study 共享 |
| 样本 | `sample` | 8640 | sample | 8640 | 一致 |
| 原始文件 | `t1` | 19178 | T1 | 25670 行 | 我按 `file_name` 去重（她大量重复文件名） |
| 处理结果 | `t2` | 38013 | T2 | 38011 | 我 +2 = `HRA000321` |
| **run（我合成）** | `run` | 11120 | —（无此实体） | — | 我从 `T1.csv.run_accession` 合成的一层 |
| 队列 | `cohort` | 26 | —（无） | — | 我方独有 |

**参考类节点**——两边都有、但用途不同：

| 我 | 计数 | 她（reference/） | 计数 |
|---|---|---|---|
| `format` | 27 | formats | 22 |
| `level` | 4 | data_level | 3 |
| `modal` | 8 | multimodal | 4 |
| `function` | 35 | function | 39 |
| `artifact_type` | 33 | —（我方 observability 专有） | — |

> 注：我图里还残留一套**大写标签的旧工具层**（`Tool 24 / IOSlot 44 / Function 24 / Format 18 / ArtifactType 14`），与小写现行层并存，属历史遗留，MCP 不查。

---

## 3. 关系层对照（核心差异所在）

### 3.1 血缘关系——语义等价，形态不同

| 语义 | 她的关系 | 行数 | 我的关系 | 计数 | 判定 |
|---|---|---|---|---|---|
| 个体∈研究 | `individual_in_study` | 5335 | `(individual)-[:IN_STUDY]->(study)` | 5559 | ✅ 等价（共享个体每 study 一条边故略多） |
| 样本∈个体 | `sample_in_individual` | 8640 | `(sample)-[:IN_INDIVIDUAL]->(individual)` | 8099 | ✅ 等价（差值=悬空样本，另议） |
| 研究∈项目 | `study_in_project` | 19 | `(study)-[:IN_PROJECT]->(project)` | 21 | ✅ 等价 |
| t1∈样本 | `T1_in_sample` | 24518 | `t1 →[:IN_RUN]→ run →[:IN_SAMPLE]→ sample` | 19178 / 10623 | ✅ 等价，**我多一跳 run** |
| t1∈研究 | `T1_in_study` | 19860 | `(t1)-[:IN_STUDY]->(study)` | 19178 | ✅ 等价 |
| t2∈研究 | `T2_in_study` | 38011 | `(t2)-[:IN_STUDY]->(study)` | 38013 | ✅ 等价（我 +2 独有） |

### 3.2 她有、我"整个没有或近乎没有"——**设计上主动丢的**

| 她的关系 | 行数 | 我这边 | 定性 |
|---|---|---|---|
| **`T2_generated_from_T1`**（处理结果↔原始文件溯源链） | **59570** | **0 条** | ❗最大缺口。我的血缘不走 t1↔t2 |
| `T1_in_format` / `T1_in_level` | 24518 / 24518 | 仅 904 / 904 条边 | 我把 format/level 存成 **t1 属性**，非边；仅少量遗留边 |
| `T1_in_modal` | 19917 | **0** | modal 节点在、但无 t1→modal 边 |
| `T2_in_format` / `T2_in_level` / `T2_in_modal` | 38011 ×3 | 2 / 1 / 0 条 | 同上，t2 的 format/level 亦为属性 |

### 3.3 工具层——两套完全不同的建模

**我的（面向 PipelineBuilder 投递的 observability 层）：**

| 关系 | 计数 |
|---|---|
| `(tool_id)-[:HAS_INPUT_SLOT]->(io_slot)` | 49 |
| `(tool_id)-[:HAS_OUTPUT_SLOT]->(io_slot)` | 50 |
| `(io_slot)-[:REQUIRES/PRODUCES]->(artifact_type)` | 49 / 50 |
| `(io_slot)-[:ALLOW_FORMAT]->(format)` | 155 |
| `(artifact_type)-[:MANIFEST_AS]->(format)` | 81 |
| `(tool_id)-[:HAS_STEP/NEXT]->(tool_id)`（流程编排） | 7 / 14 |
| `(tool_id)-[:HAS_FUNCTION]->(function)` | 35 |
| `(tool_id)-[:INPUT/OUTPUT]->(format)` | 21 / 37 |

> `io_slot` 上带 `builder_param` / `wdl_target`——本项目为师兄补的真实 WDL 参数名映射。**她完全没有这一层。**

**她的（面向语义分类的工具链）：**

| 关系 | 行数 | 我这边 |
|---|---|---|
| `tool_has_semantic_input` | 70 | 无（我用 io_slot REQUIRES 表达） |
| `tool_has_semantic_output` | 54 | 无（我用 io_slot PRODUCES 表达） |
| `tool_suitable_for_modal` | 52 | 无 |
| `tool_relationship` | 23 | 部分对应我的 NEXT/HAS_STEP |
| `tool_has_function` | 39 | ≈ 我的 HAS_FUNCTION 35 |

工具**节点**：共享约 22 个；她另有 ~15 个原子工具（limma/edgeR/DESeq2/clusterProfiler/Cell Ranger 等 R 包/脚本），**非 PipelineBuilder 可投递项，不影响跑**。

---

## 4. 差异归类与行动清单

| # | 差异 | 影响 MCP 跑？ | 性质 | 谁负责 |
|---|---|---|---|---|
| 1 | 血缘主键 | — | **完全一致** | 无需动作 |
| 2 | `HRA000321` 我独有 | 否 | 刻意保留 | 无需动作 |
| 3 | `run` 层、`io_slot`/`builder_param` | 是（我方靠它跑） | 我方设计增量 | 无需动作 |
| 4 | 15 个原子工具未同步 | 否 | 待定 | **她先加 `tool_key` 稳定列**再议 |
| 5 | `T2_generated_from_T1`（5.9 万条溯源） | 否（MCP 不查） | 我方设计丢弃 | **产品决定**是否补 |
| 6 | format/level/modal 分类边 | 否（我存成属性） | 建模不同 | **产品决定**是否补 |
| 7 | 工具语义链（semantic_input/output 等） | 否 | 建模不同 | **产品决定**是否补 |

---

## 5. 判定

- **"其他都一样吗？"** —— 在 **MCP 真正查询的血缘 + 工具键**层面：**是，逐主键一致**。
- **要师姐改的**：仅第 4 项（同步工具前先加 `tool_key`）。
- **需你拍板的**：第 5/6/7 项是我图相对她的**设计性缺口**（溯源链 + 分类边 + 语义链），不影响当前 MCP，但若目标是"我图完全替代她的全量图"，这些就是待补项。
