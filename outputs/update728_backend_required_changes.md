# 7.28 后端上线前必须修改清单

## 1. 适用范围

本清单基于以下实际交付物的离线检查结果：

- `neo4j-community-2026.06.0.zip`
  - SHA-256：`3fe51d1cc8188d531a97c7d5accdecd96f16c5a07fe136613571f36a05e908c1`
- `import.zip`
  - SHA-256：`0bfd7f56f55f67a0cfa3345598c034d1a96375000b668e0ae4ceb6e68b78346b`

目标是让数据图可以被 MCP 稳定读取、重复导入和验证。工具目录、精确输入输出 slot、Knowledge Card 和经审核的 NEXT 由 MCP 交付包管理，不以该后端中的旧 `Tool/NEXT_TOOL` 图作为执行真源。

## 2. 必须修改

### 2.1 统一 CSV 编码

**实际问题**

`import/entities/project.csv` 不能以 UTF-8 严格解码，实际为 GB18030/GBK。其他主要 CSV 是 UTF-8。Neo4j `LOAD CSV` 直接读该文件时可能报解码错误或导入乱码。

**必须修改**

- 将 `entities/project.csv` 转换为无 BOM UTF-8。
- 交付前对所有 CSV 做 UTF-8 严格解码检查。
- 不能只修改文件后缀或声明编码，必须实际重写字节。

**验收标准**

```text
所有 import/**/*.csv 以 UTF-8 严格解码成功，列数与表头一致。
```

### 2.2 明确 Individual 主键和冲突属性规则

**实际问题**

- `entities/individual.csv`：5,494 行、5,335 个唯一 `individual_accession`。
- 159 个 accession 同时存在多行。
- 部分重复行在 Study 以外的临床或生存属性上也不相同。
- 当前 `02_import_entities.cypher` 使用 `MERGE (i:Individual {individual_accession: ...}) SET ...`，后出现的行会静默覆盖先出现的行。

**必须修改**

数据提供方必须明确选择下列一种契约：

1. `individual_accession` 全局唯一：提供 159 组冲突的权威行，并说明被舍弃属性的处理规则；或
2. `(study_accession, individual_accession)` 是复合主键：导入脚本、Individual 节点和所有关系必须同步使用复合键。

不能继续使用“CSV 最后一行覆盖”作为上线规则。

**验收标准**

```text
每个 Individual 图身份唯一；重新排列 CSV 行后，导入结果不变。
```

### 2.3 不得静默丢弃关系

**实际问题**

- `T1_in_sample.csv`：6,244 条关系的 Sample 不在 `entities/sample.csv`。
- `sample_in_individual.csv`：541 条关系的 Individual 不在 `entities/individual.csv`。
- 当前 Cypher 使用两次 `MATCH` 后 `MERGE`，端点缺失时该行直接跳过，Browser 不会将其视为导入失败。

**必须修改**

二选一：

- 补齐缺失的 Sample/Individual 实体；或
- 将这 6,785 条关系从正式关系表移入 diagnostics，明确标记为 `out_of_scope`。

不接受继续保留在正式关系表中并依赖 `MATCH` 静默跳过。

**验收标准**

```text
正式 relations/*.csv 中每条关系的两端都存在；
若有范围外数据，diagnostics 中可逐行追溯。
```

### 2.4 统一语义格式标识

**实际问题**

T2 关系表中有 5,346 条格式关系无法匹配 `reference/formats.csv`：

| 参考表当前值 | 应统一为 | 影响行数 |
|---|---|---:|
| `RNA_SPLICEJUNCTION_TAB` | `RNA_SPLICE_JUNCTION_TAB` | 2,978 |
| `MUTATION_ANNOTATION_FORMA_MAF` | `MUTATION_ANNOTATION_FORMAT_MAF` | 2,355 |
| `METADATA_SAMPLEINFO` | `METADATA_SAMPLE_INFO` | 13 |

问题不是上表右列字符本身，而是关系表与参考表目前使用了不同拼写。

**必须修改**

- `reference/formats.csv`、T1/T2 Format 关系和 Tool 语义输入输出必须共用同一组值。
- 修改后不得依赖别名节点或两套 Format 节点表示同一语义。

**验收标准**

```text
T1/T2/tool 所有语义格式值都能在 reference/formats.csv 精确命中。
```

### 2.5 增加后端快照与导入证据

**实际问题**

当前节点没有统一的 `schema_version`、`snapshot_id`、源文件哈希或导入时间。MCP 可以识别标签和计数，但无法区分“正确的 7.28 数据”与“节点数相同的另一次导入”。

**必须修改**

导入结束时必须创建唯一快照节点，至少包含：

```cypher
(:BackendSnapshot {
  schema_version: 'update728/v1',
  snapshot_id: '<稳定值>',
  source_sha256: '<源数据包 SHA-256>',
  imported_at: '<ISO-8601 UTC>',
  entity_count: <实体数>,
  relationship_count: <关系数>
})
```

`snapshot_id` 必须由数据内容或发布版本确定，不能每次随机生成。

**验收标准**

```text
MATCH (s:BackendSnapshot) RETURN count(s), collect(s.snapshot_id)
结果为 1 个快照、1 个非空 snapshot_id。
```

### 2.6 修正导入验证脚本

**实际问题**

- `04_import_workflow_relations.cypher` 创建 `NEXT_TOOL {kind: ...}`。
- `05_validation.cypher` 却查询 `[:NEXT]`，因此即使导入成功也会返回 0 条。
- `05_validation.cypher` 还查询 `T1 -> Run -> Sample`，但 `01-04` 没有导入 Run 节点或 `IN_RUN`。

**必须修改**

- 验证脚本必须与实际导入的关系类型一致。
- 如果保留 `NEXT_TOOL`，则验证查询必须使用 `NEXT_TOOL`。
- 如果不导入 Run 层，必须删除 Run 链路验证；如果 Run 层是正式契约，必须补齐 Run 节点和关系导入。
- 验证必须输出“期望值、实际值、失败条件”，不能只返回 20 行样例。

### 2.7 上线导入必须有约束、索引和可重复执行入口

**实际问题**

`import.zip` 只有 `00-05` Cypher，`01-04` 没有在执行前创建必要的唯一约束和查询索引。直接在 Browser 粘贴大批量 `LOAD CSV + MERGE + MATCH` 无法提供稳定的失败恢复、执行日志和分段验收。

**必须修改**

- 在导入前创建与已确定主键一致的唯一约束。
- 为关系导入中使用的键创建索引。
- 提供一个按顺序执行、遇错停止、记录每段结果的导入入口；Browser 可作为人工调试方式，不作为唯一上线入口。
- `00_clear.cypher` 必须与正式导入分离，不得默认执行；所有 `DROP` 必须使用 `IF EXISTS`。

## 3. 无需修改

以下差异由 MCP 兼容层处理，不要为此额外改数据：

- T1 的 1,152 条完全相同重复行：可由 `MERGE`/适配层确定性去重。
- `T1_id` 与 `file_name` 分开：`T1_id` 作内部身份，`file_name` 作展示名。
- `T2_id` 与 `t2_id`、`T1/T2` 大写标签与 MCP 规范化标签的差异。
- `NEXT_TOOL` 关系名：MCP 会识别该关系，但工具执行合同仍以 MCP 包内已审核目录为准。
- `kind` 保持为关系属性：`order` 表示先后顺序，`data` 表示存在数据传递。不要将 `kind` 并入 Tool 实体表。
- 旧后端中的 39 个 `Tool` 节点可保留作数据提供方的信息图，MCP 不会将其直接视为可执行 slot 合同。

## 4. 工具图责任边界

为避免 `T01-T39` 与 MCP 现有 `T01-T23 + task pipeline` 的编号含义冲突，上线时按以下边界处理：

- 后端数据提供方负责：数据实体、数据关系、旧 Tool 信息图的可追溯导入。
- MCP 交付包负责：运行时 `tool_id`、`tool_kind`、slot、artifact、Knowledge Card、`HAS_STEP` 和经审核的 `NEXT`。
- 如果未来要让旧 39 工具图成为 MCP 执行真源，必须另行提供：稳定 `runtime_tool_id`、`tool_kind`、精确输入/输出 slot、必选性、artifact、物理格式，以及每条 `data` 边的 `output` 和 `input` slot 名。仅有 `tool_id,next_tool_id,kind` 不足以支撑执行级流程校验。

## 5. 最终交付验收结果

后端数据修改完成后，至少交付以下结果：

1. 源数据包 SHA-256。
2. 每张实体表和关系表的物理行数、唯一身份数。
3. 编码、CSV 列宽、空主键、重复主键、外键检查结果。
4. `BackendSnapshot` 查询结果。
5. 导入后各 label/关系类型计数。
6. 导入失败或跳过记录的 diagnostics，数量必须与源数据检查一致。
