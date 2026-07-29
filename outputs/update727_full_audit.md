# 7.27 Neo4j 数据包全量审计

审计对象：`更新7.27.zip`

- 外层 ZIP SHA-256：`66c90f25d6e08a9061f45fea381825f9c78f9ad2aecfefbafac4ecb53aa18a55`
- 内层 `data.zip` SHA-256：`0e0ba3374e8bca398daaa8fa1f1cbf4429ec05a880b1a9fb9b872e2532eaeb45`
- 审计方式：只读静态检查、CSV 解析、主外键与关系模拟、Cypher/schema 对照、工具契约与 NEXT 生物学检查
- 未执行任何 Neo4j 删除或导入

## 总体结论

该包是一次大规模全量替换，不是小型增量更新。ZIP 本身没有 CRC 损坏，29 个 CSV 的列数基本规整；但数据、schema、查询模板和当前运行时之间存在多处阻断性不一致。

**当前版本不应清空现有 Neo4j 后直接导入。**

## 阻断性问题

### B01. `project.csv` 不是 UTF-8

Neo4j `LOAD CSV` 要求可正常解码的 Unicode 文本。`entities/project.csv` 严格 UTF-8 解码失败，第 7、8、9、12、15、16 行含 GBK 字节（主要是全角逗号等）。用 GB18030 可解码，说明是单文件编码混用，不是 CSV 列错位。

影响：项目实体导入可能在第一张表就终止。

### B02. 清库脚本会先删数据，再因旧 schema 名称失败

`00_clear.cypher` 先执行 `MATCH (n) DETACH DELETE n`，之后按写死的名称删索引和约束。名单中多数名称在新 schema 和当前实例中都不存在，且没有 `IF EXISTS`。

影响：最危险的失败形态是“节点已经删完，脚本在第二个 DROP 中止，schema 只清了一部分”。

### B03. 约束文件没有随新字段更新

`constraints.cypher` 与 7.17 版逐字节相同，但新导入已改用新字段。

- T1 导入使用 `T1_id` / `run_accession` / `file_name`，约束却使用 `runAccession` / `dataName`。
- T2 导入使用 `T2_id`，约束使用 `t2_id`。
- 仍然创建新包不导入的 `Cohort` 和 `ToolType` 约束。
- 没有对真正的 `T1.T1_id` 和 `T2.T2_id` 建唯一约束。

影响：脚本看似创建了约束，实际没有保护新主键。

### B04. 新包和当前 Demo 的 Neo4j schema 不兼容

新包导入 `Tool` / `T1` / `T2`，当前运行时读取 `tool_id` / `io_slot` / `artifact_type` / `t1` / `t2`，并依赖：

- `catalog_id`、`tool_kind`
- `HAS_INPUT_SLOT`、`HAS_OUTPUT_SLOT`
- `REQUIRES`、`PRODUCES`、`ALLOW_FORMAT`
- pipeline `HAS_STEP`
- `snapshot_id`、`datagraph_managed`、`source_row_json`

新包不提供这些标签、属性和关系。如果清库后导入，当前程序会读到 0 个可编排工具，数据匹配器也无法识别新 T1/T2。

### B05. 28 个查询模板全部沿用旧 schema

`cypher/query_temlpates` 与 7.17 版逐字节相同。28/28 个 `.cypher` 仍使用新包不存在或已改名的元素，包括：

- `Data`、`Cohort`、`ProcessingStage`、`ToolType`、`MultiOmics`、`Platform`
- `NEXT_TOOL`、`USES_TOOL`、`DERIVED_FROM`、`BELONG_TO`
- `toolName`、`toolId`、`Format.name`

新 schema 实际使用 `NEXT`、`tool_name`、`tool_id`、`Format.format` 等。`find_workflow_end_tools.cypher` 还有方向判断写反和未绑定变量 `Tool` 的问题。

## 实体表问题

### D01. T1 含 1,152 个完全重复行

- 总行数：25,670
- 唯一 `T1_id`：24,518
- 重复主键组：1,152
- 重复行属性完全相同

影响：`MERGE` 会合并为 24,518 个节点，不会产生属性冲突，但说明上游导出重复，且行数不等于导入后节点数。

### D02. Individual 含 159 个冲突主键

- 总行数：5,494
- 唯一 `individual_accession`：5,335
- 159 个重复 accession 全部存在 `study_accession` 冲突
- 84 组同时冲突 `survival_days`
- 1 组冲突 `survival_time`
- 1 组冲突 `pfs_time`

`MERGE + SET` 会由文件最后一行覆盖节点属性，而 `individual_in_study.csv` 选的是第一个 Study。导入后将有 159 个 Individual 的 `study_accession` 属性和 `IN_STUDY` 边互相矛盾。

示例：`HRI179847` 的关系指向 `HRA001748`，但最终属性会变成 `HRA001749`。

### D03. 实体表覆盖范围不同（已确认可按范围跳过）

- 541 个 Sample 行引用了不存在的 Individual，涉及 447 个 accession。
- 5,156 个 T1 行引用了不存在的 Individual，涉及 1,324 个 accession。
- 6,244 个 T1 行引用了不存在的 Sample，涉及 1,268 个 accession。

示例：`HRS023669 -> HRI023669` 的 Individual 不在 `individual.csv`。

后端已说明 T1 覆盖 19 套数据，Sample 覆盖 15 套数据，不同实体表不要求完全等范围。因此 T1 -> Sample、Sample -> Individual 等跨范围关系可以跳过，不应强行补造节点。但发布应明确给出每张实体表覆盖的 Study 列表，并将 `skipped_by_scope` 与真实的 `invalid_reference` 分开统计。

另外，T1 覆盖 19 套数据，所以 T1 -> Study 应独立于 Sample/Individual 的收录范围生成，不应因中间实体缺席而一起跳过。

### D04. 580 个 Sample 的 Study 与所属 Individual 冲突

- 570 个 Sample 写为 `HRA002693`，但 Individual 写为 `HRA006117`。
- 10 个 Sample 写为 `HRA002693`，但 Individual 写为 `HRA007413`。

示例：`HRS1008426 / HRI769104`。

需要由数据所有者确认是 Sample 的 Study 写错，还是 Individual 被复用到多 Study。如果是后者，当前“Individual 只有一个 `study_accession`属性”的 schema 不成立。

### D05. 2,858 个 STAR RNA BAM 被标成 DNA/WES

2,858 个名为 `*Aligned.sortedByCoord.out.bam` 的 STAR 产物被标记为：

- `semantic_format=DNA_GENOMIC_ALIGNMENT_BAM`
- `strategy=WES`

同一种文件在 `HRA001272` 的 430 行却正确标为 `RNA_TRANSCRIPTOME_ALIGNMENT_BAM / RNA`。

直接后果：

- 2,548 个 run 同时被标为 RNA 和 WES。
- 5,096 个 T1 同时建立 `IN_MODAL -> RNA` 和 `IN_MODAL -> WES`。
- 例如 `HRR025534` 同时生成 WES BAM、RNA splice junction 和 RNA fusion 结果。

这不是可接受的“多组学”表达；同一 sequencing run 的 assay 不应因下游文件误分类而同时成为 RNA/WES。

### D06. T1 的 Study/Modal 关系覆盖不全

- 24,518 个唯一 T1 中，5,156 个没有 `IN_STUDY`。
- 9,702 个没有 `IN_MODAL`。
- 这 9,702 个 T1 同时没有任何 T2 下游产物，说明 modal 是从 T2 反推而来，而不是从原始测序实验元数据来。

影响：按 RNA/WES/scRNA 检索原始数据时，会遗漏这 9,702 个 T1。

### D07. 498 个 T1 同时连到两个 Study

这些 T1 主要同时连到 `HRA001748` 和 `HRA001749`，但物理路径仍在 `HRA001748` 目录。这可能是研究复用，也可能是重复导出；必须结合 Individual 冲突一起确认，不应由 CSV 行顺序决定。

### D08. 一个成对 FASTQ 的 R1 被错标为单端

`HRR025534_f1.fq.gz` 被标为 `RAW_SINGLE_END_FASTQ`，但同一 run 存在 `HRR025534_r2.fq.gz` 并标为 `RAW_PAIRED_END_R2_FASTQ`。R1 应改为 `RAW_PAIRED_END_R1_FASTQ`。

### D09. 8,926 个 T1 没有物理路径

- `file_path=NOT_FOUND`：8,926/25,670 行
- 其中全部 1,016 个 `UNMAPPEDBAM` 都是 `NOT_FOUND`
- 4,516 个无路径 T1 仍被声明为 T2 的上游来源；另有 4,410 个无路径 T1 没有任何下游 T2

这不一定是 lineage 错误，但这些数据不应被当成当前可用资产。包内没有 `path_verified` 或文件 checksum，本机也没有 `/hpcdisk1` 挂载，因此其他 16,744 个 T1 和 38,011 个 T2 路径只能判定为“格式上是绝对路径”，不能确认物理存在。

### D10. ID 把物理路径当成主键的一部分

T1/T2 主键主要使用 `file_name::file_path`。当路径从 `/mnt/...` 迁到 `/hpcdisk1/...` 时，同一数据会变成新 ID，而不是更新一个可变属性。

这是每次更新都要求“全量清库”的重要根源。建议主键改用稳定的 accession + data role，路径单独作属性。

### D11. T2 物理格式提取错误和临时文件混入

- 63 个 study-level 文件的 `format` 被写成 `0.tsv` / `0.xlsx` / `0.xls` / `0.maf`，显然把版本号 `1.0` 的小数部分当成扩展名。
- 64 个 study-level 文件的 `sub_file_name=N/A`，虽然 `file_name` 有值，但字段语义不统一。
- T2 第 32,567 行包含 Vim 临时文件 `.HRA007167-Genes-FPKM-1.0.tsv.swp`，不应进入数据图。
- 3 个 T2 ID 不符合其他行的 `basename::path` 规则。

### D12. Individual 中 11 列全表都是占位值

包括 `hsct`、`tmb_status`、`fraction_genome_altered`、`data_tier`、`analysis_pipeline`、三个血常规字段、`karyotype_subtype`、`gene_fusions`、`risk_stratification`。

这些列不会直接阻断导入，但导入后会为每个节点存储无信息量的 `NOT_FOUND`。建议转为 null 或不设属性。

### D13. `size` 不是可计算数值

- T1 用 `123456 bytes`
- T2 混用 `KB` / `MB` / `GB`
- Cypher 直接作为字符串保存

影响：无法正确做总量、范围和排序查询。建议增加整数 `size_bytes`，展示单位另行生成。

## 关系表导入模拟

Neo4j 脚本对关系使用 `MATCH ... MATCH ... MERGE`。只要任一端不存在，该行不报错，而是静默跳过。

| 关系 CSV | 源行数 | 预计创建 | 静默丢失 |
|---|---:|---:|---:|
| individual_in_study | 5,335 | 5,335 | 0 |
| sample_in_individual | 8,640 | 8,099 | 541 |
| study_in_project | 19 | 19 | 0 |
| T1_in_sample | 24,518 | 18,274 | 6,244 |
| T1_in_study | 19,860 | 19,860 | 0 |
| T1_in_format | 24,518 | 24,518 | 0 |
| T1_in_level | 24,518 | 24,518 | 0 |
| T1_in_modal | 19,917 | 19,912 | 5 |
| T2_generated_from_T1 | 59,570 | 59,570 | 0 |
| T2_in_study | 38,011 | 38,011 | 0 |
| T2_in_format | 38,011 | 32,665 | 5,346 |
| T2_in_level | 38,011 | 38,011 | 0 |
| T2_in_modal | 38,011 | 38,011 | 0 |
| tool_has_function | 39 | 39 | 0 |
| tool_has_semantic_input | 70 | 70 | 0 |
| tool_has_semantic_output | 54 | 54 | 0 |
| tool_relationship | 22 | 22 | 0 |
| tool_suitable_for_modal | 52 | 46 | 6 |
| **合计** | **339,176** | **327,034** | **12,142** |

根据后端确认的覆盖范围，这 12,142 条不应全部定性为错误：

- **6,785 条是可接受的 `skipped_by_scope`**：T1 -> Sample 6,244，Sample -> Individual 541。
- **5,357 条仍是需要修复的真实不一致**：T2 -> Format 5,346，Tool -> Modal 6，T1 -> Modal 空 ID 5。

### R01. 5,346 个 T2 Format 边因名称不一致丢失

- `RNA_SPLICE_JUNCTION_TAB`：2,978；字典是 `RNA_SPLICEJUNCTION_TAB`
- `MUTATION_ANNOTATION_FORMAT_MAF`：2,355；字典是 `MUTATION_ANNOTATION_FORMA_MAF`
- `METADATA_SAMPLE_INFO`：13；字典是 `METADATA_SAMPLEINFO`

建议采用带完整单词的新拼写作为唯一标准，同步更新 Format 字典、Tool 属性和 tool relation CSV。

### R02. 6 个 Tool Modal 边丢失

T29、T30、T32、T33、T35、T39 使用 `RNA-seq`，Modal 字典只有 `RNA`。

### R03. T1 modal 关系含 5 个空 ID 占位行

`T1_in_modal.csv` 最后含只写 Modal、没有 T1/run 的 WES、Clinical、Meta、RNA、sc-RNA 行。这些不会创建边，应删除。

## 工具目录与 NEXT 问题

### T01. Tool ID 不具有版本稳定性

7.17 到 7.27：

- T01 `fastp` 和 T02 `FastQC` 未变。
- T03-T23 共 21 个已有 ID 全部改指其他工具。
- 例如 T11 从 `featureCounts` 变成 `RSEM`，T13 从 `diff_expr_go` 变成 `MultiQC`。

任何保存 Txx ID 的 agent 计划、缓存、日志、pipeline 配方和外部关系都会发生语义错配。应保持 ID 永久稳定，新工具只分配新 ID，或提供明确迁移表。

### T02. 39 个 Tool 没有 pipeline/atomic 类型

T29-T39 看起来是 11 个原 WDL/pipeline 级工具，T01-T28 更像原子工具，但新数据没有 `tool_kind`、pipeline 标识、步骤或 `HAS_STEP`。

影响：agent 无法从图谱分辨“预制菜”与“自助餐原子工具”，也无法展开 14 个标准 pipeline 的标准流程。

### T03. NEXT 图覆盖严重不足

- Tool：39
- NEXT：22
- 最大连通分量：14 个 Tool
- 完全孤立 Tool：25
- 起点只有 `fastp` 和 `Trim Galore`
- 终点只有 `Cell Ranger`、`featureCounts`、`MultiQC`、`WGCNA`

所有 T29-T39 的 pipeline 级 Tool 都是孤立节点。`fq_to_ubam`、差异表达、富集、生存、突变景观等都无法通过 NEXT 图编排。

### T04. 22 条 NEXT 中 10 条不满足当前输入输出契约

9 条是指向 MultiQC 时的报告契约缺失：MultiQC 输入被写成 `DIRECTORY_UNCLASSIFIED`，而上游没有输出这个类型。这些步骤在实际生信流程中可能合理，但图契约不支持。

另一条是实质性冲突：

- GATK 输出 `DNA_SOMATIC_SV_VCF`
- BCFtools 输入 `DNA_VARIANT_VCF_GENERAL`

同时 GATK 的功能描述是 Mutect2 SNV/InDel，但输出语义却写成 SV（structural variant），应改为通用/体细胞小变异 VCF 或新增准确的语义类型。

### T05. 数个工具的生物学契约过于宽泛或不准确

- `fastp -> Cell Ranger` 不应做成无条件默认边。10x read 结构、barcode/UMI 和 Cell Ranger FASTQ 命名都有专用契约，通用 trimming 可破坏这些信息。
- fastp/Trim Galore 输出仍标成 `RAW_*_FASTQ`，没有 clean/trimmed FASTQ 类型，图上无法区分原始与清洗后数据。
- FastQC/fastp/MultiQC 的质控报告被归入 `DNA_VARIANT_STATS_REPORT`，这个类型名对 RNA/scRNA 也不合适。
- STAR 的 RNA 基因组比对 BAM 被同时建模为 `DNA_GENOMIC_ALIGNMENT_BAM`，容易再次引入 RNA/DNA 串线。
- featureCounts 需要基因组坐标 BAM + GTF；现有 `RNA_TRANSCRIPTOME_ALIGNMENT_BAM` 描述同时混用“基因组”和“转录组坐标”，需要拆分。

### T06. 工具语义重复且无法区分层级

- T25 `WGCNA` 与 T39 `wgcna` 大小写后同名。
- T27/T31、T21/T36、T23/T38 等分别是原子方法与 pipeline 包装的语义重叠，但没有类型字段说明层级。
- Tool 属性中声明了很多下游，但 `tool_relationship.csv` 没有对应边。例如 featureCounts 声明 edgeR/DESeq2/limma，但实际 NEXT 图中 featureCounts 是终点。

## 包结构和验证问题

### P01. 7.27 删掉了 7.17 包中的导入和 CSV 验证脚本

7.17 包含 `import_runner.py`、`validate_csv.py`、`run_import.sh` 和 PowerShell 脚本；7.27 只留下 Cypher 和内层 ZIP，没有导入顺序说明、失败中止策略和自动验证入口。

### P02. `05_validation.cypher` 不能发现上述主要错误

现有验证只做了：

- 节点数样例
- 20 行 T1/Sample/Study 样例
- 20 行 lineage 样例
- 20 条 NEXT 样例
- 缺 DataLevel 检查

它不检查重复主键、属性冲突、缺失关系、Format/Modal 字典不匹配、NEXT 契约、预期数量或 schema 状态。因此即使大量边静默丢失，该脚本仍可以看起来“验证通过”。

### P03. 发布工程信息不完整

- 没有 release manifest、schema version、snapshot ID、数据来源说明、CSV checksum 或旧新 ID 迁移表。
- 外层 ZIP 的中文目录名未正确标记 UTF-8，`unzip` 列表显示乱码，某些 Linux/CI 工具链会遇到路径问题。
- 所有归档文件权限是 `rw-rw-rw-`，不应作为发布默认权限。
- 目录名 `query_temlpates`、文件名 `reconmend_*`、`hierachy` 均有拼写错误。
- `maintenance/` 是空目录。

## 非错误但需要明确的数据范围

- 4,570 个 T2 没有 `GENERATED_FROM T1`，并且 `run_accession` 为空。其中包括 study-level MAF、VCF、Clinical、Meta 等数据。如果它们是外部导入的队列成果，没有 T1 边可以接受；但应有明确的 provenance/source 类型，不应与“lineage 缺失”混在一起。
- T2 中 26,129 个产物由成对 R1/R2 两个 T1 生成，7,312 个由单个 T1 生成，这一基数分布本身合理。
- 29 个 CSV 除 `project.csv` 编码外，均能按声明列数解析，没有普遍性 CSV 引号/列错位。

## 建议修复顺序

1. **先冻结清库操作**：保留现有实例作为回滚。
2. **确定唯一目标 schema**：新包必须在 `Tool` 方案和当前 `tool_id/io_slot/artifact_type` 方案之间二选一，或提供完整迁移层。
3. **修阻断性数据**：UTF-8、Individual 冲突、RNA/WES 错标、Format/Modal 字典；对 T1/Sample/Individual 的范围差异建立明确 manifest，不强行补造父节点。
4. **修 schema 和 ID**：真正的 T1/T2 唯一约束，稳定 Tool ID，稳定数据 ID，增加 schema/snapshot version。
5. **补齐 pipeline 结构**：明确 pipeline vs atomic，补 `HAS_STEP`、slot、artifact contract，再补 NEXT。
6. **重写 28 个 query template 和 validation**：验证必须以“预期数量 = 实际数量”为准，不能只抽样 `LIMIT 20`。
7. **在独立 Neo4j 实例试导**：完成节点/关系/schema/应用查询验收后，再切换连接，不在现库原地试错。

## 验收底线

修订包至少应同时满足：

- 全部 CSV 严格 UTF-8、主键无冲突。
- 发布范围内的关系端点全部存在，`invalid_reference=0`；跨范围关系以 `skipped_by_scope` 单独报告。
- T1/T2/Tool 语义类型只使用字典中的唯一标准拼写。
- 同一 run 不因错分类同时成为 RNA 和 WES。
- 每条“数据传递型” NEXT 至少有一个上游 output 与下游 input 契约匹配；控制/报告边必须显式标类型。
- 14 个标准 pipeline 具有可查询的标识和步骤，原子工具具有 slot/artifact contract。
- 运行时健康查询、数据匹配查询、预制菜展开和自助餐组链都能在新实例返回非空结果。
