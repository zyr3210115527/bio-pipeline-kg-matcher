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
| `T1` / `T2` | `T1_id` / `T2_id` |
| `tool` | `tool_id`（T001–T066） |
| `format` / `function` / `modal` / `datalevel` | `format` / `function` / `modal` / `level` |

关系全部小写：`in_project`、`in_study`、`in_individual`、`in_sample`、`in_format`、
`in_level`、`in_modal`、`generated_from`、`has_function`、`input`、`output`、
`next_tool`、`suitable_for`。

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

## 用这些模板时要知道的数据缺口

- T1 有 6,848 行没有 `sample_accession`，这些行不会有 `in_sample` 边，
  `trace_sample_hierarchy` 对它们只能追到 study。
- T2 有 3,878 行没有 `run_accession`，不参与 `generated_from` 溯源。
- `function` 是整句中文描述而不是短标签，所以 `find_tools_by_function` 用 `CONTAINS`
  而不是等值匹配。
- `next_tool` 只有 22 条且集中在 T001–T013，`trace_next_tool_chain` 对新增工具走不出链。
- `sample.specimen_types` 不是 0812 自带的，由
  `cypher/import0812/06_backfill_sample_specimen.cypher` 从改造前的图回填 8,353 行，
  覆盖不到 0812 新增的 1,825 个样本。
