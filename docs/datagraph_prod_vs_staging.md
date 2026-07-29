# 生产数据图与 staging 对照

对照时间：2026-07-24。生产端只读；staging 为 `--scope t1` 的已验证快照。

## 身份与总量

| | 生产 | staging |
|---|---|---|
| URI / database | `bolt://127.0.0.1:7687` / `neo4j` | `bolt://127.0.0.1:7688` / `datagraph-staging` |
| database ID | `3B6484DB...C7B1` | `AF76A4FD...F1EF` |
| Neo4j | 2026.06.0 Community | 同版本独立实例 |
| 实际节点 | 34,838 | 32,744 |
| 实际关系 | 81,227 | 73,001 |
| 工具目录 | 24 个 tool 及 slot/artifact/function/format 图 | 0；刻意不导入 |

两端总量不可直接相减解释数据差异，因为生产包含工具目录，且同一工具节点有多个 label。下表只比较数据域。

## 节点对照

| 逻辑实体 | 生产 | staging | 差异与原因 |
|---|---:|---:|---|
| `project` | 11 | 11 | 同一当前 CSV 全集 |
| `study` | 14 | 14 | 同上 |
| `individual` | 3,494 | 3,494 | 同上 |
| `sample` | 6,918 | 6,918 | 同上 |
| `run` | 8,354 | 8,354 | 同上 |
| `t1` | 15,692 | 13,772 | 生产多 1,920：HRA000021 BAM 1,016 + HRA000321 FASTQ 904；staging 无独有记录 |
| `t2` | 99 | 86 | 生产是旧 `T2.1csv` 全集；staging 使用当前 `entities/T2.csv` |
| cohort | 26 | 26 | 数量相同；staging 增加 provenance |
| level | 4 `level` | 4 `data_level` | 改名以隔离工具目录 |
| modal | 8 `modal` | 8 `data_modal` | 同上 |
| format | 27 `format` | 28 `data_format` + 29 `data_format_row` | 生产基本是物理格式；staging 保存 28 个语义概念和 CSV 29 原行，语义不同 |

### T1 关键修正

| 项目 | 生产 | staging |
|---|---:|---:|
| 当前 13,772 条 T1 的非空 `strategy` | 4,656 | 13,772 |
| 当前 T1 缺 `strategy` | 9,116 | 0 |
| 非空 `file_path` | 0 | 13,772 |
| 非空 `read_pair` | 生产全部 T1 15,692 | 当前 T1 13,772 |
| 非空物理/语义格式 | 单个 `format` 15,692 | `physical_format` 13,772 + `semantic_format` 13,772 |

staging 对当前 T1 主键去除历史 ` (N bytes)` 后缀；原始字符串与生产精确相等的只有 1,144 条，但逻辑身份覆盖 13,772/13,772。HRA000021 的 1,016 个 BAM 在 T11 中是 level 2，不属于默认 T1 范围；因此 staging 是显式排除，不是删错。HRA000321 904 条不在 T1/T11，同样不应被默认快照继承。

### 生产多出的 13 个 T2

它们是旧 Clinical/MetaInfo 记录，分布为 HRA000021 2 条、HRA007169 2 条，HRA000074/HRA000873/HRA001272/HRA001748/HRA001749/HRA003107/HRA005191/HRA006499/HRA007167 各 1 条。staging 不保留已从当前 T2 消失的记录，这是方案 A 删除语义的预期结果。

## 关系对照

| 关系及端点 | 生产 | staging | 解释 |
|---|---:|---:|---|
| `study -> project` | 14 | 14 | 一致 |
| `individual -> study` | 3,653 | 3,653 | 一致 |
| `sample -> individual` | 6,090 | 6,090 | 两端均只物化端点存在的边；CSV 的 760 条悬空行在 staging manifest 明示记录 |
| `run -> sample` | 7,857 | 7,857 | 两端均缺 CSV 的 497 条目标 sample；staging 不创建 placeholder，manifest 明示记录 |
| `t1 -> run` | 15,692 | 13,772 | 1,920 差值完全来自生产额外 T1 |
| `t1 -> study` | 15,692 | 13,772 | 同上 |
| `t2 -> study` | 99 | 86 | 13 差值来自生产旧 T2 |
| `t1 -> level` | 15,692 | 13,772 | 同 T1 scope 差值 |
| `t2 -> level` | 75 | 75 | T2 的 11 个空 level 均不建边 |
| `t1 -> format` | 15,692 物理格式 | 13,772 语义格式 | 关系名相同但端点语义不同，不能用数量宣称逐边一致 |
| `t2 -> format` | 99 物理格式 | 85 语义格式 | staging 另将 1 个空 format 行记为 dangling |
| `cohort -> cohort` | 24 | 24 | 数量一致 |
| `data_format_row -> data_format` | 0 | 29 | staging 新增，用于无损保存重复语义格式行 |

生产的额外 8,226 条关系主要包含工具目录关系，以及 1,920 个额外 T1 的四类边和 13 个旧 T2 的边；不是 staging 丢失了当前 CSV 中可物化的关系。

## staging 修正了什么

- 当前 13,772 个 T1 的 `strategy`、`file_path`、物理格式、语义格式和 read pair 都有值。
- 当前 86 个 T2 与规范化 CSV 精确对齐，生产残留的 13 个旧 T2 被清除。
- 所有有效端点的当前关系全部物化；1,269 条不可物化关系不再静默，而是完整进 manifest。
- 所有数据节点/关系带确定性 `snapshot_id`、源表、原行和 hash；相同 CSV 连续两次导入的稳定 manifest 和图指纹完全相同。
- 范围内全量替换已用删除一个 T2 的 CSV 副本证明，源中消失的节点不再永久残留。

## 切换前仍需解决

1. **T1/T11 权威范围待确认**：HRA000122 的 696 个 level-1 WES FASTQ 为何不在 T1，仍无法从数据推导。本轮未替数据负责人决定。
2. **悬空外键是源数据缺口**：497 个 run 的 sample 不在 sample 实体表；760 条 sample-individual 关系有端点缺失。在 matcher 迁移前要么补齐实体真源，要么明确查询必须回报拓扑不完整。
3. **T2 语义格式有噪声**：smoke query 显示两个名为 `Fusion` 的 T2 被 `T2_in_format.csv` 标为 `Raw Counts`，某些 BAM/SpliceJunction 也有可疑语义格式。导入器忠实保留了源值，但 matcher 不应盲目将其当成角色真值。
4. **关系语义已变更**：新 `IN_FORMAT` 指语义格式，物理格式在文件属性。新 matcher 查询必须按 `datagraph/v1` 编写，不能拷贝生产旧 Cypher。
5. **尚未切换运行时**：本轮只完成导入、验证、备份恢复和对照，`CsvKGDataMatcher` 未改，生产未写。

## 结论

staging 已经是对“当前 T1 + 当前 T2 + 规范化实体/关系表”的可复现、可往返、可恢复快照；它不是经数据负责人确认的 T1/T11 最终权威全集。将 matcher 切到 Neo4j 前，优先做双读对照，并对悬空拓扑和 T2 角色噪声 fail closed。
