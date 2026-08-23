# 输入槽 → WDL 参数绑定：收口记录

## 结论

`io_slot.csv` 的**输入槽已全部绑定**。

| 时点 | 输入槽数 | 已绑定 | 未绑定 |
|---|---|---|---|
| 0823 起点 | 128 | 33 | 95 |
| 第一轮（卡片 `interface.params` + 角色双射） | 128 | 64 | 64 |
| 第二轮（加 `.wdl` 本体 + `example_inputs.json` 三方交叉验证） | 128 | 89 | 39 |
| 第三轮（**按 WDL 重建槽本身**） | 122 | 117 | 5 |

剩下的 5 条是别名行（`bwa` / `fastp` / `star` / `trim_galore` / `cellranger_workflow` 的
`*_fastq_read`），`variant_alias_for` 指向 `_r1` 槽，不是独立输入，按既有约定必须留空，
`_execution_params` 也显式跳过它们，不会重复上报。

图谱按设计就不携带 slot / wdl_target / builder_param（见 `tool_catalog_source.py` 模块注释），
这些是执行侧契约，只存在于 `data/csv/catalog/`。**图谱不用动。**

---

## 第三轮改的是槽，不是参数名

前两轮都在做同一件事：槽表说有这个槽，就去 WDL 里找同角色的参数填上。剩下的 39 个填不上，
不是参数名难找，是**槽本身是错的**。

硬证据：`dataset_downstream` 与 `dataset_matrix_annotation` 在槽表里槽集合逐字相同，连
description 文案（`SCRNA_OBJECT_RDS` / `TABULAR_BIO_DATA` / `REFERENCE_GENOME_FASTA`）都一样，
但两个 WDL 的 File 输入数量不同（前者 2 个、后者 1 个）。槽表是**按模板批量生成**的，
不是按 WDL 生成的。继续往里填参数名，等于给模板猜出来的槽盖章。

所以这一轮以每个工具的 `knowledge_card.yaml` `interface.params` 为准（师兄规则："参数名需要
与 knowledge card 相同"），四类动作：

### 1. 删幽灵槽（23 个）

card 里根本没有对应的 `type: file` 参数。

| 槽 | 涉及工具 | 依据 |
|---|---|---|
| `genome_annotation` ×10 | bwa、gatk、snpeff、rmats、breast_cellchat、immunotherapy_cellchat、celltype_case_control_de、ipf_trajectory_regulon、tcell_intervention、dataset_matrix_annotation | 参考资源在这些 WDL 里全是 `String` + 容器内默认路径（`reference_fasta=/opt/wes_resources/…`、`annotation_gtf=/opt/rmats-workflow/…`），或干脆是 `String species` / `String genome` 标签。**没有 File 参数** |
| `tabular_bio_data` ×6、`sample_metainfo` ×2 | celltype_case_control_de、dataset_downstream、dataset_matrix_annotation、lung_tme_annotation_cnv、tcell_intervention、cnvkit、ipf_trajectory_regulon | 这 6 个单细胞工具的 File 参数只有 `input_rds`（dataset_downstream / lung_tme_annotation_cnv 多一个 `gene_order`，第二轮已填） |
| `gatk::input::sorted_dedup_bam` | gatk | `single` 变体不可实现：`GatkWesSomaticWorkflow` 是严格 tumor-normal Mutect2，四个 BAM/BAI 都必需，没有单样本入口。`tool_id.csv` 的 `input_variants_json` 同步去掉 `single` |
| `cellranger_workflow::input::aligned_bam` | cellranger | 槽表把它同时建成必需 input 和 output（自环）。`CellRangerFullPipeline` 的输入里没有任何 BAM |

留着它们的代价不是报错：`required=true` 的幽灵槽永远匹配不上，会把整条链判成数据不全。

### 2. 拆该拆未拆的槽

一个槽对着 WDL 的两个参数。**风险不对称**：`read2` 是 `File?`，漏填不报错，
`is_paired = defined(read2)` 变 false，STAR / trim_galore **静默按单端跑完，结果错但一路绿灯**。

- `star::clean_fastq_read` → `clean_fastq_read_r1`(`read1`) + `clean_fastq_read_r2`(`read2`)，旧槽降级为别名行
- `trim_galore::raw_fastq_read` → `raw_fastq_read_r1` + `raw_fastq_read_r2`，同上
- `trim_galore` 的**输出**也拆成 r1/r2——不拆的话 star 新拆出的 r1/r2 在图里没有上游可连，拆了等于白拆（`fastp` 已经是这个形状）
- `cellranger::raw_fastq_read` → `raw_fastq_read_r1`(`fastq_file1`) + `raw_fastq_read_r2`(`fastq_file2`)
- `star::genome_annotation` → `rrna_star_index` + `genome_star_index`（两个必需 File 索引）
- `rsem::genome_annotation` → 改名 `rsem_index`（task 里按目录用 `~{rsem_index}/rsem_ref`，塞 GTF 会直接崩）

### 3. 改命名/方向错的槽

**`bcftools`**：card 的输入就叫 `filtered_vcf`，槽表叫 `unfiltered_vcf`。图是按 `slot_name`
同名串联工具的，于是 `gatk::output::unfiltered_vcf` → `bcftools::input::unfiltered_vcf` 把
Mutect2 的**原始 VCF** 喂给执行 `bcftools view -f PASS` 的步骤。FILTER 注记要
`FilterMutectCalls` 之后才存在——**这条线不报错，只安静地给出空的 PASS 集合**。

GATK 的 WDL 内部就跑了 `FilterMutectCalls`，workflow 同时输出 `unfiltered_vcf` /
`unfiltered_vcf_index` / `filtered_vcf` / `filtered_vcf_index`，槽表只建了前者。这一轮：

- `bcftools::input::unfiltered_vcf` → 改名 `filtered_vcf`，绑 `BcftoolsSomaticPostprocessWorkflow.filtered_vcf`
- 补 `bcftools::input::filtered_vcf_index`（card 里是必需 File，槽表整个漏了；缺了 `ln -sf` 读不到 `.tbi`，**执行直接失败**）
- 补 `gatk::output::filtered_vcf` / `filtered_vcf_index`，`tool_relationship.csv` 的 `T008→T009` 改接过滤后 VCF

### 4. 加数组基数

新增 `io_slot.cardinality` 列，`array` 表示 WDL 侧是 `Array[File]`。单文件槽装不下数组，
只补参数名没用——会给出一个字符串路径，执行端按数组解就崩，或者更糟：只跑了第一个样本。

| 工具 | 槽 | 参数 |
|---|---|---|
| fastqc | `clean_fastq_read` / `raw_fastq_read` | `fastqs`（`Array[File]+`，对它 scatter） |
| multiqc | `quality_control_report` | `qc_files`（N:1 扇入） |
| cnvkit | `tumor_bams` / `tumor_bais` / `normal_bams` / `normal_bais` | 同名，`dimension=sample_role` |
| rmats | `group1_bams` / `group1_bais` / `group2_bams` / `group2_bais` | 同名，`dimension=comparison_group` |

cnvkit 的同下标绑定由 `ValidateCnvInputs` + `scatter(range(length(sample_ids)))` 强制，
形状可以定死；**哪个样本算 tumor、哪组算 case 是业务标注决定的**，槽表只表达形状，
不表达分组语义（rmats 的分组含义全在 `group1_label` / `group2_label` 两个 String 里）。

### 附：WGS 三个流程

师兄 0823 回复："WGS 的三个流程你先按照 wdl 参数补充，这部分语料是很久之前做的，一直没更新。"
即这三个流程的 knowledge card 是陈旧语料，**以 WDL 为准**——原先卡住
`paired_fastq_to_unmapped_bam` 的 `fastq_1` / `fastq_2` 的"参数名要与 card 相同"在这里被豁免。
已按 `ConvertPairedFastQsToUnmappedBamWf.fastq_1/.fastq_2` 补齐，并补上 `dimension=mate`
（`example_inputs.json` 里 `fastq_2` 指的就是和 `fastq_1` 同一个 R1 文件——正是没有 mate 维度时
会发生的错）。

`WholeGenomeGermlineSingleSample`（WGS 单样本分析）和 `JointGenotyping`（联合分型）
**尚未在 `tool_id.csv` / 图谱里注册**，不是"槽没绑定"而是"工具不存在"，需要先立工具节点，
不在本轮范围内。

---

## 顺带发现的、不属于本次映射范围但会咬人的问题

1. **`required` 标注和 WDL 系统性相反。** `gatk` 的 `tumor_bam`/`tumor_bai`/`normal_bam`/
   `normal_bai` 在槽表里仍是 `required=false`，WDL 里全是无默认的必需 `File`。本轮只修正了
   自己动过的行，这批没动——改它会影响配对 WES 匹配器的行为，建议单独立项验证。
2. **`fastp` 声明了 `single_end` 变体，但 `FastpPairedEndWorkflow` 的 `read2` 是 `File`
   （非 `File?`）且 task 无条件展开 `--in2`，跑不了单端。**
3. **样本身份类必需 String 全线无槽。** `sample_id`（几乎每个工具）、`gatk` 的
   `pair_id`/`tumor_id`/`normal_id`（要与 BAM 头 `@RG SM` 一致，填错直接报错）、
   `paired_fastq_to_unmapped_bam` 的 7 个 read-group 元数据。`readgroup_name` 决定 uBAM
   输出文件名，`sample_id` 决定几乎所有输出名，缺了输出槽的实际产物路径在图里不可推导。
4. **QC 边在图里几乎全断。** `samtools` 的 flagstat/stats/idxstats、`trim_galore` 的
   trimming_reports、`fastp` 的 html/json、`star` 的两个 Log.final.out、`featurecounts` 的
   summary——输出槽全都没建，`multiqc` 在图上几乎没有可连的上游。
5. **`samtools` 的 `sorted_dedup_bam` 名不副实。** `remove_duplicates` 默认 `false`，
   此时产出的是 `sorted_bam`（**未去重**），槽名却承诺了 dedup，下游 `featurecounts` 接的就是它。
6. **`rmats_alternative_splicing::output::aligned_bam` 是明确的错槽。** 该 workflow 不产出
   任何 BAM（README：流程从已比对 BAM 开始），且把 RNA 流程的输出标成了
   `DNA_GENOMIC_ALIGNMENT_BAM`，组学类型也错了。
7. **`relationships.csv` 的 `ALLOW_FORMAT` 没有槽级判别力。** 它是工具级 `input_format` 并集
   下放到每个槽，做映射时不能拿它当证据。
8. **`xlrd_vendor_zip` 绑死在共享文件系统上。** 10 个 bulk 工具都有硬编码默认路径的非可选
   File 参数，换环境执行会失败。
9. **`paired_fastq_to_unmapped_bam` 的发布物自身有错**（跟槽表无关，但会误导任何拿样例做
   推断/冒烟的人）：`example_inputs.json` 里 `fastq_2` 指向和 `fastq_1` 同一个 R1 文件；
   `make_fofn` 传的是字符串 `"true"` 而不是 JSON 布尔；workflow 顶层把 `fastq_1`/`fastq_2`
   声明为 `String`，Cromwell 对 String 不做 localization，路径按字面量透传。

---

## 空槽现在会自己说话

`workflow_composer.py`：以前没有 `builder_param` 的槽是**无声 `continue`**，回包给出
`execution_params: {}` 加一份字段完整、看不出异常的推荐，`execution_params_missing` 也是空的
——"零个参数、且一个都不缺"，消费方按 `not missing` 判可提交就会当成能提交。

现在未绑定的数据槽会进 `execution_params_missing`，`reason: "slot_not_bound"`，`param: null`。
三条边界：参考文件槽仍然不报（师兄规则 4）；别名行不报（真实槽自己会报）；
`slot_not_bound` 与 `no_confirmed_path` 不合并（前者要人补目录表，后者要数据侧补 `file_path`）。

配套两处修正：

- `_role_for_input` 原先按 "index" 关键字把 `filtered_vcf_index` 判成参考资源，于是它既不映射
  也不报缺——bcftools 少给一个必需参数还一声不吭。现在数据文件的伴随索引
  （`*_vcf_index` / `*_bam_index` / `*_bai` / `*_tbi`）按数据走。
- `cardinality=array` 的槽返回**全部**匹配路径（规格第 2 条）。走单值那条路只会取一个：
  fastqc 的 scatter 就只跑一个 FASTQ、cnvkit 的队列只算一个样本，都不报错，只是悄悄少做。
  两个槽可以共用一个参数（fastqc 的 raw / clean 都对 `fastqs`），所以是并集去重不是覆盖。

测试见 `tests/test_slot_not_bound_is_reported.py`；本轮迁移脚本见
`scripts/python/reconcile_slots_with_wdl_2026_08_23.py`。
