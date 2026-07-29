# 数据图目标 schema

版本：`datagraph/v1`；默认范围：`--scope t1`；已验证快照：`dg-b23135d49c950d0846a563bc`。

## 设计边界

- 数据图与工具目录完全分开。本 schema 不使用 `Tool/tool_id/io_slot/artifact_type/function/format` 等工具标签，也不创建 `NEXT/HAS_STEP/ALLOW_FORMAT` 等目录关系。
- 所有实体的 CSV 原列均作为 Neo4j 字符串属性保存，包括空串。另存 `source_row_json` 和 SHA-256，保证列顺序及原值可往返还原。
- `t1` 是 `entities/T1.csv` 的当前范围，用 `T11.csv` 补足路径、物理格式、read pair 和历史元数据。`t1_plus_t11` 和 `custom` 只是显式参数，不替数据负责人决定权威全集。
- 语义格式使用 `data_format`，避免与工具目录 `format` 碰撞。`formats.csv` 的 29 行中有 28 个唯一名称；`data_format_row` 保存全部 29 行，`data_format` 保存 28 个语义概念。

## 通用 provenance

每个管理节点都带：

| 属性 | 类型 | 必需 | 含义 |
|---|---|---|---|
| `datagraph_managed` | Boolean | 是 | 固定为 `true`；方案 A 删除范围的安全标记 |
| `snapshot_id` | String | 是 | 由 schema、scope 和源文件 hash 决定，不含时间或随机值 |
| `source_table` | String | 是 | 相对 `data/csv/` 的源表，派生节点写明派生来源 |
| `source_row_number` | Integer | 按表 | CSV 原行号，含表头偏移 |
| `source_row_hash` | String | 是 | 该行或派生输入的 SHA-256 |
| `source_row_json` | String | 按表 | 按 CSV 原列顺序保存的整行 JSON |

每条物化关系还带 `derived: Boolean`；非派生关系的 `source_row_json` 参与往返验证。

## 节点

“原表列”全部为 String；只有主键和通用 provenance 是 schema 必需项，其余是源数据必填率的事实，不在导入时擅自填充。

| 标签 / 已验证数 | 源 | 主键 | 原表属性 |
|---|---|---|---|
| `project` / 11 | `entities/project.csv` | `project_accession` | `project_accession, project_name, project_code, relevance, project_description, data_types, organisms, sample_scope, individual_count, country, tumor_type, study_accession, type, health_conditions, organization, submission_date, release_date, information_source` |
| `study` / 14 | `entities/study.csv` | `study_accession` | `study_accession, title, study_description, study_type, tumor_type, individual_count, sample_count, information_source` |
| `individual` / 3,494 | `entities/individual.csv` | `individual_accession` | 该表全部 48 列：`project_accession` 至 `overall_vital_status`；实际属性名与 CSV 表头逐字一致 |
| `sample` / 6,918 | `entities/sample.csv` | `sample_accession` | `study_accession, sample_accession, sample_name, sample_description, individual_accession, individual_name, biospecimen_anatomic_site, sample_type, specimen_types, strategy, tissue_type` |
| `run` / 8,354 | `relations/run_in_sample.csv` 及当前 T1 的 run 并集 | `run_accession` | `run_accession`；无独立 run 实体表，因此不伪造其他属性 |
| `t1` / 13,772 | `entities/T1.csv` + `T11.csv` + T1 format/level 关系表 | `files` | `study_accession, individual_accession, individual_name, sample_accession, sample_description, sample_name, gender, run_accession, files, experiment_accession, platform, strategy, data_type, read_pair, physical_format, semantic_format, file_path, file_description, data_level, pipeline_id, parameter`; 另有 `normalized_source_*`, `legacy_source_*`, `source_tables`, `*_source_present` |
| `t2` / 86 | `entities/T2.csv` | `t2_id` | `study_accession, t2_id, files, file_type, format, size, data_level, size_bytes, file_path, strategy` |
| `data_format` / 28 | `reference/formats.csv` 唯一名称概念 | `format` | `format`, `descriptions: List<String>` |
| `data_format_row` / 29 | `reference/formats.csv` 每一原行 | `format_row_id` | `format_row_id, format, description` |
| `data_level` / 4 | `reference/data_level.csv` | `level` | `level, name, description` |
| `cohort` / 26 | `reference/cohorts.csv` | `status` | `status, description` |
| `data_modal` / 8 | `reference/multimodal.csv` | `modal` | `modal, description` |

`t1.files` 去掉历史 ` (N bytes)` 显示后缀后作唯一键。HRA000021 BAM 的 `data_level/read_pair` 和所有 T1 `strategy/file_path` 均以当前 CSV 为准，不沿用生产图旧值。

## 关系

| 关系 | 方向 | 源 | 已物化 | 跳过的悬空行 |
|---|---|---|---:|---:|
| `IN_PROJECT` | `study -> project` | `relations/study_in_project.csv` | 14 | 0 |
| `IN_STUDY` | `individual -> study` | `relations/individual_in_study.csv` | 3,653 | 0 |
| `IN_INDIVIDUAL` | `sample -> individual` | `relations/sample_in_individual.csv` | 6,090 | 760 |
| `IN_SAMPLE` | `run -> sample` | `relations/run_in_sample.csv` | 7,857 | 497 |
| `IN_RUN` | `t1 -> run` | `relations/T1_in_run.csv` | 13,772 | 0 |
| `IN_STUDY` | `t1 -> study` | `relations/T1_in_study.csv` | 13,772 | 0 |
| `IN_FORMAT` | `t1 -> data_format` | `relations/T1_in_format.csv` | 13,772 | 0 |
| `IN_LEVEL` | `t1 -> data_level` | `relations/T1_in_level.csv` | 13,772 | 0 |
| `IN_STUDY` | `t2 -> study` | `relations/T2_in_study.csv` | 86 | 0 |
| `IN_FORMAT` | `t2 -> data_format` | `relations/T2_in_format.csv` | 85 | 1 |
| `IN_LEVEL` | `t2 -> data_level` | `relations/T2_in_level.csv` | 75 | 11 |
| `SUBCLASS_OF` | `cohort -> cohort` | `reference/cohort_subclass.csv` | 24 | 0 |
| `DESCRIBES_FORMAT` | `data_format_row -> data_format` | 由 `reference/formats.csv` 确定性派生 | 29 | 0 |

悬空外键策略是 `skip_edge_and_report`：不创建 placeholder，不静默丢弃。1,269 条原行完整写入 manifest，verifier 将其加回往返数据集。

## 约束与索引

- 12 个唯一约束：上表每个标签的主键，名称为 `dg_<label>_<property>_unique` 的稳定变体。
- 12 个显式 RANGE 索引：`t1.study_accession, individual_accession, sample_accession, run_accession, strategy, physical_format`；`t2.study_accession, strategy, format`；`sample.study_accession, individual_accession`；`individual.study_accession`。
- Neo4j 还为唯一约束维护 12 个 owned RANGE 索引，并保留默认的 node/relationship LOOKUP 索引。已验证 26 个索引全部 `ONLINE`。

## 源表范围

verifier 往返 23 张实际导入/补充表。以下文件只进 source inventory，不进数据图：

- `project.csv/sample.csv/study.csv`：与 `entities/` 对应表字节相同的重复副本。
- `T2.1csv`：99 行旧版 T2；当前范围明确使用规范化 `entities/T2.csv` 86 行。
- `entities/tool.csv`、`relations/tool_*.csv`、`reference/function.csv`、`reference/tool_types.csv`：属于工具目录，由独立同步路径管理。

## 删除语义与隔离门禁

实现采用方案 A：在精确认证的隔离 database 中，分批删除带 `datagraph_managed=true` 且带本 schema 数据标签的节点，再全量重建。导入器在 schema、每批删除和每批写入前都检查：

1. `CALL db.info()` 的 ID 必须等于 `--expected-database-id`；
2. ID 不得出现在 `--forbid-database-id`，生产 ID 必须列入；
3. 目标库不得有任何工具目录标签；
4. 目标数据标签不得出现未受管节点；
5. 真正写入必须显式传入 dry-run 产生的 `--confirm-replace <snapshot_id>`。

已用 CSV 副本删除一个 T2 及三条关系实测：重导后 T2 从 86 变为 85，目标节点查询为 0，临时快照完整 verifier 仍为 0 实质差异；随后已恢复 canonical 快照。

## 与生产旧图的差异

- 沿用小写运行标签 `t1/t2/run/sample/individual/study/project/cohort`和 snake_case 属性。
- 修正所有当前 T1 `strategy`，新增 `file_path`，分开 `physical_format` 与 `semantic_format`，HRA000021 旧 BAM 不在默认 `t1` 范围。
- 将参考数据标签改为 `data_*`，避免工具目录 label collision。
- 不为 1,269 条悬空外键创建假实体；差异由 manifest 明示。
- 每个节点/关系具有确定性 snapshot 和源行 provenance，解决旧图无导入时间、版本和删除语义的问题。
