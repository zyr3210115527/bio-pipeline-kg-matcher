# 更新 7.28 后端数据包修复记录与待决策项

## 1. 处理范围与结论

本次检查对象为 `更新7.28.zip`，原始文件 SHA-256：

```text
85bc0e10d8e0d4feb6ec7d3847995c7c0bb79536f66660fb49f684d13461d94f
```

处理方式为复制后离线修复：未覆盖原压缩包，未连接或写入 Neo4j 7687/7688，也未执行清库、导入、约束或索引变更。

已生成 `更新7.28-确定性修复版.zip`。确定性数据问题已修复，但修复包当前仍不满足直接覆盖生产库的条件，主要阻断点是 Individual 主键建模、导入脚本与目标 schema 缺失，以及工具图不完整。

## 2. 已完成的修复

### 2.1 CSV 编码统一

**问题**

29 个业务 CSV 中，`entities/project.csv` 使用 GB18030/GBK 编码，其余文件主要为 UTF-8。若导入器统一按 UTF-8 读取，该文件可能解码失败或出现中文乱码。

**修改方法**

1. 每个 CSV 先尝试以 `utf-8-sig` 严格解码。
2. 解码失败时仅回退到 `gb18030`。
3. 使用 CSV 解析器读取字段和记录，不做字符串分行拼接。
4. 所有文件重新以无 BOM UTF-8 和标准 CSV 转义规则写出。

**结果**

- 30 个输出 CSV（29 个业务 CSV，加 1 个 diagnostics CSV）均可被严格 UTF-8 解码。
- CSV 列宽错误为 0。

### 2.2 语义格式词表统一

**问题**

Format 参考表和数据关系表使用了三组不同拼写，导致 5,346 条 `T2 -> Format` 关系找不到目标 Format 节点：

| 旧标识 | 统一后的标识 |
|---|---|
| `METADATA_SAMPLEINFO` | `METADATA_SAMPLE_INFO` |
| `MUTATION_ANNOTATION_FORMA_MAF` | `MUTATION_ANNOTATION_FORMAT_MAF` |
| `RNA_SPLICEJUNCTION_TAB` | `RNA_SPLICE_JUNCTION_TAB` |

**修改方法**

对以下位置做全局、精确的标识替换，而不是只改其中一张关系表：

- `reference/formats.csv`
- T1/T2 的 Format 关系
- Tool 的语义输入、语义输出关系
- `entities/tool.csv` 中分号分隔的语义输入和输出字段

共更新 45 处旧词表值。T2 表原本使用的 5,346 个正确拼写因此都能关联到统一后的 Format 节点。

**结果**

- 修复前：5,346 条 T2 Format 外键无法解析。
- 修复后：Format 外键错误为 0。

### 2.3 T1 完全重复记录去重

**问题**

`entities/T1.csv` 有 25,670 行，但只有 24,518 个唯一 `T1_id`。多出的 1,152 行是整行字段完全相同的重复记录。

**修改方法**

以 CSV 表头顺序组合整行签名，只有所有字段完全一致时才删除后出现的记录。没有按 `T1_id` 强制合并属性不同的行，也没有推断或覆盖字段。

**结果**

- 删除 1,152 条完全相同的重复行。
- 修复后 T1 为 24,518 行、24,518 个唯一 `T1_id`。
- 既有关系仍能解析到对应 T1。

### 2.4 清理确定无效的空记录

**修改内容**

- 从 `relations/T1_in_modal.csv` 删除 5 条 `T1_id` 为空的关系。
- 从 `relations/tool_relationship.csv` 删除 1 条尾部空行。

这些记录没有可恢复的主键或关系端点，保留只会造成导入失败或产生无意义记录，因此可以确定删除。

### 2.5 显式隔离包外关系

**问题**

两张关系表包含本包实体表中不存在的端点：

| 来源关系 | 数量 | 缺少的端点 |
|---|---:|---|
| `relations/T1_in_sample.csv` | 6,244 | Sample |
| `relations/sample_in_individual.csv` | 541 | Individual |
| 合计 | 6,785 |  |

当前约定允许跳过这些不在本次数据范围内的 T1/Sample/Individual，但若继续留在正式关系表中，导入器会静默漏关系或报告外键错误。

**修改方法**

1. 使用实体表主键集合逐行校验关系两端。
2. 端点齐全的记录保留在原关系表。
3. 端点缺失的 6,785 条记录移至 `diagnostics/out_of_scope_relations.csv`。
4. diagnostics 中保留来源文件、原行号、两端字段和值以及跳过原因，便于后续补数据后恢复。

**结果**

- 正式关系表外键错误为 0。
- 被跳过的数据没有丢失，也不会被误认为已经成功导入。

### 2.6 补回明确声明的 Individual-Study 关系

**问题**

`entities/individual.csv` 明确记录了 159 个额外的 `(individual_accession, study_accession)` 组合，但 `relations/individual_in_study.csv` 没有对应关系。

**修改方法**

从 Individual 实体表提取非空的 `(individual_accession, study_accession)` 对，与现有关系集合做差集，仅补入实体表已经明确声明的组合，不推测新的 Study 归属。

**结果**

- 补入 159 条 Individual-Study 关系。
- 修复后所有明确声明的 Study 成员关系都在关系表中有对应记录。
- 此修改只恢复成员关系，不解决下述 Individual 属性冲突。

## 3. 修复后校验结果

| 检查项 | 结果 |
|---|---:|
| 输出 CSV 数量 | 30（含 diagnostics） |
| UTF-8 解码错误 | 0 |
| CSV 列宽错误 | 0 |
| 空主键 | 0 |
| 关系外键错误 | 0 |
| T1 重复主键 | 0 |
| Individual 重复主键 | 159 |
| 压缩包完整性 | 通过 |
| 重复构建的 CSV 哈希 | 一致 |

`strict_import_ready` 当前仍为 `false`，唯一直接的数据主键原因是 159 个重复 Individual；此外还有 schema、导入脚本和工具图层面的阻断项。

## 4. 不能直接走、需要先判断的项目

### 4.1 Individual 应当使用什么身份键

**现状**

- `entities/individual.csv` 有 5,494 行、5,335 个唯一 `individual_accession`。
- 159 个 accession 同时出现在多个 Study。
- 其中 84 个在 `study_accession` 以外还存在临床或生存属性差异。
- 另外 75 个主要表现为 Study 归属不同，但仍会违反 accession 唯一约束。

**为什么不能自动修**

旧导入逻辑如果执行：

```cypher
MERGE (i:Individual {individual_accession: row.individual_accession})
SET i += row
```

后导入的记录会覆盖先导入记录的标量属性，最终结果依赖 CSV 行顺序。任意选择一行或合并字段都会改变临床数据语义。

**需要确定一种方案**

1. 推荐：用 `(study_accession, individual_accession)` 作为复合身份，每个 Study 保留独立 Participant/Individual 节点。
2. 将 Study 特异的临床、生存属性放到 `Individual-Study` 关系或独立 ClinicalRecord 节点。
3. 如果 accession 在业务上必须全局唯一，需要数据负责人指定 159 组中的权威记录及冲突字段处理规则。

在方案确定前，不能以 `individual_accession` 单键直接导入生产库。

### 4.2 7.28 包缺少配套导入契约

**现状**

压缩包只有 CSV，没有随包提供：

- 约束和索引脚本；
- 与 7.28 字段对应的实体、关系导入脚本；
- 重复导入或增量导入策略；
- 清理和回滚脚本；
- 导入后验证查询；
- schema/version/snapshot/provenance 定义。

当前 matcher 读取的是规范化结构，例如 `t2`、`files`、`file_path`、`snapshot_id` 和 `datagraph_managed`；原包字段则是 `T2_id`、`file_name`，也没有 snapshot/provenance 字段。

**需要判断**

- 是把 CSV 转换为现有规范化 schema，还是让 matcher 适配新的后端 schema。
- 节点标签大小写、主键、属性名和关系类型以哪一版为正式契约。
- 全量替换时如何校验和回滚，而不是直接删除生产数据库目录。

在 importer 和 schema 契约补齐前，不能沿用 7.27 脚本直接导入 7.28 数据。

### 4.3 工具图不能支撑 unrestricted workflow composition

**现状**

- Tool：39 个。
- NEXT：22 条。
- 无向连通分量：26 个。
- 孤立工具：25 个。
- 缺少 `tool_kind`、`decomposition_status`、输入输出 slot、`HAS_STEP` 等流程展开信息。

**确定不能直接走的边**

`GATK -> BCFtools` 当前不满足 artifact 契约：

- GATK 声明输出 `DNA_SOMATIC_SV_VCF`。
- BCFtools 声明输入 `DNA_VARIANT_VCF_GENERAL`。

在统一格式或增加显式兼容映射前，不能把这条边用于自动流程编排。

**需要生物学确认的边**

`fastp -> Cell Ranger` 不是可以默认推广的通用连接。Cell Ranger 对 10x FASTQ 的命名、read structure 和 barcode/UMI 有专门要求，常规 fastp 修剪可能破坏这些结构。需要明确该边只适用于什么输入和参数，否则应删除或增加条件约束。

**不能自动完成的工作**

不能根据工具名称或旧 WDL 为 25 个孤立工具、未拆解 pipeline 编造 NEXT、内部步骤或 slot。缺失拆解应由工具/流程提供方补齐。

### 4.4 数据路径不能直接标记为已验证

T2 中的物理路径主要位于 `/hpcdisk1/...`。当前检查环境没有挂载该存储，因此只能确认“CSV 中存在路径元数据”，不能确认：

- 文件真实存在；
- 文件可读；
- 文件大小与记录一致；
- FASTQ mate、样本和 Study 归属正确；
- 导入后的执行节点能够访问该路径。

建议在实际存储环境生成路径核验清单，至少记录 `exists/readable/size/checksum`。核验完成前，接口中的 `path_verified` 应保持 `false`。

### 4.5 可跳过但会限制检索覆盖率的数据

- 5,156 个唯一 T1 没有 Study 关系。
- 9,702 个唯一 T1 没有 Modal 关系。

按当前约定可以跳过，不作为本轮阻断错误；但这些 T1 不能用于带 Study 或组学条件的数据匹配，也不能被接口误报为已满足相应筛选条件。

## 5. 建议的放行顺序

1. 先确定 Individual 的身份键和 Study 特异属性模型。
2. 固化 Neo4j 标签、主键、属性名、关系类型和 schema version。
3. 编写与该 schema 一致的全量/增量 importer、约束、索引和回滚脚本。
4. 修复或条件化不满足输入输出契约的 NEXT 边，不补造未拆解流程。
5. 在隔离数据库导入修复包，执行节点数、关系数、唯一性、孤儿关系和代表性查询验证。
6. 在 `/hpcdisk1` 所在环境完成物理文件核验。
7. 隔离库全部门禁通过后，再制定生产切换方案；生产切换不应以直接删除数据库目录作为默认步骤。

## 6. 建议的最低验收门禁

只有同时满足以下条件，才建议标记为可导入生产：

- Individual 主键冲突为 0，或新 schema 明确支持 Study 维度的复合身份。
- 所有正式关系端点外键错误为 0。
- 所有 CSV 严格 UTF-8、列宽一致、主键非空。
- importer、constraints、indexes、validator 与同一 schema version 配套。
- 导入过程可重复执行，并有明确的幂等或替换策略。
- NEXT 边通过输入输出 artifact 兼容性校验。
- 未拆解工具不会被伪装成已经具有内部步骤的 pipeline。
- 数据路径状态区分“元数据存在”和“物理文件已验证”。
- 在隔离库完成导入、查询和回滚演练。

## 7. 修复产物

- 修复包：`更新7.28-确定性修复版.zip`
- 修复说明：`REPAIR_REPORT.md`
- 机器可读清单：`repair_manifest.json`
- 跳过关系明细：`diagnostics/out_of_scope_relations.csv`
- 可重复执行的修复脚本：`scripts/repair_update728.py`

