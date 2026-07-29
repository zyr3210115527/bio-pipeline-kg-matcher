# 7.27 Neo4j 后端数据包接入评估与修改建议

评估原则：Neo4j 后端作为最终数据源。标签命名、属性命名、路径格式和 MCP 输出包装由接入层适配；数据事实、主外键、生物学语义和完成状态由后端保证。

本文将问题分成三类：

1. **后端必须修改**：数据事实、主外键、生物学分类或导入安全性存在问题，不能由接入层猜测。
2. **需要双方确认契约**：pipeline 完整度、Tool ID 和 NEXT 语义需要明确一个稳定合同。
3. **接入侧可以适配**：不影响数据真实性的 schema 形式和输出格式。

---

## 一、后端必须修改的问题

## 1. `project.csv` 不是严格 UTF-8

### 现象

`entities/project.csv` 严格 UTF-8 解码失败。第 7、8、9、12、15、16 行含 GBK 字节，主要是全角逗号等中文标点。用 GB18030 可以解码，其他 CSV 则是 UTF-8/ASCII。

### 为什么是问题

Neo4j `LOAD CSV` 需要能按 Unicode 正常解码输入文件。同一批导入文件混用 UTF-8 和 GBK，导入程序不会自动猜测单个文件的编码。

### 会导致什么

- Project 导入可能直接报编码错误。
- 如果导入流程未开启遇错即停，可能留下部分节点已导入、部分未导入的半成品图。
- 后续 `Study -> Project` 关系会因 Project 不存在而无法创建。

### 建议修改

将所有 CSV 统一转换为无损 UTF-8，发布前用严格 UTF-8 解码做自动检查。

---

## 2. 159 个 Individual 主键重复且属性冲突

### 现象

- `individual.csv` 有 5,494 行，但只有 5,335 个唯一 `individual_accession`。
- 159 个重复 accession 的 `study_accession` 全部存在冲突。
- 84 组还冲突 `survival_days`，个别记录冲突 `survival_time` 或 `pfs_time`。
- 例如 `HRI179847` 同时出现在 `HRA001748` 和 `HRA001749`。

### 为什么是问题

导入脚本使用：

```cypher
MERGE (i:Individual {individual_accession: individual_accession})
SET i.study_accession = row.study_accession, ...
```

`MERGE` 会把相同 accession 合并为一个节点，`SET` 则由 CSV 最后一行覆盖前面属性。但 `individual_in_study.csv` 使用的是第一个 Study。

因此导入完成后，159 个 Individual 会同时出现：

- 节点属性 `study_accession=HRA001749`
- `IN_STUDY` 关系却指向 `HRA001748`

### 会导致什么

- 通过节点属性和通过图关系查到两个不同答案。
- 按 Study 筛选生存、临床或组学数据时会串组。
- 后写入的生存值会静默覆盖前一条，无法追溯被覆盖内容。

### 建议修改

需要数据所有者确认：

- 如果是重复导出：保留正确的唯一行。
- 如果同一 Individual 确实属于多个 Study：不应在 Individual 上存一个单值 `study_accession`，而应使用多条 `IN_STUDY` 关系；生存字段也要明确是 Individual 级还是 Study 队列级。

这一项不能由接入层用“保留第一条”或“保留最后一条”代替，因为接入层无法判断哪个值是真实值。

---

## 3. T1、Sample、Individual 覆盖范围不同（已确认可按范围跳过）

### 现象

| 引用关系 | 无效行数 | 缺失的唯一父 ID |
|---|---:|---:|
| Sample -> Individual | 541 | 447 |
| T1 -> Individual | 5,156 | 1,324 |
| T1 -> Sample | 6,244 | 1,268 |

例如 `HRS023669` 引用 `HRI023669`，但 `individual.csv` 中没有 `HRI023669`。

后端已说明：T1 覆盖 19 套数据，Sample 覆盖 15 套数据，不同实体表的收录范围本来就不完全相同。在这个前提下，T1 找不到 Sample/Individual，或 Sample 找不到 Individual，**不再定性为原始数据错误**，可以按后端规则跳过这些跨范围关系。

### 为什么是问题

允许跳过本身没有问题，问题在于当前关系脚本使用：

```cypher
MATCH (s:Sample {sample_accession: row.sample_accession})
MATCH (i:Individual {individual_accession: row.individual_accession})
MERGE (s)-[:IN_INDIVIDUAL]->(i)
```

只要一端不存在，Neo4j 不会报错，而是整行静默跳过。如果不另外声明范围，接入方无法区分“预期的跨范围跳过”和“真实的外键漏数”。

### 会导致什么

- 541 个 Sample 不会具有 Individual 追溯，6,244 个 T1 不会具有 Sample 追溯；这是范围限制，不是导入失败。
- 如果 API 不暴露覆盖范围，使用者仍可能把“未收录 Individual/Sample”误解为“数据不存在”。
- 如果将范围跳过与真实字典/外键错误统计在一起，会让发布验证无法判断是否通过。

### 建议修改

不要强行补造 Individual/Sample 节点。建议将范围变成明确发布契约：

- 在 manifest 中写明 `T1=19 datasets`、`Sample=15 datasets`、Individual 的实际覆盖范围及 Study 列表。
- 关系 CSV 只输出两端都在当前发布范围内的关系；或者单独输出 `out_of_scope_relations.csv`。
- 验证报告将 `skipped_by_scope` 与 `invalid_reference` 分开计数。
- **T1 -> Study 不应依赖 Sample/Individual 是否收录**。T1 覆盖 19 套数据，即使中间的 Sample/Individual 不在 15 套表内，也应使用原始 Study/Experiment 元数据直接建立 `T1 -> Study`。

---

## 4. 580 个 Sample 与所属 Individual 的 Study 冲突

### 现象

- 570 个 Sample 的 `study_accession=HRA002693`，但所属 Individual 的 Study 是 `HRA006117`。
- 10 个 Sample 的 `study_accession=HRA002693`，但所属 Individual 的 Study 是 `HRA007413`。
- 例如 `HRS1008426 -> HRI769104`。

### 为什么是问题

在当前模型中，Sample 通过 `IN_INDIVIDUAL` 属于 Individual，Individual 通过 `IN_STUDY` 属于 Study。Sample 自己的 `study_accession` 应与该路径一致，否则同一个 Sample 存在两个不同的 Study 归属。

### 会导致什么

- 按 Sample 属性查询和按图关系查询返回不同 Study。
- 临床资料、RNA/WES 文件和队列信息可能被错误组合。
- 数据匹配结果可能将其他 Study 的样本当成用户指定 Study 的数据。

### 建议修改

根据原始 accession 表核对 Sample 和 Individual 的 Study。如果同一 Individual 可以出现在多个 Study，需在 schema 中明确建模这种多对多关系，不能同时保留互相冲突的单值属性。

---

## 5. 2,858 个 STAR RNA BAM 被错标为 DNA/WES

### 现象

2,858 个名为 `*Aligned.sortedByCoord.out.bam` 的 STAR 产物被标记为：

```text
semantic_format = DNA_GENOMIC_ALIGNMENT_BAM
strategy = WES
```

但同一类 STAR 文件在 `HRA001272` 的 430 条记录中正确标为：

```text
semantic_format = RNA_TRANSCRIPTOME_ALIGNMENT_BAM
strategy = RNA
```

该错误导致 2,548 个 run 同时拥有 RNA 和 WES 标签，5,096 个 T1 同时连到 `RNA` 和 `WES` Modal。

例如 `HRR025534`同时被声明产生：

- WES `DNA_GENOMIC_ALIGNMENT_BAM`
- RNA splice junction
- RNA fusion TSV

### 为什么是问题

`Aligned.sortedByCoord.out.bam` 是 STAR 的典型 RNA-seq 比对产物。同一 sequencing run 不应因为下游文件分类错误而同时被当成 RNA-seq 和 WES。这不是正常的“多组学样本”；多组学应由不同 assay/run 关联到同一样本，而不是让同一 run 同时具有两种 assay 身份。

### 会导致什么

- RNA-seq 数据可能被送入 WES/BWA/GATK 类流程。
- WES 数据筛选会夹带 STAR RNA BAM。
- agent 在自助组链时会得到生物学上错误的候选工具。
- 按 Modal 统计节点数会重复计数，RNA/WES 数量均不可信。

### 建议修改

重新根据生成工具、Study assay 和文件名综合判定这 2,858 个 BAM，不要仅根据 `.bam` 扩展名归为 DNA。修正 T2 后重新生成 T1 Modal 关系。

---

## 6. T1 的 Study 和 Modal 关系覆盖不完整

### 现象

在 24,518 个唯一 T1 中：

- 5,156 个没有 `IN_STUDY`。
- 9,702 个没有 `IN_MODAL`。
- 这 9,702 个 T1 同时没有任何 T2 下游产物。

### 为什么是问题

现有 T1 Modal 看起来主要是从 T2 的 strategy 反推生成。对于尚无下游产物的原始数据，反推方法无法得到 Modal。但原始 FASTQ 的 assay 应该来自 Study/Experiment 元数据，不应依赖是否已经产生 T2。

### 会导致什么

- 按 RNA/WES/scRNA Modal 查询时，9,702 个 T1 会被遗漏。
- “还没有分析过的原始数据”反而更容易没有 Modal，影响流程入口选择。
- 5,156 个 T1 无法稳定追溯到 Study。

### 建议修改

- T1 Modal 从 Experiment/Study 的实验策略生成，T2 strategy 只作一致性校验。
- 发布前检查每个 T1 至少有一个 Study 和一个 Modal，除非它被明确标为 unknown/unresolved。

---

## 7. Format 和 Modal 字典命名不一致

### 现象

T2 关系表使用的新名称与 Format 字典不一致：

| T2 使用 | Format 字典使用 | 影响行数 |
|---|---|---:|
| `RNA_SPLICE_JUNCTION_TAB` | `RNA_SPLICEJUNCTION_TAB` | 2,978 |
| `MUTATION_ANNOTATION_FORMAT_MAF` | `MUTATION_ANNOTATION_FORMA_MAF` | 2,355 |
| `METADATA_SAMPLE_INFO` | `METADATA_SAMPLEINFO` | 13 |

此外，T29、T30、T32、T33、T35、T39 的 Modal 写为 `RNA-seq`，而 Modal 字典只有 `RNA`。

### 为什么是问题

Neo4j 对字符串做精确匹配。虽然人可以看出这些名称表示同一概念，`MATCH (f:Format {format: row.semantic_format})` 不会自动识别别名。

### 会导致什么

- 5,346 条 T2 -> Format 边静默丢失。
- 6 条 Tool -> Modal 边静默丢失。
- 按 MAF、splice junction 或 metadata 格式检索数据时返回不全。
- Tool 输入语义和数据节点语义使用不同词，无法做正确的工具推荐。

### 建议修改

选定一套唯一标准名称。建议使用单词完整、语义清楚的：

- `RNA_SPLICE_JUNCTION_TAB`
- `MUTATION_ANNOTATION_FORMAT_MAF`
- `METADATA_SAMPLE_INFO`
- Modal 统一使用 `RNA`

然后同步更新 Format/Modal 字典、T1/T2 关系表、Tool 属性和 Tool relation CSV。

---

## 8. 导入时有 12,142 条关系不会创建，其中 6,785 条已确认为范围跳过

### 现象

对 18 张关系表按当前 Cypher 做端点匹配模拟：

| 类别 | 源行数 | 预计创建 | 静默丢失 |
|---|---:|---:|---:|
| 全部关系 | 339,176 | 327,034 | 12,142 |

按已确认的数据覆盖范围，需要拆成两类：

**已确认可跳过的跨范围关系：6,785**

- T1 -> Sample：6,244
- Sample -> Individual：541

**仍需修复的真实不一致：5,357**

- T2 -> Format：5,346
- Tool -> Modal：6
- T1 -> Modal 空 ID 行：5

### 为什么是问题

Neo4j `MATCH ... MATCH ... MERGE` 对不存在的端点不会主动报错。因此“Cypher 执行成功”并不等于“关系全部导入”。同时，不能将经过确认的范围跳过与真实的引用错误混为一个“丢失”指标。

### 会导致什么

- 如果不分类，验证会永远报 6,785 条“错误”，即使它们实际是产品范围设计。
- 反过来，如果简单允许所有 `MATCH` 未命中，5,357 条真实的 Format/Modal/空 ID 问题也会被一起忽略。
- 只抽查 `LIMIT 20` 无法区分这两种情况。

### 建议修改

关系导入前先做范围与外键校验：

- `skipped_by_scope=6,785` 作为发布 manifest 中的预期值，不作为失败条件。
- `invalid_reference` 必须为 0；当前 Format/Modal/空 ID 的 5,357 条应先修复。
- 导入后对每张关系表分别对账，不只检查总数。

---

## 9. T1/T2 主键约束仍使用旧字段

### 现象

新导入脚本使用：

- `T1.T1_id`
- `T1.run_accession`
- `T1.file_name`
- `T2.T2_id`

但 `constraints.cypher` 仍使用：

- `T1.runAccession`
- `T1.dataName`
- `T2.t2_id`

而且 `constraints.cypher` 与 7.17 版逐字节相同，还包含新包不再导入的 `Cohort` 和 `ToolType` 约束。

### 为什么是问题

Neo4j 属性名区分大小写，`T2_id` 和 `t2_id` 是两个不同属性。在一个节点上对不存在的旧属性建约束，不会保护真正的新主键。

### 会导致什么

- `T1_id` / `T2_id` 不受唯一约束保护。
- 重复节点、空主键或导入顺序问题无法在 schema 层阻止。
- 开发者看到“约束已创建”会误以为主键安全。

### 建议修改

至少改为：

```cypher
CREATE CONSTRAINT T1_id_unique IF NOT EXISTS
FOR (n:T1) REQUIRE n.T1_id IS UNIQUE;

CREATE CONSTRAINT T2_id_unique IF NOT EXISTS
FOR (n:T2) REQUIRE n.T2_id IS UNIQUE;
```

其他约束和索引也需要按新导入脚本实际设置的标签/属性重新生成，不要沿用旧文件。

---

## 10. 当前清库脚本存在“先删数据，后中途失败”的风险

### 现象

`00_clear.cypher` 的执行顺序是：

1. `MATCH (n) DETACH DELETE n`
2. 按写死的名称删除索引
3. 按写死的名称删除约束

名单中多数索引/约束名称与当前实例及新 schema 不一致，并且 `DROP` 没有 `IF EXISTS`。

### 为什么是问题

删节点是第一条语句，所以即使后面第二个 `DROP INDEX` 就报错，原数据也已经不可用。该流程也没有自动回滚。

同时执行物理 `rm -rf databases/neo4j` 和逻辑 `DETACH DELETE` 是重复操作。直接删数据目录还可能让 user database 与 `system` database 中的数据库记录不一致。

### 会导致什么

- 现库数据已删，新包又没有完整导入。
- schema 可能只删了一部分，导致下次导入继续受旧约束影响。
- 缺少可验证的回滚点。

### 建议修改

推荐使用“新实例导入 -> 验证 -> 切换连接”，保留旧实例回滚。如果必须原地替换，也要先使用 Neo4j 支持的 dump/backup 得到可恢复副本，再选择“数据库级替换”或“逻辑清理”其中一种，不同时使用两种方法。

---

## 11. `05_validation.cypher` 无法发现主要错误

### 现象

现有验证脚本主要是查节点数和 `LIMIT 20` 样例，另外只检查 T1/T2 是否缺 DataLevel。

### 为什么是问题

抽到 20 条正常数据，不能证明其余几万条数据的关系完整。当关系导入是静默跳过时，更需要全量对账。

### 会导致什么

即使导入后有 12,142 条关系未创建（其中 6,785 条是已确认的范围跳过，5,357 条是仍需修复的真实不一致），现有验证脚本仍可能只显示几组正常样例，既不能确认范围契约，也不能阻止真实错误发布。

### 建议修改

验证脚本至少加入：

- 每张实体表的源行数、唯一主键数、Neo4j 节点数对账。
- 每张关系表的唯一行数与 Neo4j 关系数对账。
- 空主键、重复主键、孤立节点、字典外值检查。
- schema 中约束/索引的实际属性检查。
- 任何数量不等应让发布失败。

---

## 12. Tool ID 在 7.17 -> 7.27 之间大规模改指

### 现象

- T01 `fastp` 和 T02 `FastQC` 保持不变。
- T03-T23 共 21 个旧 ID 全部改指其他工具。
- 例如 T11 从 `featureCounts` 变成 `RSEM`，T13 从 `diff_expr_go` 变成 `MultiQC`。

### 为什么是问题

ID 应表示稳定实体身份，而不是当前 CSV 中的行号。如果一个 ID 在新版本中变成另一个工具，旧记录不会显示“已失效”，而是被误解为另一个真实工具。

### 会导致什么

- 历史 pipeline 配方中的 T11 会从 featureCounts 静默变成 RSEM。
- agent 缓存、日志、MCP 输出、测试用例和外部关系全部可能串义。
- 无法对不同时间的运行结果做稳定追溯。

### 建议修改

如果 7.27 仍处于未对外发布阶段，可以把这次视为一次性重编号，但需要：

1. 提供 7.17 -> 7.27 ID 迁移表。
2. 从确定版本开始冻结 ID，已分配的 ID 不再复用给其他工具。
3. 新工具只分配新 ID，删除工具则保留 deprecated/tombstone 记录。

---

## 13. NEXT 中存在真实的输入输出契约冲突

### 现象

22 条 NEXT 中，按当前 `tool_has_semantic_input/output.csv` 做精确匹配，有 10 条没有任何共享格式。

其中 9 条是指向 MultiQC：MultiQC 输入写成 `DIRECTORY_UNCLASSIFIED`，而上游没有对应输出。这些在实际流程中可能合理，但图上缺少质控报告/日志契约。

另一条是：

```text
GATK output: DNA_SOMATIC_SV_VCF
BCFtools input: DNA_VARIANT_VCF_GENERAL
```

### 为什么是问题

GATK 的功能描述是 Mutect2 SNV/InDel，但输出却标成 SV（structural variant）。这不仅是字符串不相等，也是生物学语义不一致。

### 会导致什么

- 契约验证会拒绝 GATK -> BCFtools。
- 如果无视契约强制连接，可能将 SV 与 SNV/InDel 的处理流程混淆。
- MultiQC 边无法区分“数据传递”和“报告汇总依赖”。

### 建议修改

- 为 Mutect2 输出使用 `DNA_VARIANT_VCF_GENERAL`，或新增更准确的 `DNA_SOMATIC_SMALL_VARIANT_VCF`。
- 为 FastQC/fastp/STAR/SAMtools/GATK/BCFtools/SnpEff/RSEM 等建模质控报告或日志输出。
- NEXT 最好加 `kind=data|control|report`，只有 `kind=data` 必须满足 output -> input 契约。

---

## 14. NEXT 图覆盖不足，当前不能支撑全量自助组链

### 现象

- Tool：39
- NEXT：22
- 最大连通分量：14 个 Tool
- 完全孤立 Tool：25
- 39 个 Tool 最终形成 26 个互不连通的分量

featureCounts、fq_to_ubam、差异表达、富集、生存分析、突变景观等下游节点大量断开。例如 Tool 属性声明 featureCounts 可下游到 edgeR/DESeq2/limma，但 `tool_relationship.csv` 中 featureCounts 是终点。

### 为什么是问题

如果 Neo4j 是唯一工具编排数据源，agent 只能使用图中实际存在的边。Tool 属性中的中文逗号文本不能代替可查询、可验证的 NEXT 关系。

### 会导致什么

- 明明后端有某个 Tool，agent 却无法把它接入流程。
- 自助餐模式会在 featureCounts、Cell Ranger 等节点提前终止。
- 为了让 Demo 工作，接入层只能再硬编码一套 NEXT，最终产生两个互相不一致的真值源。

### 建议修改

现在工具还在持续拆分，不要为了看起来完整而猜测补边。建议每条边加：

- `status=reviewed|draft`
- `kind=data|control|report`
- `output_semantic_format`
- `input_semantic_format`
- `source`

对已确认的工具先补齐。未拆完的范围可以明确标为 work in progress，接入端不将 draft 边当成可执行/可展示流程。

---

## 15. 通用 trimming -> Cell Ranger 不应作为无条件 NEXT

### 现象

NEXT 中存在：

```text
fastp -> Cell Ranger
```

### 为什么需要谨慎

Cell Ranger 处理 10x FASTQ 时依赖固定的 read 结构、barcode/UMI 位置和命名规则。通用 fastp trimming/UMI 处理可能改变 read 长度或破坏 barcode/UMI 语义。

这不代表 fastp 在所有单细胞场景中都绝对不能用，而是它不应被表达为任意 paired FASTQ 到 Cell Ranger 的默认无条件路径。

### 会导致什么

- agent 可能默认对 10x FASTQ 先执行 fastp。
- barcode/UMI 结构可能被错误修剪。
- Cell Ranger 输入命名或 read 结构校验失败。

### 建议修改

删除该默认 NEXT，或将它标为需要 10x protocol/read-structure 条件审查的 draft/conditional 边。Cell Ranger 默认应直接使用符合 10x 要求的原始 FASTQ。

---

## 16. 当前 Tool 无法区分原子工具、完整 pipeline 和 task pipeline

### 现象

39 个 Tool 使用同一种节点形式，没有：

- `tool_kind=atomic|pipeline|task_pipeline`
- `status=complete|partial|draft`
- pipeline 有序步骤
- `HAS_STEP`

T25 `WGCNA` 和 T39 `wgcna` 在不区分大小写时同名，看起来分别代表原子方法与 pipeline 包装，但 schema 中没有说明二者层级。

### 为什么是问题

编排逻辑需要区分：

- **预制菜**：已审核的标准 pipeline，可展开固定步骤。
- **自助餐**：用原子工具和已审核 NEXT 自由组链。
- **task pipeline**：暂时仍以一个大任务形式存在，内部尚未完全拆分。

仅根据 tool name 猜测类型不稳定，特别是同名或语义重叠时。

### 会导致什么

- pipeline 可能被当成单个原子工具参与组链。
- 原子 WGCNA 和完整 wgcna pipeline 无法稳定区分。
- agent 无法知道哪些流程已经完整拆分，可能展示不存在的内部步骤。

### 建议修改

为 Tool 增加至少：

```text
tool_kind: atomic | pipeline | task_pipeline
decomposition_status: complete | partial | not_started
```

对完整 pipeline 增加有序步骤关系，例如：

```text
(pipeline)-[:HAS_STEP {order, step_id, depends_on}]->(atomic_tool)
```

尚未拆完的 pipeline 可以继续作为 `task_pipeline` 使用，不需要为了接入而虚构内部步骤。

---

## 二、需要双方确认的契约

## 17. 14 个标准 pipeline 与当前后端完成度

产品侧此前有“14 个标准 pipeline 优先作为预制菜”的设想，但已知当前完整拆分范围仍在持续更新，不能默认后端已经提供 14 个完整 recipe。

这里建议明确选择一种契约：

### 方案 A：后端当前只承诺已完成的 2 个 pipeline + 1 个 task pipeline

- 后端对这 2+1 个流程提供 `tool_kind`、完成状态和步骤。
- 接入端只将这些标记为已确认预制菜。
- 其他流程显示为 `work_in_progress`，不展示猜测的内部步骤。

### 方案 B：产品当前必须提供 14 个预制菜

后端至少需要提供一张机器可读配方表：

```text
pipeline_id
pipeline_name
status
ordered_tool_ids
depends_on
```

如果没有这张表，仅靠当前 22 条全局 NEXT 无法准确恢复 14 条标准流程。

建议采用方案 A：如实展示已完成的范围，不把旧 WDL 拆出的工具或接入层猜测的配方冒充为新 Neo4j 后端的正式流程。

---

## 18. T1/T2 主键是否应包含物理路径

当前 T1/T2 ID 主要使用：

```text
file_name::file_path
```

这会导致同一个数据从 `/mnt/...` 迁到 `/hpcdisk1/...` 后，节点 ID 也随之改变。这可能是每次发布都需要全量清库的原因之一。

建议双方确认：

- 如果 ID 表示数据逻辑身份：应使用 accession + data role 等稳定键，路径作为可变属性。
- 如果 ID 就是物理文件实例：需要明确迁移后是新实例，并提供 supersedes/moved_from 关系，否则无法追溯路径迁移。

---

## 三、接入侧可以迎合和适配的部分

下列内容不需要后端迁就当前接入实现，可以按后端原生 schema 修改接入层。

## 19. 标签和属性命名

接入层可以直接适配：

- `Tool` / `T1` / `T2` 大写标签
- `tool_id`、`tool_name`
- `T1_id`、`T2_id`
- `Format.format`、`Function.function`、`Modal.modal`
- `INPUT`、`OUTPUT`、`NEXT`、`GENERATED_FROM`

后端不需要为了兼容当前小写标签而再存一份重复节点。

## 20. 不要求后端保留当前接入专用属性

当前接入层曾使用 `source_row_json`、`datagraph_managed`、`snapshot_id` 等字段重建 CSV 逻辑。如果后端原生节点属性已经稳定，接入层可改为直接查询，不要求后端添加这些历史适配字段。

但建议保留一个发布级 `snapshot_id/schema_version`，用于确认当前连接的是哪个后端版本。

## 21. MCP/agent JSON 输出格式

后端可以继续提供 Neo4j 原生节点和关系。接入层负责将：

- Tool 属性
- `INPUT/OUTPUT` Format
- NEXT
- pipeline step
- T1/T2 数据资产

转换为 agent 期望的 MCP JSON，后端不需要直接存储最终 JSON 展示结构。

## 22. 数据路径和参数分工

- `/hpcdisk1/...` 可作为后端权威路径，接入层将其视为不透明路径，不要求改成本机路径。
- `file_path=NOT_FOUND` 将被视为数据资产缺失。
- 流程运行参数不影响编排状态；接入层只负责展示流程，不要求后端在当前接口中补齐执行参数。

但如果需要声明数据“实际可用”，后端最好补一个 `path_status/path_verified`，因为仅有一串路径不等于文件已在存储上存在。

## 23. 查询模板可以由接入侧重写

7.27 包里的 28 个 query template 仍是 7.17 旧 schema，使用 `Data`、`Cohort`、`ToolType`、`NEXT_TOOL`、`toolName` 等新包不存在的元素。

如果这些模板也是后端对外交付的一部分，则应由后端同步修正；如果它们只是历史参考文件，接入层可以不使用，直接按新 schema 维护参数化 Cypher。

---

## 四、建议优先级

## P0：导入前必须修正

1. `project.csv` 统一 UTF-8。
2. 处理 159 个 Individual 冲突。
3. 将 T1=19 套、Sample=15 套及 Individual 的覆盖范围写入 manifest，将 6,785 条跨范围关系显式标记为 `skipped_by_scope`，不补造父节点。
4. 为所有 T1 直接建立 Study 归属，不依赖 Sample/Individual 是否在发布范围。
5. 核对 580 个 Sample/Individual Study 冲突。
6. 修正 2,858 个 STAR BAM 的 RNA/WES 分类。
7. 统一 Format/Modal 字典命名。
8. 重新生成正确的 T1/T2 约束。
9. 替换当前危险的清库/导入流程。
10. 导入对账中 `invalid_reference=0`，同时单独报告预期的 `skipped_by_scope`。

## P1：对外接入前需要确认

1. Tool ID 一次性迁移表与后续冻结规则。
2. `tool_kind` 和 `decomposition_status`。
3. 当前正式支持的 pipeline 列表和步骤。
4. NEXT 中 data/control/report 语义及契约。
5. 稳定的 `schema_version` 和 `snapshot_id`。

## P2：可以后续优化

1. 将 `size` 统一为整数 `size_bytes`。
2. 清理 T1 的 1,152 个完全重复行。
3. 删除 T2 中 `.swp` 临时文件，修正 63 个 `0.xlsx/0.tsv/0.xls/0.maf` 格式值。
4. 将 Individual 中全列 `NOT_FOUND` 的属性改为 null/不设属性。
5. 增加发布 manifest、CSV checksum、schema 说明和变更日志。

---

## 五、建议的交付验收标准

下一版数据包满足以下条件后，可开始按新 Neo4j schema 做全量接入：

- 所有 CSV 严格 UTF-8。
- 所有实体主键无冲突，或重复已按明确的多对多模型表达。
- 发布范围内的所有关系端点存在，`invalid_reference=0`；跨范围关系不进入正式关系 CSV，或以 `skipped_by_scope` 单独报告。
- T1/T2/Tool 使用同一套 Format/Modal 字典名称。
- 同一 run 不会因错分类同时成为 RNA 和 WES。
- `T1_id` / `T2_id` 有真正有效的唯一约束。
- Tool ID 及 schema version 已稳定。
- 后端明确给出已完成 pipeline、task pipeline 和 atomic tool 范围。
- 已完成 pipeline 可查到有序步骤，原子工具可查到输入输出语义。
- 在独立 Neo4j 实例完成试导和数量对账，不需要在现库原地试错。

建议职责边界：**Neo4j 后端负责事实、身份、关系和完成状态；接入层负责 schema 查询适配、MCP JSON 转换、LLM 路由和流程展示。**
