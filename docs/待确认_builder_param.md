# 待确认：39 个输入槽的 builder_param / wdl_target

## 先说结论

`io_slot.csv` 有 128 个输入槽。0823 起点：33 个有 `builder_param`（12 个工具），95 个空。
空槽会被 `workflow_composer.py` 跳过，`execution_params` 于是跟着空——师兄看到的"三个输入
builder_param、wdl_target 全空"是这条链的末端。

图谱按设计就不携带 slot / wdl_target / builder_param（见 `tool_catalog_source.py` 模块注释），
这些是执行侧契约，只存在于 `data/csv/catalog/`。**要改的是 MCP 这边的目录表，图谱不用动。**

两轮补完后：**89 个有值，39 个仍空（23 个工具）**。

| 轮次 | 依据 | 落地 |
|---|---|---|
| 第一轮 | 卡片 `interface.params` + 角色唯一对应 + 双射校验 | 31 |
| 第二轮 | 把 `归档.zip` 里的 `.wdl` 本体和 `example_inputs.json` 一起当证据，三方交叉验证 | 25 |

**这 56 条没有一条是猜的。** 第二轮的门槛是三条同时成立，任一条不过就整条退回人工：

1. `.wdl` 顶层 `workflow X { input {...} }` 里存在该参数，且类型是 `File`；
2. `knowledge_card.yaml` 的 `interface.params` 里有**同名**参数（师兄这条规则被做成了硬校验）；
3. 卡片该参数的 `target` 逐字等于 `<WorkflowName>.<param>`，并以它作为 `wdl_target` 落库。

第一轮的 31 条也已用同一套三方规则回验过一遍，31/31 全对，无一需要改。

下面 39 个槽没过校验，**没填也没猜**。这里猜错的后果不是报错，是给出一张填满的、看着合理的
错参数表，要到执行端才炸——或者更糟，不炸，只是结果错。

---

## 好消息：39 个槽不是 39 个问题，是 4 类

按"要做的决定"归并之后，真正需要师兄拍板的只有下面 4 件事，其中 A、B 两类占 19 个槽，
而且各自只是**同一个决定重复了十几遍**。

### A. `genome_annotation` 槽在 12 个工具上都没有对应的 File 参数（12 槽）

`bwa`、`gatk`、`snpeff`、`rsem`、`star`、`rmats_alternative_splicing`、`breast_cellchat`、
`immunotherapy_cellchat`、`celltype_case_control_de`、`ipf_trajectory_regulon`、
`tcell_intervention`、`dataset_matrix_annotation`

这 12 个槽全部 `required=true`、`wdl_type=File`。但查遍这 12 个 WDL，**没有一个有对应的 File 输入**：

- `bwa` / `gatk` / `snpeff` / `rmats`：参考资源全是 **String + 容器内默认路径**
  （`reference_fasta=/opt/wes_resources/...`、`annotation_gtf=/opt/rmats-workflow/reference/gencode.v49.annotation.gtf`）。
  rmats 的 README 甚至明写"镜像内置 GTF，因此它们不再是 Cromwell 文件输入"。
- 6 个单细胞工具（breast_cellchat / immunotherapy_cellchat / celltype_case_control_de /
  ipf_trajectory_regulon / tcell_intervention / dataset_matrix_annotation）：WDL 顶层的
  File 参数**只有 `input_rds` 一个**，参考基因组是 `String species` / `String genome` 标签。
- `star`：两个必需 File 索引（`rrna_star_index` + `genome_star_index`），一个槽对两个参数。
- `rsem`：只剩 `rsem_index`，但它在 task 里按目录用（`"~{rsem_index}/rsem_ref"`），塞个 GTF 会直接崩。

**要师兄回答的是一个问题，不是 12 个**：这批 `genome_annotation` 槽是不是建模时误加的？
如果是，删掉即可（`star` / `rsem` 例外，它们要改成 `rrna_star_index` / `genome_star_index` /
`rsem_index` 三个独立槽——姊妹流程 `rnaseq_singletask` 已经是这么建的，可以照抄）。

> 注：`featurecounts` 的 `genome_annotation` 是**真的** GTF（`File gtf_file`，卡片默认
> `annotation.gtf`），本轮已填。所以不是"这个槽名一律错"，是这 12 个工具上错。

### B. `tabular_bio_data` 槽在 6 个单细胞工具上是幽灵槽（7 槽）

`celltype_case_control_de`、`dataset_downstream`、`dataset_matrix_annotation`、
`lung_tme_annotation_cnv`、`scrna_cell_communication`、`tcell_intervention`
（外加 `ipf_trajectory_regulon` / `tcell_intervention` / `scrna_cell_communication` 的
`sample_metainfo` 槽，同一性质）

同样是 `required=true`，同样在 WDL 里找不到任何可落的 File 参数——这些工具的输入就是一个
`input_rds`（`lung_tme_annotation_cnv` 和 `dataset_downstream` 多一个 `gene_order`，已填）。

硬证据：`dataset_downstream` 与 `dataset_matrix_annotation` 在槽表里**槽集合逐字相同**，连
description 文案（`SCRNA_OBJECT_RDS` / `TABULAR_BIO_DATA` / `REFERENCE_GENOME_FASTA`）都一样，
但两个 WDL 的 File 输入数量不同（前者 2 个、后者 1 个）。这说明槽表是**按模板批量生成**的，
不是按 WDL 本体生成的。

**要回答的同样是一个问题**：这批槽删掉，还是它们本意指向 `dataset_id`（必需 String）？
两种解法后果相反（删槽 vs 改槽类型），我不替师兄选。

### C. 数组/队列型输入——槽模型表达不了（8 槽）

这几个不是"漏抄参数名"，是**单文件槽装不下数组**，补 `builder_param` 也没用：

| 工具 | 槽 | WDL 实际接口 |
|---|---|---|
| `fastqc` | `raw_fastq_read` / `clean_fastq_read` | `Array[File]+ fastqs`，且对它 scatter |
| `multiqc` | `quality_control_report` | `Array[File]+ qc_files`，N:1 扇入 |
| `cnvkit_cnv_clinical` | `aligned_bam` / `tabular_bio_data` / `clinical_table` | 5 个等长并行数组（`sample_ids` / `tumor_bams` / `tumor_bais` / `normal_bams` / `normal_bais`），按同下标绑定 |
| `rmats_alternative_splicing` | `transcriptome_bam` / `genome_annotation` | `group1_bams` + `group2_bams` 两组 `Array[File]+` |

`example_inputs.json` 能把**形状**定死，但定不了**分组规则**：

- cnvkit 的样例 `tumor_bams=[HRR365787, HRR365898]`、`normal_bams=[HRR365786, HRR365897]`，
  787/786 与 898/897 是相邻登录号，**证明了同下标即同一病人的肿瘤/正常配对**。但两边文件名
  都是 `.BQSR.bam`，形态上没有任何区别，**哪个样本算 tumor 是临床标注决定的，样例证明不了**。
- rmats 更明显：分组的全部含义在 `group1_label="adjacent_normal_liver"` /
  `group2_label="intrahepatic_recurrent_tumor"` 这两个字符串里，而槽表没地方放它们。

所以这一类要的不是参数名，是**槽模型加数组基数 + 分组语义**（第 2 项架构改造）。

### D. 逐个要人定的（12 槽）

只有这些是真正一条一条要师兄看的：

**`bcftools` / `unfiltered_vcf`** — 这条我特意没填，虽然它结构上被逼死了（`filtered_vcf`
是 workflow 唯一的 File VCF 输入）。原因：图谱是按 `slot_name` 同名串联工具的，
`gatk::output::unfiltered_vcf` → `bcftools::input::unfiltered_vcf` 会把 Mutect2 的**原始 VCF**
喂给一个执行 `bcftools view -f PASS` 的步骤。FILTER 注记要 `FilterMutectCalls` 之后才存在，
**这条线不会报错，只会安静地给出空的 PASS 集合**。填上参数名等于给这条错线盖章。
需要先判定：是槽名口径问题（改名 `filtered_vcf`），还是上游连线本身错了。

另外 `bcftools` 还缺一个必需 File 槽 `filtered_vcf_index`（`ln -sf` 成 `.tbi` 后才能读），
**缺了直接执行失败**。这是本工具最硬的缺口。

**`paired_fastq_to_unmapped_bam` / `fastq_1`、`fastq_2`** — 参数名毫无歧义（WDL 里就叫
`fastq_1`/`fastq_2`），但**卡片的 `interface.params` 里根本没有这两个参数**，只有
`sample_name` / `sample_accession` / `output_base` / `make_fofn` / `platform_name` /
`sequencing_center` / `run_date` 七个。按师兄自己定的"参数名要与 knowledge card 相同"这条规则，
这两条我填不了——**要先补卡片**。

顺带两个发布物自身的错，跟槽表无关但会误导任何拿样例做推断/冒烟的人：
- `example_inputs.json` 里 `fastq_2` 指向的是**和 `fastq_1` 同一个 R1 文件**（`NVM0598_R1.clean.clean.fastq.gz`），R2 被写成了 R1；
- `make_fofn` 传的是字符串 `"true"` 而不是 JSON 布尔 `true`；
- workflow 顶层把 `fastq_1`/`fastq_2` 声明为 `String`，task 内部却是 `File`——Cromwell 对
  String 不做 localization，路径按字面量透传。

**`star` / `clean_fastq_read`、`trim_galore` / `raw_fastq_read`** — 一个槽 vs WDL 的
`read1` + `read2`。`bwa` 和 `fastp` 已经做过 mate 拆分（带 `dimension=mate` / `variant_alias_for`，
本轮已填），`star` 和 `trim_galore` 这三列全空，没被那次改造覆盖。
**风险不对称**：`read2` 是 `File?`，漏填不会报错，`is_paired = defined(read2)` 变 false，
STAR / trim_galore **静默按单端跑完，结果错但一路绿灯**。建议照 `bwa`/`fastp` 拆槽。

**`cellranger_workflow` / `raw_fastq_read`、`aligned_bam`** — `raw_fastq_read` 对上
`fastq_file1` + `fastq_file2` 两个必需参数；`aligned_bam` 在槽表里被同时建成了
**必需 input 和 output**（自环）。另外 `CellRangerFullPipeline.transcriptome` 是这批里唯一
一个货真价实的参考文件参数，反而没有槽。

**`scrna_cell_communication`** 的三个槽（`tabular_bio_data` / `scrna_object_rds` /
`sample_metainfo`）全部 `required=true`，但 WDL 里 **7 个 File 参数全是 `File?`**，且
`seurat_rds` 与 `combined_counts` 是互斥二选一（槽表没建模这个互斥）。必需性标注整体反了。

**别名行 2 条**（`bwa/clean_fastq_read`、`fastp/raw_fastq_read`）——这两行
`variant_alias_for` 指向 `_r1` 槽，不是独立输入。已填的 89 行里没有任何一行是别名行，
所以保持空是符合既有约定的；`_execution_params` 也已显式跳过别名行，不会重复上报。

---

## 顺带发现的、不属于本次映射范围但会咬人的问题

这些不用师兄现在回答，但建议单独立项：

1. **`required` 标注和 WDL 系统性相反。** `gatk` 的 `tumor_bam`/`tumor_bai`/`normal_bam`/
   `normal_bai` 在槽表里全是 `required=false`，WDL 里全是无默认的必需 `File`；反过来
   `genome_annotation` 槽表 `required=true`，WDL 里压根没这参数。`fastp`、`fastqc`、
   `multiqc`、`cnvkit` 同病。按槽表直接构建输入会漏必填项。

2. **`gatk` 的 `single` 变体不可实现。** `tool_id.csv` 声明了
   `{"single":["sorted_dedup_bam"],"paired":[tumor_bam,...]}` 且 `exactly_one_variant=true`，
   但 `GatkWesSomaticWorkflow` 是严格的 tumor-normal Mutect2，四个 BAM/BAI 都是必需，
   没有任何单样本入口。同理 `fastp` 声明了 `single_end` 变体，但 `FastpPairedEndWorkflow`
   的 `read2` 是 `File`（非 `File?`）且 task 无条件展开 `--in2`，跑不了单端。

3. **样本身份类必需 String 全线无槽。** `sample_id`（几乎每个工具）、`gatk` 的
   `pair_id`/`tumor_id`/`normal_id`（要与 BAM 头 `@RG SM` 一致，填错直接报错）、
   `paired_fastq_to_unmapped_bam` 的 7 个 read-group 元数据。这些不只是命名：
   `readgroup_name` 决定 uBAM 输出文件名，`sample_id` 决定几乎所有输出名，
   缺了输出槽的实际产物路径在图里不可推导。

4. **QC 边在图里几乎全断。** `multiqc` 的输入是各工具的 QC 报告，但 `samtools` 的
   flagstat/stats/idxstats、`trim_galore` 的 trimming_reports、`fastp` 的 html/json、
   `star` 的两个 Log.final.out、`featurecounts` 的 summary——输出槽全都没建。
   `multiqc` 在图上几乎没有可连的上游。

5. **`samtools` 的 `sorted_dedup_bam` 名不副实。** `remove_duplicates` 默认 `false`，
   此时产出的是 `sorted_bam`（**未去重**），槽名却承诺了 dedup，下游 `featurecounts`
   接的就是它。语义被静默弱化。

6. **`rmats_alternative_splicing::output::aligned_bam` 是明确的错槽。** 该 workflow
   不产出任何 BAM（README：流程从已比对 BAM 开始），且这个槽把 RNA 流程的输出标成了
   `DNA_GENOMIC_ALIGNMENT_BAM`，组学类型也错了。

7. **`relationships.csv` 的 `ALLOW_FORMAT` 没有槽级判别力。** 它是工具级 `input_format`
   并集下放到每个槽——`gatk` 两个输入槽都拿到 `{bam, fasta, vcf}`，`snpeff` 两个都拿到
   `{database, vcf}`。做映射时不能拿它当证据。

8. **`xlrd_vendor_zip` 绑死在共享文件系统上。** 10 个 bulk 工具都有
   `File xlrd_vendor_zip = "/cromwell-share/cromwell_building_group/liuq/bulk10_dependencies/xlrd_vendor.zip"`，
   声明为非可选 File 却带硬编码默认路径。换环境执行会失败。

---

## 空槽现在会自己说话

配套改了 `workflow_composer.py`：以前没有 `builder_param` 的槽是**无声 `continue`**，
回包给出 `execution_params: {}` 加一份字段完整、看不出异常的推荐，`execution_params_missing`
也是空的——"零个参数、且一个都不缺"，消费方按 `not missing` 判可提交就会当成能提交。

现在未绑定的数据槽会进 `execution_params_missing`，`reason: "slot_not_bound"`：

```json
{"param": null, "slot": "scrna_object_rds", "role": "data_file",
 "reason": "slot_not_bound",
 "detail": "该输入槽在 data/csv/catalog/io_slot.csv 里没有 builder_param，无法映射到 WDL 参数；待确认清单见 docs/待确认_builder_param.md"}
```

三条边界：

- **参考文件槽仍然不报**（师兄规则 4：参考索引带卡片默认值，不是用户数据），否则噪声淹掉真问题；
- **别名行不报**（真实槽自己会报，别名再报一次是把同一件事说两遍）；
- **`slot_not_bound` 与 `no_confirmed_path` 不合并**——前者要人去补目录表，后者是绑定没问题
  但图里没有确认路径（如 T1 FASTQ 的 `file_path=NOT_FOUND`），要数据侧补，处置完全不同。

`execution_params_missing` 是已有的契约字段，新增一个 `reason` 取值是加法，不破坏现有消费方。
测试见 `tests/test_slot_not_bound_is_reported.py`。
