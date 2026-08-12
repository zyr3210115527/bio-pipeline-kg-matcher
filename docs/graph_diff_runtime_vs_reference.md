# 数据图 Diff：运行图 vs 参考数据集

> 审计日期：2026-07-29
> 运行图：审计当时的 Neo4j 活图（对应已删除的 datagraph-staging dump，即 0811 改造前的图）
> 参考数据集：上游交付的全量 CSV（entities + reference + relations）
> 说明：本报告为一次结构性核对，供后续对齐讨论参考；不涉及悬空 sample 议题（那是源 CSV 内部的引用断链，另行处理）。

---

## 0. 摘要

- **血缘层（study / individual / sample / t1 / t2）**：逐主键核对下，参考数据集的 19 个 study 与运行图一致（individual 按 `IN_STUDY` 边计）。运行图另含 1 个数据集里没有的 study（`HRA000321`），为历史保留。
- 运行图是参考数据集的一个**带取舍的投影**：额外合成了 `run` 一跳与 `io_slot / builder_param` 工具可观测层；同时未纳入参考数据集的 T1↔T2 溯源、format/modal/level 分类边、工具语义链。
- 需对方配合的仅一处：工具层若要同步，需要一个稳定的 `tool_key` 列。其余差异属两侧建模取向不同，是否补齐可按需要再定。

---

## 1. 血缘层：逐 study 主键核对

对参考数据集的 19 个 study，逐个比对 4 类实体的**主键集合**（individual 按 `IN_STUDY` 边计，以规避共享 individual 的属性 last-write-wins）：

| study 范围 | individual | sample | t1（文件名） | t2 |
|---|---|---|---|---|
| 参考数据集 19 个 study | ✅ 一致 | ✅ 一致 | ✅ 一致 | ✅ 一致 |
| `HRA000321`（仅运行图有） | +65 | — | +904 | +2 |

主键层面未发现差异，计数相等背后是同一批主键。

---

## 2. 节点层对照

| 概念 | 运行图标签 | 计数 | 参考数据集实体 | 计数 | 说明 |
|---|---|---|---|---|---|
| 研究 | `study` | 20 | study | 19 | 多 1 = `HRA000321` |
| 项目 | `project` | 18 | project | 17 | 同上带出 |
| 个体 | `individual` | 5400 | individual | 5335 唯一 | 多 65 = `HRA000321`；数据集 5494 行含 159 个跨 study 共享 |
| 样本 | `sample` | 8640 | sample | 8640 | 一致 |
| 原始文件 | `t1` | 19178 | T1 | 25670 行 | 运行图按 `file_name` 去重（数据集有大量重复文件名） |
| 处理结果 | `t2` | 38013 | T2 | 38011 | 多 2 = `HRA000321` |
| run（运行图合成） | `run` | 11120 | —（无此实体） | — | 由 `T1.csv.run_accession` 合成的一层 |
| 队列 | `cohort` | 26 | —（无） | — | 运行图侧独有 |

参考类节点——两侧都有，用途略有不同：

| 运行图 | 计数 | 参考数据集（reference/） | 计数 |
|---|---|---|---|
| `format` | 27 | formats | 22 |
| `level` | 4 | data_level | 3 |
| `modal` | 8 | multimodal | 4 |
| `function` | 35 | function | 39 |
| `artifact_type` | 33 | —（运行图 observability 专有） | — |

> 注：运行图里另有一套**大写标签的旧工具层**（`Tool 24 / IOSlot 44 / Function 24 / Format 18 / ArtifactType 14`），与小写现行层并存，属历史遗留，MCP 不查询。

---

## 3. 关系层对照

### 3.1 血缘关系——语义等价，形态不同

| 语义 | 参考数据集关系 | 行数 | 运行图关系 | 计数 | 判定 |
|---|---|---|---|---|---|
| 个体∈研究 | `individual_in_study` | 5335 | `(individual)-[:IN_STUDY]->(study)` | 5559 | ✅ 等价（共享个体每 study 一条边，故略多） |
| 样本∈个体 | `sample_in_individual` | 8640 | `(sample)-[:IN_INDIVIDUAL]->(individual)` | 8099 | ✅ 等价（差值=悬空样本，另议） |
| 研究∈项目 | `study_in_project` | 19 | `(study)-[:IN_PROJECT]->(project)` | 21 | ✅ 等价 |
| t1∈样本 | `T1_in_sample` | 24518 | `t1 →[:IN_RUN]→ run →[:IN_SAMPLE]→ sample` | 19178 / 10623 | ✅ 等价，运行图多一跳 run |
| t1∈研究 | `T1_in_study` | 19860 | `(t1)-[:IN_STUDY]->(study)` | 19178 | ✅ 等价 |
| t2∈研究 | `T2_in_study` | 38011 | `(t2)-[:IN_STUDY]->(study)` | 38013 | ✅ 等价（多 2 为独有） |

### 3.2 参考数据集有、运行图暂未纳入的部分

| 参考数据集关系 | 行数 | 运行图 | 说明 |
|---|---|---|---|
| `T2_generated_from_T1`（处理结果↔原始文件溯源链） | 59570 | 0 条 | 运行图血缘目前不走 t1↔t2 |
| `T1_in_format` / `T1_in_level` | 24518 / 24518 | 仅 904 / 904 条边 | 运行图把 format/level 存为 **t1 属性**，仅少量遗留边 |
| `T1_in_modal` | 19917 | 0 | modal 节点在，暂无 t1→modal 边 |
| `T2_in_format` / `T2_in_level` / `T2_in_modal` | 38011 ×3 | 2 / 1 / 0 条 | 同上，t2 的 format/level 亦为属性 |

### 3.3 工具层——两套不同的建模

**运行图（面向 PipelineBuilder 投递的 observability 层）：**

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

> `io_slot` 上带 `builder_param` / `wdl_target`，来自上游 workflow 卡片的真实 WDL 参数名映射；参考数据集侧没有这一层。

**参考数据集（面向语义分类的工具链）：**

| 关系 | 行数 | 运行图 |
|---|---|---|
| `tool_has_semantic_input` | 70 | 以 io_slot `REQUIRES` 表达 |
| `tool_has_semantic_output` | 54 | 以 io_slot `PRODUCES` 表达 |
| `tool_suitable_for_modal` | 52 | 暂无 |
| `tool_relationship` | 23 | 部分对应 `NEXT`/`HAS_STEP` |
| `tool_has_function` | 39 | ≈ `HAS_FUNCTION` 35 |

工具**节点**：共享约 22 个；参考数据集另有约 15 个原子工具（limma/edgeR/DESeq2/clusterProfiler/Cell Ranger 等 R 包/脚本），非 PipelineBuilder 可投递项，不影响运行。

---

## 4. 差异归类与清单

| # | 差异 | 影响 MCP 运行？ | 性质 | 后续 |
|---|---|---|---|---|
| 1 | 血缘主键 | — | 一致 | 无需动作 |
| 2 | `HRA000321` 仅运行图有 | 否 | 历史保留 | 无需动作 |
| 3 | `run` 层、`io_slot`/`builder_param` | 是（运行图依赖） | 运行图侧增量 | 无需动作 |
| 4 | 约 15 个原子工具未同步 | 否 | 待定 | 同步前建议先加稳定 `tool_key` 列 |
| 5 | `T2_generated_from_T1`（约 5.9 万条溯源） | 否（MCP 不查询） | 建模取舍 | 可按需补齐（见 §5） |
| 6 | format/level/modal 分类边 | 否（运行图存为属性） | 建模不同 | 可按需补齐 |
| 7 | 工具语义链（semantic_input/output 等） | 否 | 建模不同 | 可按需补齐 |

---

## 5. 补齐路径与可行性

初步核对下来，两侧的缺口性质不对称，倾向于「分层各认一个权威源、由运行图侧单向投影」，而非两侧互补。

### 5.1 运行图侧补齐——可由本侧独立完成

运行图缺的部分，源数据都在已交付的 CSV 里，可像已有的 resync 一样翻译进来：

| 待补 | 数据源 | 实测可落地量 | 备注 |
|---|---|---|---|
| `T2_generated_from_T1`（溯源边） | `T2_generated_from_T1.csv` 59570 行 | 57620 条（96%）两端可接到运行图现有节点 | 剩 4% 文件名不在运行图 t1；数据集 20% 的 T1 端标 `::NOT_FOUND`，按文件名仍可落到运行图 t1 |
| `modal` 分类边 | `T1/T2_in_modal.csv` | 可直接翻译 | 约 30~37% 为 NOT_FOUND；modal 亦可改存为属性 |
| `format`/`level` | `T1/T2_in_format/level.csv` | 运行图已存为 t1/t2 属性 | 若要改成边则需再翻译一遍，收益有限 |

→ 这部分不依赖对方，一个翻译脚本即可完成。

### 5.2 参考数据集侧补齐——多数无实际收益

参考数据集"缺"的多是运行图为 MCP 合成的部分，未必适合让对方补：

| 参考数据集"缺"的 | 本质 | 让对方补是否合适 |
|---|---|---|
| `run` 层 | 由 `run_accession` 合成的一跳 | 对方用 `T1_in_sample` 直连，通常不需要 |
| `io_slot` / `builder_param` / `artifact_type` | 由上游 workflow 卡片合成的工具投递可观测层 | 需对方引入 workflow 包并采用本侧 schema，对其数据集用途收益有限 |

### 5.3 倾向的对齐方式

- **血缘 / 溯源 / 参考分类**：以参考数据集为权威源，运行图侧翻译投影（溯源实测约 96% 可落地）。
- **工具可观测层（io_slot/builder_param）**：以运行图侧为权威源（来自上游卡片），对方不必参与。
- 若要同步工具节点，建议先在参考数据集侧加稳定 `tool_key` 列（见第 4 项）。

---

## 6. 小结

- 在 MCP 实际查询的血缘 + 工具键层面，运行图与参考数据集主键一致；仅保留了运行图独有的 `HRA000321`。
- 需对方配合的仅工具同步时的 `tool_key` 一项。
- 关于「两侧各补各的缺口」：运行图缺的部分可由本侧独立补齐（溯源约 96% 可落地）；参考数据集"缺"的多为本侧 MCP 集成层，倾向不由对方补，而是分层定权威源、单向投影（§5.3）。
- 待定：是否将 `T2_generated_from_T1`（及可选 modal 边）翻译进运行图，使其成为参考数据集的忠实超集——此项不影响当前 MCP，仅为「运行图完整覆盖参考数据集」这一目标做准备，可按需要再定。
