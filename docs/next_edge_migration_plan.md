# NEXT 边改造方案 + 数据图只读探查

> 状态：只读方案，未实施任何代码/CSV/Neo4j 修改，未运行 `sync_neo4j_tool_catalog.py --apply`。
> 时间戳：2026-07-23。
> 仓库：`bio-pipeline-kg-matcher`。

---

## 0. 定位与环境

执行命令：

```bash
pwd && ls
git log --oneline -10 && git status
```

结果：

- 工作目录 `/Users/zhouyiran/Documents/可选`，项目根目录 `bio-pipeline-kg-matcher`。
- `docs/` 下存在 `paired_sample_probe.md`、`neo4j_next_relationship_review.md` 等。
- Git 仓库当前 `main` 分支尚未有任何 commit，因此 `git log` 失败；`git status` 显示大量未跟踪文件（与项目当前状态一致）。

关键文件定位：

- `workflow_composer.py`（2275 行）
- `pipeline_router.py`（1682 行）
- `data/csv/relations/tool_relationship.csv`
- `scripts/python/sync_neo4j_tool_catalog.py`
- `scripts/python/validate_csv.py`
- `neo4j_observability.py`
- `tests/test_workflow_composer.py`

Neo4j 状态：

- 首次裸连返回 `not_configured`，因为未加载 `.env.local`。
- 通过 `workflow_composer.initialize_runtime()` 加载环境后，Neo4j 可正常连接（版本 `2026.06.0`，节点 34838，关系 81234）。
- 工具图：`24` 个 tool 节点，`21` 条 `NEXT {source:'curated-next-csv'}` 边，与 CSV 真源一致。

测试基线：

```bash
.venv/bin/python -m unittest discover -s tests
# Ran 63 tests, OK (skipped=3)
```

---

## 1. 项目是什么（摘要）

自然语言 → 生信工作流编排器。系统只做：意图理解、流程选择/组链、结构校验、数据资产匹配，不执行任何生信任务。

核心约束：

- Neo4j 是工具目录唯一运行时真源；
- LLM 只能从 12 个 atomic tool 闭集组链；
- `from`/`depends_on` 衔接必须存在于 curated NEXT 边集；
- 当前 `from` 绑定挂在单个 input 下，需同时满足 artifact 相等（除 `ARTIFACT_COMPATIBILITY` 唯一例外）和 NEXT 边存在。

---

## 2. 主任务：NEXT 边改造

### 2.1 现状

21 条 curated NEXT 边真源为 `data/csv/relations/tool_relationship.csv`（CSV 解析后确认无 `\r` 残留）：

```text
fastp       → fastqc, bwa, star, multiqc
fastqc      → bwa, trim_galore, multiqc
bwa         → samtools
samtools    → gatk, featurecounts, multiqc
gatk        → bcftools, multiqc
bcftools    → snpeff
trim_galore → star
star        → rsem, samtools, multiqc
rsem        → multiqc
featurecounts → multiqc
snpeff      → multiqc
```

当前校验（`workflow_composer.py:1399-1553`）：

- R3：input 名必须匹配目标工具注册 input；
- R5：`from` 的 output 名必须匹配源工具注册 output；artifact 必须相等，唯一例外 `ARTIFACT_COMPATIBILITY = {("sorted_dedup_bam", "aligned_bam")}`；
- R6：每条 `from` / `depends_on` 的 `(源工具, 目标工具)` 必须命中 NEXT 边集。

### 2.2 改造目标

把“artifact 推理 + NEXT 存在性”双校验，改为**显式查表**：

- **data 边**：携带 `output`（源工具注册输出名）和 `input`（目标工具注册输入名），用于 `from` 绑定；
- **order 边**：只携带源和目标，用于 `depends_on`，不传输数据。

改造后：

- `from` 必须命中 data 边集：`(source_tool, output, target_tool, input)`；
- `depends_on` 只需 `(source_tool, target_tool)` 命中任意 NEXT 边（data 或 order 均可）；
- 删除 `ARTIFACT_COMPATIBILITY` 和 artifact 相等校验；
- 保留 R3（input 名必须匹配注册 input）。

### 2.3 工具输入输出契约（真源核对）

以下名称来自 Neo4j 当前 `io_slot` / `artifact_type` 节点（与 `tool_input_format.csv`、`tool_output_format.csv` + `SEMANTIC_TO_ARTIFACT` 映射一致）。

| tool_id | 注册 inputs | 注册 outputs |
|---|---|---|
| `fastp` | `raw_fastq_read` | `clean_fastq_read` |
| `fastqc` | `clean_fastq_read` (optional), `raw_fastq_read` (optional) | `quality_control_report` |
| `bwa` | `clean_fastq_read`, `genome_annotation` | `aligned_bam` |
| `samtools` | `aligned_bam` | `sorted_dedup_bam` |
| `gatk` | `sorted_dedup_bam`, `genome_annotation` | `sorted_dedup_bam`, `unfiltered_vcf` |
| `bcftools` | `unfiltered_vcf` | `filtered_vcf` |
| `snpeff` | `filtered_vcf`, `genome_annotation` | `annotated_vcf` |
| `trim_galore` | `raw_fastq_read` | `clean_fastq_read` |
| `star` | `clean_fastq_read`, `genome_annotation` | `aligned_bam`, `clean_fastq_read`, `transcriptome_bam` |
| `rsem` | `transcriptome_bam`, `genome_annotation` | `expression_abundance_matrix` |
| `featurecounts` | `sorted_dedup_bam`, `genome_annotation` | `expression_count_matrix` |
| `multiqc` | `quality_control_report` (optional) | `quality_control_report` |

### 2.4 21 条边完整表

| source_tool | kind | output | target_tool | input | 判定依据 | 是否确定 | MultiQC 退出 |
|---|---|---|---|---|---|---|---|
| `fastp` | data | `clean_fastq_read` | `fastqc` | `clean_fastq_read` | fastp 唯一输出 `clean_fastq_read`；fastqc 注册输入含 `clean_fastq_read`（optional） | 确定 | — |
| `fastqc` | order | — | `bwa` | — | fastqc 输出 `quality_control_report`；bwa 输入 `clean_fastq_read`/`genome_annotation`，无交集 | 确定 | — |
| `fastqc` | order | — | `trim_galore` | — | fastqc 输出 QC report；trim_galore 输入 `raw_fastq_read`，无交集 | 确定 | — |
| `bwa` | data | `aligned_bam` | `samtools` | `aligned_bam` | bwa 输出 `aligned_bam`；samtools 输入 `aligned_bam` | 确定 | — |
| `samtools` | data | `sorted_dedup_bam` | `gatk` | `sorted_dedup_bam` | samtools 输出 `sorted_dedup_bam`；gatk 输入 `sorted_dedup_bam` | 确定 | — |
| `gatk` | data | `unfiltered_vcf` | `bcftools` | `unfiltered_vcf` | gatk 另一输出 `sorted_dedup_bam` 与 bcftools 输入 `unfiltered_vcf` 不匹配，唯一匹配为 `unfiltered_vcf` | 确定 | — |
| `bcftools` | data | `filtered_vcf` | `snpeff` | `filtered_vcf` | bcftools 输出 `filtered_vcf`；snpeff 输入 `filtered_vcf` | 确定 | — |
| `snpeff` | order | — | `multiqc` | — | snpeff 输出 `annotated_vcf`；multiqc 输入 `quality_control_report`，无交集 | 确定 | 是 |
| `trim_galore` | data | `clean_fastq_read` | `star` | `clean_fastq_read` | trim_galore 输出 `clean_fastq_read`；star 输入 `clean_fastq_read` | 确定 | — |
| `star` | data | `transcriptome_bam` | `rsem` | `transcriptome_bam` | star 输出 `transcriptome_bam`；rsem 输入 `transcriptome_bam` | 确定 | — |
| `star` | data | `aligned_bam` | `samtools` | `aligned_bam` | star 输出 `aligned_bam`；samtools 输入 `aligned_bam` | 确定 | — |
| `samtools` | data | `sorted_dedup_bam` | `featurecounts` | `sorted_dedup_bam` | samtools 输出 `sorted_dedup_bam`；featurecounts 输入 `sorted_dedup_bam` | 确定 | — |
| `rsem` | order | — | `multiqc` | — | rsem 输出 `expression_abundance_matrix`；multiqc 输入 `quality_control_report`，无交集 | 确定 | 是 |
| `featurecounts` | order | — | `multiqc` | — | featurecounts 输出 `expression_count_matrix`；multiqc 输入 `quality_control_report`，无交集 | 确定 | 是 |
| `fastp` | data | `clean_fastq_read` | `bwa` | `clean_fastq_read` | fastp 输出 `clean_fastq_read`；bwa 输入 `clean_fastq_read` | 确定 | — |
| `fastp` | data | `clean_fastq_read` | `star` | `clean_fastq_read` | fastp 输出 `clean_fastq_read`；star 输入 `clean_fastq_read` | 确定 | — |
| `fastp` | order | — | `multiqc` | — | fastp 输出 `clean_fastq_read`；multiqc 输入 `quality_control_report`，无交集 | 确定 | 是 |
| `fastqc` | data | `quality_control_report` | `multiqc` | `quality_control_report` | fastqc 输出 `quality_control_report`；multiqc 输入 `quality_control_report`（optional） | 确定 | 是 |
| `samtools` | order | — | `multiqc` | — | samtools 输出 `sorted_dedup_bam`；multiqc 输入 `quality_control_report`，无交集 | 确定 | 是 |
| `gatk` | order | — | `multiqc` | — | gatk 输出 `sorted_dedup_bam`/`unfiltered_vcf`；multiqc 输入 `quality_control_report`，无交集 | 确定 | 是 |
| `star` | order | — | `multiqc` | — | star 输出 `aligned_bam`/`transcriptome_bam`/`clean_fastq_read`；multiqc 输入 `quality_control_report`，无交集 | 确定 | 是 |

统计：

- **data 边**：12 条（fastp→fastqc, bwa→samtools, samtools→gatk, gatk→bcftools, bcftools→snpeff, trim_galore→star, star→rsem, star→samtools, samtools→featurecounts, fastp→bwa, fastp→star, fastqc→multiqc）
- **order 边**：9 条（fastqc→bwa, fastqc→trim_galore, snpeff→multiqc, rsem→multiqc, featurecounts→multiqc, fastp→multiqc, samtools→multiqc, gatk→multiqc, star→multiqc）
- **不确定边**：0 条。
- **MultiQC 入边**：**8 条**（snpeff→multiqc, rsem→multiqc, featurecounts→multiqc, fastp→multiqc, fastqc→multiqc, samtools→multiqc, gatk→multiqc, star→multiqc），其中 7 条为 order 边、1 条为 data 边（fastqc→multiqc）。CSV 真源 `tool_relationship.csv` 中目标为 `T12`（MultiQC）的关系共 8 行，不是 9 行。

与预期一致性说明：

- 你预期 `fastqc → bwa`、`fastqc → trim_galore` 是 order 边——**一致**。
- 你预期“8 条 `* → multiqc` 是 order 边”——实际 CSV 中到 multiqc 的边共 **8 条**，其中 **7 条为 order 边**，`fastqc → multiqc` 是 **data 边**（QC report → QC report），因为 MultiQC 的 `quality_control_report` 输入虽然 optional，但契约上确实接收该 artifact。
- 所有能填出 output/input 的边均唯一，没有“源工具多个输出都能接”或“目标多个输入槽都能接”的歧义项。

---

## 3. 校验改造方案（不实施）

### 3.1 需要改动的位置

| 文件 | 行号 | 改动内容 |
|---|---|---|
| `workflow_composer.py` | `62-64` | 删除 `ARTIFACT_COMPATIBILITY` 常量。 |
| `workflow_composer.py` | `168-175` | `RegisteredMethodCatalog.__init__`：保留 `next_edges: Set[Tuple[str,str]]`（任意边，用于 `depends_on`）；新增 `data_edges: Set[Tuple[str,str,str,str]]`（`source_tool, output, target_tool, input`，用于 `from`）。 |
| `workflow_composer.py` | `1468-1483` | 删除 `source_artifact` / `target_artifact` 比较块（artifact 相等校验 + `ARTIFACT_COMPATIBILITY` 例外）。 |
| `workflow_composer.py` | `1485-1490` | `from` 的 NEXT 校验改为查 `data_edges`：`if (source_tool, source_output, tool_id, input_name) not in self.registered_methods.data_edges`。 |
| `workflow_composer.py` | `1514-1519` | `depends_on` 的 NEXT 校验保持查 `next_edges`（当前 `(source_tool, tool_id)` 命中任意边即可）。 |
| `neo4j_observability.py` | `59-66` | `TOOL_NEXT_QUERY` 增加读取 `edge.kind`、`edge.output`、`edge.input`。 |
| `scripts/python/sync_neo4j_tool_catalog.py` | `423-430` | `MERGE (a)-[r:NEXT {source:'curated-next-csv'}]->(b)` 后增加 `SET r.kind=$kind, r.output=$output, r.input=$input`；order 边 output/input 置空字符串。 |
| `data/csv/relations/tool_relationship.csv` | 全表 | 增加 `kind`、`output`、`input` 三列，并按 2.4 节填表。 |
| `scripts/python/validate_csv.py` | `133` | `tool_relationship.csv` 必填列改为 `["tool_id", "next_tool_id", "kind"]`（如希望更强校验可加上 `output`、`input`）。 |
| `workflow_composer.py` | `869-887` | `_method_menu_lines` 菜单格式从 `allowed_next_tool_ids=[...]` 改为分别列出 data 边（`output→target[input]`）和 order 边（`target`）。 |

### 3.2 两个关键测试的拦截能力

#### `test_custom_mode_rejects_transcriptome_bam_as_genomic_aligned_bam`

测试构造：

```python
star.output = "transcriptome_bam"
samtools.input = "aligned_bam"
```

改造后 `from` 查 data 边：`star → samtools` 的 data 边是 `(star, aligned_bam, samtools, aligned_bam)`。LLM 给的 `(star, transcriptome_bam, samtools, aligned_bam)` 不命中，**会被拒绝**。

⚠️ **但该测试会挂**：当前断言检查的错误字符串是：

```text
artifact 不兼容: align.transcriptome_bam[transcriptome_bam] -> bam_process.aligned_bam[aligned_bam]
```

改造后错误信息会变成类似：

```text
NEXT data 边未命中: align(transcriptome_bam) -> bam_process(aligned_bam)
```

因此实施时必须同步更新该测试的断言字符串（或只断言 `validation["ok"]` 为 False 并检查包含 `transcriptome_bam`）。

#### `test_custom_mode_connects_star_aligned_bam_to_samtools_exactly`

测试构造：

```python
star.output = "aligned_bam"
samtools.input = "aligned_bam"
```

命中 data 边 `(star, aligned_bam, samtools, aligned_bam)`，**通过**。

### 3.3 8 个 `validate_steps` 相关测试逐个评估

| 测试 | 改造后是否通过 | 备注 |
|---|---|---|
| `test_custom_mode_rejects_next_edge_not_in_neo4j` | ✅ | `trim_galore → multiqc` 不在 NEXT 边集，仍拒绝。 |
| `test_custom_mode_connects_star_aligned_bam_to_samtools_exactly` | ✅ | 命中 data 边。 |
| `test_custom_mode_rejects_transcriptome_bam_as_genomic_aligned_bam` | ⚠️ 需同步改断言 | 方案能拦住，但错误信息改变导致字符串断言失败。 |
| `test_custom_mode_validates_complete_rnaseq_atomic_chain` | ✅ | 所有 `from` 均命中 data 边；所有 `depends_on` 均命中任意边。 |
| `test_custom_mode_validates_bwa_to_samtools_chain` | ✅ | 命中 data 边 `(bwa, aligned_bam, samtools, aligned_bam)`。 |
| `test_custom_mode_normalizes_numeric_step_ids_and_references` | ✅ | 依赖 `trim_galore → star` data 边，命中。 |
| `test_custom_mode_normalizes_string_asset_binding` | ✅ | 单步无 from/depends_on，不受影响。 |
| `test_custom_mode_rejects_asset_only_disconnected_chain` | ✅ | 连通性规则（非首步必须 from/depends_on）保留，仍拒绝。 |

**结论**：改造方案本身没有逻辑漏洞，唯一需要同步修改的是 `test_custom_mode_rejects_transcriptome_bam_as_genomic_aligned_bam` 的断言文本。

---

## 4. 影响面清单

### 4.1 `tool_relationship.csv`

需要新增三列：`kind`、`output`、`input`。21 条边按 2.4 节填表，order 边的 `output`/`input` 留空。

示例：

```csv
tool_id,next_tool_id,kind,output,input
T01,T02,data,clean_fastq_read,clean_fastq_read
T02,T03,order,,
...
```

### 4.2 `validate_csv.py`

- `relation_files` 中 `tool_relationship.csv` 的 required cols 至少改为 `["tool_id", "next_tool_id", "kind"]`；建议同步加上 `"output"`、`"input"` 以强制新表完整。
- 当前 `validate_csv.py` 不校验 `output`/`input` 是否存在于工具 slot 中，这一点在人工填表后由单元测试兜底；如需自动校验，可新增对 `tool_input_format.csv` / `tool_output_format.csv` 的外键检查，但这属于增强，不在本次最小改造范围内。

### 4.3 `sync_neo4j_tool_catalog.py`

当前 `--apply` 写 NEXT 边的 Cypher（`:423-430`）只设置 `r.reviewed`、`r.review_version`。需要增加：

```cypher
SET r.kind = $kind,
    r.output = $output,
    r.input = $input
```

`load_catalog()` 返回的 `expected_next` 需要把 CSV 新列带过去。order 边 output/input 为空字符串时，Neo4j 中可存 `""` 或不设置属性（查询时 COALESCE 为 `""`）。

### 4.4 `neo4j_observability.py`

`TOOL_NEXT_QUERY` 当前只返回 `source_tool_id`、`target_tool_id`、`source_catalog_id`、`target_catalog_id`。需要扩展为：

```cypher
RETURN source.tool_id AS source_tool_id,
       target.tool_id AS target_tool_id,
       source.catalog_id AS source_catalog_id,
       target.catalog_id AS target_catalog_id,
       edge.kind AS kind,
       edge.output AS output,
       edge.input AS input
```

### 4.5 stage-two 菜单 `_method_menu_lines`

当前菜单字符数：**3017**（12 行原子工具）。

当前格式示例（fastqc）：

```text
- fastqc | catalog_id=T02 | inputs=[clean_fastq_read[...], raw_fastq_read[...]] | outputs=[quality_control_report[...]] | allowed_next_tool_ids=['bwa', 'trim_galore', 'multiqc'] | ...
```

改造后建议格式示例（fastqc）：

```text
- fastqc | catalog_id=T02 | inputs=[...] | outputs=[...] | data_next=[bwa(clean_fastq_read→clean_fastq_read), multiqc(quality_control_report→quality_control_report)] | order_next=[trim_galore] | ...
```

Token 变化估算：

- 每条 data 边需要额外描述 `output→target[input]`，平均约 35-45 字符；12 条 data 边共增加约 **420-540 字符**。
- order 边仍只需列出 target 名，不增加显著长度。
- 预计改造后菜单总长度约 **3500-3600 字符**，仍在可接受范围，不会一次性冲破 LLM 上下文。

### 4.6 其他引用 `NEXT` 边 / `ARTIFACT_COMPATIBILITY` 的位置

`grep` 结果：

- `ARTIFACT_COMPATIBILITY`：仅在 `workflow_composer.py:62`、`workflow_composer.py:1477` 和 `AI_PROJECT_CONTEXT*.md` 文档中引用。代码实施时删除代码处两处即可，文档需同步更新。
- `NEXT` 边读取：
  - `neo4j_observability.py:60` 查询；
  - `workflow_composer.py:168-175` 消费；
  - `sync_neo4j_tool_catalog.py:420-430` 写入；
  - `cypher/import/04_import_workflow_relations.cypher:14` 旧导入脚本（运行时不用，但改 CSV 后如需保留应同步列）。
- `curated-next-csv`：仅用于标识 NEXT 边来源，可保留，不受影响。

---

## 5. 只读探查（第 3 节五条）

> 说明：以下 Cypher 均在已连接 Neo4j 的真实图上执行。由于 `sample` 与 `study` 之间没有直接关系，样本归属通过 `sample.study_accession` 属性匹配；`individual` 与 `study` 之间通过 `IN_STUDY` 关系连接；`study → project` 通过 `IN_PROJECT` 关系连接。

### 5.1 ground truth 校准：HRA006499 `_T`/`_N` 后缀样本的 `specimen_types` 分布

**实际查询：**

```cypher
MATCH (s:sample)
WHERE s.study_accession = 'HRA006499'
  AND (s.sample_name ENDS WITH '_T' OR s.sample_name ENDS WITH '_t'
       OR s.sample_name ENDS WITH '_N' OR s.sample_name ENDS WITH '_n')
WITH s,
  CASE WHEN s.sample_name ENDS WITH '_T' OR s.sample_name ENDS WITH '_t' THEN '_T' ELSE '_N' END AS suffix
RETURN suffix, s.specimen_types AS specimen_types, count(*) AS cnt
ORDER BY suffix, specimen_types;
```

**原始结果：**

| suffix | specimen_types | cnt |
|---|---|---|
| `_N` | Patient Solid Tissue | 58 |
| `_T` | Patient Solid Tissue | 149 |

**说明**：`_T` 和 `_N` 后缀样本的 `specimen_types` 全部是 `Patient Solid Tissue`，没有按后缀区分出 `Peritumoral`。因此**不能**用后缀直接映射到 `Peritumoral`/`Solid Tissue` 角色。

### 5.2 每个 study 的测序类型

**实际查询：**

```cypher
MATCH (s:study)-[:IN_PROJECT]->(p:project)
OPTIONAL MATCH (sample:sample {study_accession: s.study_accession})
RETURN s.study_accession AS study,
       p.data_types AS data_types,
       s.tumor_type AS tumor_type,
       count(sample) AS n
ORDER BY study;
```

**原始结果：**

| study | data_types | tumor_type | n |
|---|---|---|---|
| HRA000021 | Whole genome sequencing | Esophageal Cancer | 1016 |
| HRA000071 | Transcriptome or Gene expression | Glioma | 572 |
| HRA000074 | Transcriptome or Gene expression | Glioma | 693 |
| HRA000122 | Exome， Transcriptome or Gene expression | Leukemia | 287 |
| HRA000321 | Transcriptome or Gene expression、Raw sequence reads | multiple cancers | 0 |
| HRA000873 | Exome， Raw sequence reads | Colorectal Cancer | 2030 |
| HRA001272 | Exome， Transcriptome or Gene expression， Raw sequence reads | Liver Cancer | 698 |
| HRA001748 | Single cell sequencing, WES | Liver Cancer | 160 |
| HRA001749 | Single cell sequencing, WES | Liver Cancer | 178 |
| HRA003107 | Whole genome sequencing， Epigenomics， Transcriptome or Gene expression | Esophageal Cancer | 310 |
| HRA005191 | Transcriptome or Gene expression | Lung Cancer | 243 |
| HRA006499 | Exome， Transcriptome or Gene expression | Liver Cancer | 482 |
| HRA007167 | Exome， Transcriptome or Gene expression， Single cell sequencing | Melanoma | 81 |
| HRA007169 | Exome， Transcriptome or Gene expression， Single cell sequencing | Melanoma | 168 |

### 5.3 跨 study 配对嫌疑

#### HRA001748 / HRA001749

**实际查询（前 40 条按 accession）：**

```cypher
MATCH (i:individual)-[:IN_STUDY]->(s:study)
WHERE s.study_accession IN ['HRA001748', 'HRA001749']
RETURN s.study_accession AS study,
       i.individual_accession AS accession,
       i.individual_id AS individual_id,
       i.individual_name AS individual_name
ORDER BY i.individual_accession
LIMIT 40;
```

**重叠统计查询：**

```cypher
MATCH (i:individual)-[:IN_STUDY]->(s:study)
WHERE s.study_accession IN ['HRA001748', 'HRA001749']
WITH i.individual_accession AS acc,
     i.individual_id AS name,
     collect(DISTINCT s.study_accession) AS studies
RETURN size(studies) AS study_count, count(*) AS individuals
ORDER BY study_count;
```

**原始结果：**

- `study_count=1`：40 个 individual（仅在 HRA001748）；
- `study_count=2`：84 个 individual（同时出现在 HRA001748 和 HRA001749）。

HRA001748 全部 `individual_id`：`A001`–`A124`（124 个）。
HRA001749 全部 `individual_id`：84 个，全部在 HRA001748 的 `A001`–`A124` 范围内，例如 `A007, A009, A010, A012, ..., A124`。

20 条示例对比（原样）：

| HRA001748 accession | HRA001748 name | HRA001749 accession | HRA001749 name |
|---|---|---|---|
| HRI179841 | A001 | — | — |
| HRI179842 | A002 | — | — |
| HRI179843 | A003 | — | — |
| HRI179844 | A004 | — | — |
| HRI179845 | A005 | — | — |
| HRI179846 | A006 | — | — |
| HRI179847 | A007 | HRI179847 | A007 |
| HRI179848 | A008 | — | — |
| HRI179849 | A009 | HRI179849 | A009 |
| HRI179850 | A010 | HRI179850 | A010 |
| HRI179851 | A011 | — | — |
| HRI179852 | A012 | HRI179852 | A012 |
| HRI179853 | A013 | HRI179853 | A013 |
| HRI179854 | A014 | HRI179854 | A014 |
| HRI179855 | A015 | HRI179855 | A015 |
| HRI179856 | A016 | HRI179856 | A016 |
| HRI179857 | A017 | HRI179857 | A017 |
| HRI179858 | A018 | HRI179858 | A018 |
| HRI179859 | A019 | — | — |
| HRI179860 | A020 | HRI179860 | A020 |

此外，HRA001748 全 `Tumor`，HRA001749 全 `Normal`；两者 `data_types` 均为 `Single cell sequencing, WES`。

#### HRA000021 / HRA003107

**实际查询：**

```cypher
MATCH (i:individual)-[:IN_STUDY]->(s:study)
WHERE s.study_accession IN ['HRA000021', 'HRA003107']
WITH i.individual_accession AS acc,
     i.individual_id AS name,
     collect(DISTINCT s.study_accession) AS studies
RETURN size(studies) AS study_count, count(*) AS individuals
ORDER BY study_count;
```

**原始结果：**

- `study_count=1`：663 个 individual；
- `study_count=2`：0 个。

20 条示例对比：

| HRA000021 accession | HRA000021 name | HRA003107 accession | HRA003107 name |
|---|---|---|---|
| HRI035286 | BDESCC0004 | HRI281308 | BDESCC2-1 |
| HRI035287 | BDESCC0006 | HRI281309 | BDESCC2-2 |
| HRI035288 | BDESCC0007 | HRI281310 | BDESCC2-3 |
| HRI035289 | BDESCC0008 | HRI281311 | BDESCC2-4 |
| HRI035290 | BDESCC0009 | HRI281312 | BDESCC2-6 |
| HRI035291 | BDESCC0010 | HRI281313 | BDESCC2-9 |
| HRI035292 | BDESCC0011 | HRI281314 | BDESCC2-10 |
| HRI035293 | BDESCC0013 | HRI281315 | BDESCC2-11 |
| HRI035294 | BDESCC0014 | HRI281316 | BDESCC2-12 |
| HRI035295 | BDESCC0015 | HRI281317 | BDESCC2-14 |
| HRI035296 | BDESCC0017 | HRI281318 | BDESCC2-15 |
| HRI035297 | BDESCC0019 | HRI281319 | BDESCC2-16 |
| HRI035298 | BDESCC0020 | HRI281320 | BDESCC2-17 |
| HRI035299 | BDESCC0023 | HRI281321 | BDESCC2-19 |
| HRI035300 | BDESCC0026 | HRI281322 | BDESCC2-20 |
| HRI035301 | BDESCC0027 | HRI281323 | BDESCC2-22 |
| HRI035302 | BDESCC0028 | HRI281324 | BDESCC2-23 |
| HRI035303 | BDESCC0029 | HRI281325 | BDESCC2-24 |
| HRI035304 | BDESCC0030 | HRI281326 | BDESCC2-26 |
| HRI035305 | BDESCC0031 | HRI281327 | BDESCC2-29 |

### 5.4 HRA001272 是否是干净的配对队列

**实际查询：**

```cypher
MATCH (s:sample {study_accession: 'HRA001272'})
RETURN s.tissue_type AS tissue_type,
       s.specimen_types AS specimen_types,
       count(*) AS cnt
ORDER BY tissue_type, specimen_types;
```

**原始结果：**

| tissue_type | specimen_types | cnt |
|---|---|---|
| Normal | Patient Solid Tissue | 199 |
| Normal | Peritumoral | 142 |
| Tumor | Patient Solid Tissue | 286 |
| Tumor | Peritumoral | 71 |

### 5.5 单侧多样本分布

定义：一个 individual 下同时含有 `Patient Solid Tissue` 和 `Peritumoral` 样本，视为“按 specimen_types 判定为配对”。

**实际查询：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WITH i,
  count(CASE WHEN s.specimen_types = 'Patient Solid Tissue' THEN 1 END) AS n_solid,
  count(CASE WHEN s.specimen_types = 'Peritumoral' THEN 1 END) AS n_peri
WHERE n_solid >= 1 AND n_peri >= 1
RETURN n_solid, n_peri, count(*) AS individuals
ORDER BY individuals DESC;
```

**原始结果：**

| n_solid | n_peri | individuals |
|---|---|---|
| 1 | 1 | 1865 |
| 4 | 1 | 22 |
| 3 | 1 | 20 |
| 2 | 1 | 15 |
| 6 | 1 | 10 |
| 5 | 1 | 9 |
| 7 | 1 | 4 |
| 8 | 1 | 4 |
| 5 | 2 | 2 |
| 6 | 2 | 2 |
| 12 | 2 | 1 |
| 3 | 2 | 1 |
| 7 | 2 | 1 |
| 9 | 1 | 1 |

（注：完整 pattern 还包含少量同时带 `Blood` 或 `Organoid` 的个体，上文为 Solid/Peritumoral 核心分布。）

---

## 6. 判断、风险与边界情况

### 6.1 方案有没有洞

- **transcriptome_bam → aligned_bam 的误绑定**：改造后 `from` 必须命中 data 边。`star → samtools` 的 data 边明确为 `(star, aligned_bam, samtools, aligned_bam)`，LLM 无法用 `transcriptome_bam` 接入 samtools，因此能拦住。比原 artifact 校验更严格、更直接。
- **sorted_dedup_bam → aligned_bam 的反向兼容**：原 `ARTIFACT_COMPATIBILITY` 只允许 `(sorted_dedup_bam, aligned_bam)`，即 samtools 输出作为某些工具的 aligned_bam 输入。改造后如果存在这种需求，需要显式在边表中增加一条 data 边（例如 `samtools → bwa`）。当前 21 条边中没有这种场景，所以删除兼容规则是安全的。
- **depends_on 允许 order 边**：这是设计意图，但意味着 LLM 可以把 `star` 和 `multiqc` 用 `depends_on` 串起来，即使它们之间没有数据传输。这与 MultiQC“扫目录聚合日志”的语义一致，是合理的。
- **input 名校验保留**：即使 data 边存在，如果 LLM 把 `from` 挂在目标工具未注册的 input 名上，仍会被 R3 拒绝。这是必要的第二层防护。

### 6.2 order / data 二分够不够用

对当前 12 个 atomic tool、21 条边足够：

- data 边精确描述“数据从哪来、接到哪个槽”；
- order 边精确描述“执行顺序/报告汇总，不传输主数据”。

但未来如果出现以下场景，二分可能不够：

- **同一 (source, target) 之间有多条 data 边**：例如某个工具输出两种矩阵，目标工具有两个对应输入槽。当前 21 条边没有这种情况；若未来出现，data 边集天然支持（按 4 元组区分）。
- **可选 data 边**：例如 fastqc 的 `clean_fastq_read` 输入是 optional。当前 data 边 `fastp → fastqc` 使用 `clean_fastq_read`，合理；若 fastp 也能接 fastqc 之前的 raw FASTQ，则需额外 data 边 `fastqc → fastp`（当前不存在）。
- **同一目标 input 可从多个源 output 接**：例如 `multiqc` 的 `quality_control_report` 可来自 fastqc、也可来自其他 QC 工具。只要每条都作为独立 data 边存在即可。

### 6.3 没想到的边界情况

1. **CSV 行尾污染**：本次发现 `tool_relationship.csv` 在部分编辑器/查看工具中显示为混合 `\r` 行尾，但 Python `csv.DictReader(newline="")` 能正确解析。实施填表时务必用 `newline=""` 写入，避免 `` 残留导致 Neo4j match 失败。
2. **空字符串 vs NULL**：sync 脚本对 order 边的 `output`/`input` 若存 `""`，查询时需注意与未设置属性区分。建议统一存 `""`，并在 `RegisteredMethodCatalog` 中过滤掉空值。
3. **`_method_menu_lines` token 膨胀**：虽然估算只增加 ~500 字符，但若未来边数大量增加，菜单会线性膨胀。可考虑把 data 边按 target 聚合显示，但当前 21 条边无需过度设计。
4. **跨 study 配对（HRA001748/HRA001749）**：数据图显示 HRA001749 的 84 个 individual 全部在 HRA001748 中，且两 study 分别为全 Tumor / 全 Normal。当前 `pipeline_router.py:858` 附近按 `study_accession` 分组，会排除这种跨 study 配对。这是业务逻辑层面的问题，不在本次 NEXT 边改造范围内，但属于潜在的重大数据匹配缺口。
5. **HRA006499 后缀 ground truth 失败**：`_T`/`_N` 后缀全部落在 `Patient Solid Tissue` 上，说明 `specimen_types` 与提交者后缀并不一致。若要用 `_T`/`_N` 做角色校准，需要重新评估可信度。

---

## 7. 任务 B：MultiQC 退出 NEXT 边集影响分析（只查不实施）

> 前提：把 MultiQC 视为“流程结束时由执行端无条件运行的日志聚合器”，不再参与编排决策，因此将其所有入边从 NEXT 边集中移除。
> 真源 `tool_relationship.csv` 中目标为 `T12`（MultiQC）的关系共 **8 条**（不是 9 条），已在 2.4 节表中以“MultiQC 退出 = 是”标出。

### 7.1 rnaseq_singletask 锁定 recipe 是否还通得过校验？

**结论：standard 模式不走 `_validate_custom_steps`，去掉 NEXT 入边对标准 recipe 的校验无影响；但 recipe 列表本身取决于 MultiQC 节点是否保留。**

- `workflow_composer.py:1255-1337` 的 `_standard_plan` 直接把 Neo4j 返回的 `pipeline_steps`（HAS_STEP 关系）作为 `internal_steps` 返回，**不调用 `_validate_custom_steps`**。
- `rnaseq_singletask` 的 7 步 recipe 来源是 `RegisteredMethodCatalog.pipeline_steps`（`workflow_composer.py:204-216`），由 Neo4j 的 `HAS_STEP` 关系独立维护，与 `NEXT` 边无关。
- 因此：
  - **只删 NEXT 边、保留 MultiQC 节点**：`internal_steps` 仍是 7 步（含 multiqc），standard 模式返回与现在一致，校验层面不会报错。
  - **连 MultiQC 节点一起删除**：`pipeline_steps` 加载时会因 `self.methods.get(tool_id)` 为 `None` 而跳过 multiqc（`workflow_composer.py:208-210`），`internal_steps` 变为 6 步，`test_standard_rnaseq_recipe_uses_only_neo4j_tools` 会失败。

### 7.2 会挂哪些测试？

| 测试 | 当前期望 | 只删 NEXT 边（留节点） | 连节点一起删 |
|---|---|---|---|
| `test_standard_rnaseq_recipe_uses_only_neo4j_tools` | 7 步含 multiqc | ✅ 通过 | ❌ 失败（期望 7 步，实际 6 步） |
| `test_custom_mode_validates_complete_rnaseq_atomic_chain` | 7 步链通过校验 | ❌ 失败（multiqc `depends_on` rsem/featurecounts 无 NEXT 边） | ❌ 失败（multiqc 为未知 tool_id） |
| `test_custom_mode_rejects_next_edge_not_in_neo4j` | trim_galore→multiqc 被拒绝 | ✅ 通过（trim_galore→multiqc 仍不在 NEXT 边集） | ⚠️ 断言可能失败（错误从“NEXT 不允许”变成“未知 tool_id: multiqc”） |
| 其余 custom 链测试（如 `test_custom_mode_connects_star_aligned_bam_to_samtools_exactly`、`test_custom_mode_rejects_transcriptome_bam_as_genomic_aligned_bam` 等） | 不依赖 multiqc | ✅ 通过 | ✅ 通过 |

说明：
- `test_custom_mode_validates_complete_rnaseq_atomic_chain` 是主要受害者，因为它构造的链以 multiqc 收尾，且 multiqc 使用 `depends_on: ["rsem", "featurecounts"]`，这两条 order 边正是要移除的 8 条中的 2 条。
- 若保留节点只删边，该测试仍会报 `"NEXT 不允许: rsem -> multiqc"` 和 `"NEXT 不允许: featurecounts -> multiqc"`。
- 若连节点一起删，该测试会先报 `"第 7 步包含未知 tool_id: multiqc"`，连 artifact/edge 校验都走不到。

### 7.3 “留节点删边” vs “连节点一起删”的影响面

#### 方案一：保留 MultiQC 节点，只删除 8 条 NEXT 入边

**优点：**
- 不破坏 standard recipe 的 7 步结构，`test_standard_rnaseq_recipe_uses_only_neo4j_tools` 继续通过。
- atomic tool 数量保持 12 个，不动目录节点计数。
- 执行端仍可从 `internal_steps` 中看到 multiqc，自行决定是否运行。

**缺点：**
- MultiQC 在 custom 模式变成“不可达孤儿”：节点存在，但没有任何 NEXT 边指向它，因此 LLM 无法通过 `depends_on` 或 `from` 把它接进链里。
- `_method_menu_lines` 中 MultiQC 的 `allowed_next_tool_ids` 为空，菜单会出现一个“存在但无法连接”的工具，可能让 LLM 困惑。
- `test_custom_mode_validates_complete_rnaseq_atomic_chain` 需要改写或删除 multiqc 步骤。

#### 方案二：连 MultiQC 节点一起删除

**优点：**
- 语义干净：MultiQC 彻底退出编排层，执行端自行在流程末尾运行。
- 菜单、atomic tool 计数、NEXT 边集完全一致，没有孤儿节点。
- 与“MultiQC 不需要编排决策”的语义完全对齐。

**缺点：**
- atomic tool 数量从 12 降到 11，影响任何依赖该数字的日志/报告/测试。
- `rnaseq_singletask` 的 standard recipe 从 7 步变成 6 步，`test_standard_rnaseq_recipe_uses_only_neo4j_tools` 必须更新预期。
- 若同事的其他 pipeline（如 WES pipeline）也把 multiqc 作为 HAS_STEP 的一步，那些 recipe 同样会少一步，需要同步检查所有 `pipeline_steps`。
- `test_custom_mode_rejects_next_edge_not_in_neo4j` 的断言需要调整，因为错误类型从 edge 违规变成未知 tool_id。

### 7.4 我的判断

- **推荐方案一（留节点删边）**，因为：
  1. 本次任务 B 的诉求是“MultiQC 退出 NEXT 边集”，而不是删除工具目录；
  2. 方案一最小化对 standard recipe 和同事目录的侵入；
  3. MultiQC 作为孤儿节点虽然不完美，但比“连节点一起删”带来的连锁修改小得多。
- **无论选哪个方案**，`test_custom_mode_validates_complete_rnaseq_atomic_chain` 都需要修改——这是无法避免的。
- 如果未来决定“MultiQC 彻底从编排层消失”，再执行方案二（删节点），并同步更新所有依赖 12 个 atomic tool / 7 步 recipe 的测试和文档。
