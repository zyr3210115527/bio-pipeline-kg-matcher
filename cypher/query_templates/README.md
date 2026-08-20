# 查询模板

针对 0812 图谱重写。每条模板都用 `EXPLAIN` 对真实实例校验过，标签、关系类型和属性名
与当前图一致。

上一版模板写的是更早的原型模型（`Data` / `Cohort` / `ToolType` 节点，
`BELONG_TO` / `DERIVED_FROM` / `IS_TOOL_TYPE` 关系，`toolId` / `toolName` 属性），
这些标签在改造前的图里就已经不存在，无法机械改名迁移，因此整体重写。
师姐的变更说明 §10.7 也点了这一项。

## 图里就是 0812 交付本身

**数据层（0812，师姐交付）**

| 节点 | 主键 |
|---|---|
| `project` / `study` / `individual` / `sample` | `*_accession` |
| `T1` / `T2` | `t1_id` / `t2_id`（**0819 起小写**，0812 时写作 `T1_id`/`T2_id`；模板已改，照抄旧写法会一行都查不到） |
| `tool` | `tool_id`（T001–T066，实有 51 个，编号不连续） |
| `format` / `function` / `modal` / `datalevel` | `format` / `function` / `modal` / `level` |

关系全部小写：`in_project`、`in_study`、`in_individual`、`in_sample`、`in_format`、
`in_level`、`in_modal`、`generated_from`、`has_function`、`input`、`output`、
`next_tool`、`suitable_for`、`subclass_of`（0819 新增）。

**图里只有这一层。** 我方的 slot 模型（槽位名、WDL 绑定、输入变体、GATK 四槽）
不在 Neo4j 里，它们留在 `data/csv/catalog/`，由 `tool_catalog_source.py` 在运行时
与这张图合并。所以这里的模板只针对她的标签写，不会出现 `tool_id` / `io_slot`。

## 模板清单

| 文件 | 回答的问题 | 参数 |
|---|---|---|
| `find_tools_by_function.cypher` | 哪些工具承担某个功能 | `$keyword` |
| `find_tools_by_input_format.cypher` | 哪些工具能吃某个语义格式 | `$format` |
| `find_tools_by_output_format.cypher` | 哪些工具能产出某个语义格式 | `$format` |
| `find_tool_input_output.cypher` | 某个工具的完整 IO 签名 | `$tool_id` |
| `find_tools_by_modal.cypher` | 某个组学模态适用哪些工具 | `$modal` |
| `recommend_next_tools_via_output_match.cypher` | 某工具之后能接什么（按格式相接） | `$tool_id` |
| `trace_next_tool_chain.cypher` | 沿 `next_tool` 走出的工具链 | `$tool_id` |
| `trace_paths_from_input_format_to_output_format.cypher` | 从输入格式能否到达目标输出格式 | `$input_format`、`$output_format` |
| `find_t1_by_study_and_format.cypher` | 某研究下某语义格式的一级数据 | `$study_accession`、`$format` |
| `find_t1_by_modal.cypher` | 某模态的一级数据在各研究的分布 | `$modal` |
| `trace_data_lineage.cypher` | 某个二级结果由哪些一级数据产生 | `$t2_id` |
| `trace_sample_hierarchy.cypher` | 一级数据往上追到样本、个体、研究、项目 | `$t1_id` |
| `find_paired_tumor_normal_samples.cypher` | 某研究里哪些个体同时有 tumor 和 normal | `$study_accession` |
| `count_data_by_study.cypher` | 每个研究的 T1/T2 计数，核对导入完整性 | 无 |
| `count_by_semantic_format.cypher` | T1/T2 的语义格式分布 | 无 |

## 用这些模板时要知道的数据缺口（数字为 0819 图上实测）

- **run→sample 映射不全，这是最影响下游的一条**：`sample` 节点每个只记录**一个**
  `run_accession`，而文件侧共有 13,063 个 run，**3,758 个 run（29%，牵连 7,516 个 T1 文件）在图里没有对应
  sample 节点**。表现为 T1 有 6,969 行没有 `sample_accession`、拿不到 `in_sample` 边，
  `trace_sample_hierarchy` 对它们只能追到 study。按 run 组织的 fastq 出现
  `sample_accession = null` 属于这一类，**不是"聚合文件本来就没有样本"**，
  也**不能**用 `run_accession` 回连（实测命中 0）。缺口最大的队列：
  HRA000087 1492/1553、HRA016026 684/1384、HRA001272 482/1180、HRA003107 266/576、
  HRA005191 242/485、HRA006499 240/763、HRA000122 23/310。
- **数样本不要走文件路径**：用 `MATCH (sp:sample) WHERE sp.study_accession = $s`
  （等价于 `study<-individual<-sample`），不要用 `(T1)-[:in_sample]->(sample)`
  ——后者只能看到挂了文件的样本。HRA006117 实有 835 个样本，走文件路径只剩 570。
- T2 有 3,855 行没有 `run_accession`，不参与 `generated_from` 溯源。
- `function` 是整句中文描述而不是短标签，所以 `find_tools_by_function` 用 `CONTAINS`
  而不是等值匹配。
- `next_tool` 只有 22 条且集中在 T001–T013，`trace_next_tool_chain` 对新增工具走不出链。
- `sample.specimen_type` 仍有 899 个样本为空，`tissue_type` 有 803 个为空
  （HRA006117 一家就占 265 个），这些样本判不出 tumor/normal 角色。
