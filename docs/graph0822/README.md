# 0822 图谱全量测试记录

这一份记的是 0822 图谱接上之后跑的全量测试：**问了哪 151 道题、每题期望什么、实际
答成什么样、查出的问题怎么修的**。

写这份东西的理由很直接：前面几轮测试的题目散在四个探针脚本和若干测试文件里，跑分
只留在终端里。谁要复核"到底测没测过 XX 情况"，得把五个文件翻一遍。所以这里做两件事：

* `all_test_questions.json` —— 151 道题的全量清单，**从题目源文件导出**，不是手抄的。
  题目改了重跑 `scripts/collect_test_questions.py` 就同步。手抄的清单从写下那天起
  就开始过期，而过期的清单比没有清单更糟：它看着像"全部测试问题"，漏掉的偏偏是最新
  加的那批。
* `probe_*.json` —— 每套题的逐条跑分，含实际 status、推荐流程、绑到的资产、失败原因。

---

## 1. 图谱与目录基线

跑测试之前先核对，免得拿一个不对的库测出一堆假结论。与生产库逐项对上：

| 项 | 值 |
| --- | --- |
| 节点 | 80,679 |
| 关系 | 352,468 |
| label | 11（project / study / individual / sample / tool / T1 / T2 / format / function / datalevel / modal） |
| 关系类型 | 14 |
| 工具 | 51 |
| 目录方法 | 50（原子 11 + 业务流程 39） |

图里的 18 种 format 及其数量（这张表后面第 4 节要用）：

| format | 数量 | format | 数量 |
| --- | ---: | --- | ---: |
| DNA_VARIANT_VCF_GENERAL | 8310 | RNA_SPLICEJUNCTION_TAB | 430 |
| DNA_ALIGNMENT_BQSR_BAM | 6177 | SCRNA_MATRIX_H5 | 403 |
| DNA_ALIGNMENT_INDEX_BAI | 6177 | DNA_SOMATIC_SV_VCF | 286 |
| DNA_VARIANT_INDEX_TBI | 5788 | VISUALIZATION_RESULT | 52 |
| RNA_TRANSCRIPTOME_ALIGNMENT_BAM | 3288 | BIO_DATA_CONTAINER_OBJECT | 18 |
| MUTATION_ANNOTATION_FORMAT_MAF | 2355 | SOMATIC_CNV_TSV | 4 |
| OTHER_UNCLASSIFIED_DATA | 1081 | CLINICAL_DATA_EXCEL | 2 |
| DNA_VARIANT_STATS_REPORT | 603 | SCRNA_MATRIX_H5_ZIP | 2 |
| TABULAR_BIO_DATA | 592 | METADATA_SAMPLE_INFO | 2 |

---

## 2. 151 道题都在测什么

| 套件 | 题数 | 问什么 | 判什么算过 |
| --- | ---: | --- | --- |
| `probe_30_prompts` | 30 | 基础能力面：能做什么、怎么问、缺数据怎么答 | 按每题声明的 status / 推荐 / 理由逐条判 |
| `probe_robustness` | 68 | 模糊表述、同义改写、脏输入、越界要求、注入尝试 | 同一语义的不同问法必须给同一类结论；越界必须拒绝 |
| `probe_privacy_and_kind` | 20 | 病人年龄/姓名等个人数据，以及与生信无关的闲聊 | 涉及个人隐私一律拒绝；无关问题不许硬套流程 |
| `probe_graph_grounded` | 23 | 图谱实证：期望值先查图再写 | 有这个模态必须绑到数据；没有必须说没有 |
| `test_named_tool_substitution` | 10 | 点名了目录里没有的工具（Salmon/HISAT2/Kallisto/Bowtie2） | 必须拒答并指名道姓；链里不许出现被要求换掉的工具 |
| **合计** | **151** | | |

第四套题的期望值全部是先查图再写的，不是"我觉得应该"。例如：

```cypher
MATCH (t:T2) WHERE toLower(t.file_name) =~ '.*(fpkm|tpm|count|matrix).*'
RETURN t.study_accession, count(*)
```

查出 14 个队列有表达矩阵；HRA000001 和 HRA000021 只有 WGS 的 BQSR.bam，一张矩阵都没有；
scRNA 的 h5 只在 HRA001748 和 HRA005191；MAF 只在 HRA000873/001272/001749/006499/007169/016026。
正反两面因此都能真判——**"该有的必须绑上"和"没有的不许拿别的模态顶上"**。

---

## 3. 这一轮查出的最严重的一个问题

### 症状

```
问：把 RNA-seq 标准流程中的 RSEM 换成 Salmon
答：selection_status=ready
    链 = fastp -> star -> rsem -> samtools -> featurecounts
```

用户要求把 RSEM 换掉，回包里 RSEM 还在，标 ready，`unsupported_reason` 为 null。

这条链**完全合法**：工具都在目录里、NEXT 边都对、终产物确实是表达矩阵，所有校验器
一条都拦不住。光看回包发现不了——这是这个项目反复出现的那类错：**错得像对**。
确定性复现 6/6，同类还有「用 HISAT2 代替 STAR」拿到 star、「用 Salmon 做定量」拿到 rsem。

### 根因有两层，都是"规则盖过 LLM"

**第一层，提示词漏了触发词。** 第 6 条的硬约束词表只列了"只要/不要/不做/不能修改/
已有/只有"，不含"换成/代替/改用"；第 8 条只在**终产物**不可达时才清空 candidates，
而"表达矩阵经 RSEM"是可达的。于是规划器判 ready 并不违反当时的提示词。补了第 6b 条。

**第二层才是要命的。** 补完提示词后规划器**判对了**——`analysis.checks` 原话是
"用户逐字点名 HISAT2，目录无该工具，按硬约束清空 candidates"，candidates 交的就是空。
然后两处确定性回退把它改写了：

* `_top3_llm_decision` 里的链回退，凭关键词（命中 rna-seq、没命中 maf/vcf/wes）把标准链
  塞了回去，链里赫然还是 star，整个回包标 ready。
* `_build_recommendations` 里的推荐回退，把规划器主动清掉的 `rnaseq_singletask`
  （内置 STAR/RSEM，正是用户要排除的那套）又补了回来，顺带把顶层状态从 `unsupported`
  顶成了 `information`——"做不了"变成"给你推荐"。

这直接违背了"答案都要来源于 LLM"这条要求：一次正确的拒答被关键词规则覆盖掉了。

### 修法：判据不是"交没交链"，是"有没有**主动**拒答"

第一版我把判据写成 `normalized and not accepted`（规划器交了链、但全被校验拦下才回退），
结果 `test_16_empty_model_output_falls_back_to_reviewed_rnaseq_chain` 挂了
（`'information' != 'ready'`）。翻开那条测试才看清：它调的是 `self.top3(None)`——
模型**什么都没产出**。而 `test_15_unsupported_is_not_empty_success` 锁的是模型**主动拒答**。
两条测试早把意图分清了，缺的只是一个能区分它们的判据。我第一版键错了信号。

正确判据落在新增的 `WorkflowComposer._planner_declined()`：规划器留没留下拒答理由
（`unsupported_reason` / `unsupported_kind`）。

* 留了 → 它是**看着这道题**做的决定，必须原样透出去，两处回退都不许动。
* 什么都没留（decision 为 None、解析失败、API 挂了）→ 才是这两处回退要兜的"空输出"。

两处回退各自加一个 `not self._planner_declined(decision)` 闸门，共用同一个判据。

### 回归防护

新增 `tests/test_named_tool_substitution.py`，10 道题分两半：

* 5 条**必须拒答**（Salmon / HISAT2 / Kallisto / Bowtie2 / Salmon 定量），断言四件事：
  链里不许出现被换掉的工具、拒答不许被改写成 ready、理由必须指名道姓说缺哪个工具、
  推荐里不许出现 `rnaseq_singletask`。
* 5 条**必须照常出链**（fastp 换 trim_galore、MultiQC、三种标准上游问法）——这是收紧
  判据时的连坐检查。上面那几条断言只要把两处回退整个删掉就能全绿，但那会让标准
  bulk RNA-seq 上游重新在 ready / information 之间抖动，正是回退当初要治的毛病。

另有一条前提自检 `test_the_named_tools_really_are_absent_from_the_catalog`：哪天 Salmon
真被原子化了，这个文件该在这里响亮地挂掉，而不是继续以"必须拒答"的名义把一个已经
支持的需求判成不支持。

---

## 4. 两条不是代码 bug、但会让结果不对的数据质量问题

这两条得师兄那边改目录，代码侧改不了（图谱是只读的）。

### 4.1 九条流程要 rds，图里一个 rds 都没有

查法（`data/csv/catalog/relationships.csv`）：`ALLOW_FORMAT -> catalog_format:rds`
的 io_slot，再沿 `HAS_INPUT_SLOT` 反查 tool_id，得到 9 条：

```
breast_cellchat            celltype_case_control_de   dataset_downstream
dataset_matrix_annotation  immunotherapy_cellchat     ipf_trajectory_regulon
lung_tme_annotation_cnv    scrna_cell_communication   tcell_intervention
```

而第 1 节那张表里，图中单细胞只有 `SCRNA_MATRIX_H5`（403）和 `SCRNA_MATRIX_H5_ZIP`（2），
**一个 rds / Seurat 对象都没有**。这 9 条流程在当前图谱上永远填不满输入槽。

h5 矩阵和 Seurat 对象不是一回事——后者带聚类、降维、注释结果。真正危险的不是"填不上"，
而是**松绑**：拿 h5 顶上去，回包会显示"数据已就绪"，执行端才会炸。所以 G04/G05 两题
就钉这一条：这 9 条流程谁报 `available` 谁就算错。

### 4.2 两条流程声明了零个输入槽

`hvg_pca_gmm` 和 `bootstrap_stability` 没有任何 `HAS_INPUT_SLOT`，因此永远绑不到数据。

### 4.3 0821 交付的 sample 字段口径 —— 详见 `docs/0821_sample字段口径.md`

0821 那版 sample 表把若干**研究级别的默认值**覆盖到了**样本级别的事实**上：
`tumor_descriptor` 全库压平（Metastatic 210→0、Recurrent 407→0，反而有 1476 个
`tissue_type=Normal` 的样本被填上了肿瘤分期）、`biospecimen_anatomic_site` 变成研究级
原发部位（HRA001272 十种转移灶全写成"肝"）、`gender` 大小写不统一、`specimen_type`
新增分号多值 `Organoid;Patient_Solid_Tissue`（486，用等号比会静默漏掉）。

坏值不是空也不是乱码，每格都填满、单看都合理，查回包发现不了——**又是一次
"错得像对"**，和第 3 节那个 Salmon bug 同一个形状；这次是拿样本名后缀
（`M019_LM1_` = 肺转移）当独立信号才验出来的。

四条口径已落到代码：`normalize_gender()` / `specimen_tokens()` / `sample_lesion()` /
`UNRELIABLE_SAMPLE_FIELDS`，回归防护见 `tests/test_sample_field_semantics.py`
（11 条）。同一份结论的 light 版落在 `web/manual_compact.md`——那边 LLM 直接写
Cypher，规则写给模型看就够；这边代码自己查图，**不改代码等于没改**。

---

## 5. 我自己写错的期望（记下来，因为这类错最容易被"改测试让它绿"糊弄过去）

`probe_graph_grounded` 的 G04–G07 四题，初版我写成 `data_available=True`，跑出来全"失败"。
查下去发现**是期望错了，不是产品错了**：我照着 `dataset_downstream` 一条流程的槽位反推
期望，没去看图里还有别的流程接得住。

改期望是对的，但改法有讲究。我先改成了"整题都不许报 available"，G05 又挂——系统推的是
`cellranger_workflow` 绑 `HRR1320767_f1.fq.gz`，而 cellranger 声明的输入本来就是 FASTQ，
HRA005191 也确实有 scRNA FASTQ。**这个 available 是诚实的**，是我的判据太宽。

所以最终改成了带范围的判据：`slot_unsatisfied` 可以是 `True`（整题）也可以是一串
pipeline_id（只锁这几条）。G04/G05 只锁 4.1 节那 9 条 rds 流程，别的流程照常可用。

留着这四题而不是删掉，是因为它们的共同形状——"图里有看着像的文件，但不是流程要的东西"——
恰恰是最容易被松绑掉的一类。

---

## 6. 跑分

跑的是本地 Neo4j（`DATA_MATCHER_MODE=neo4j`）+ 真实 LLM（glm-5.3），没有规则降级路径。

| 套件 | 结果 |
| --- | --- |
| 单元测试全量（含新增套件） | **Ran 156, OK (skipped=5)**（1114s） |
| `test_named_tool_substitution` | **7/7 OK**（446s） |
| `probe_30_prompts` | **30/30** |
| `probe_robustness` | **68/68** |
| `probe_privacy_and_kind` | **20/20** |
| `probe_graph_grounded` | **23/23** |
| **151 道题** | **全绿** |

5 条 skip 全部是"缺图谱/缺 LLM 时无从断言"的守卫，每条的 skip 文案都写了
**跳过不等于通过**。

### 6.1 分组明细

`probe_30_prompts` 30/30：

```
A 能力问答 5/5   B RNA-seq 上游 5/5   C WES/WGS 5/5
D 未原子化需求 6/6   E 输入方法冲突 4/4   F 数据可用性 5/5
```

`probe_robustness` 68/68：

```
A 换说法的正常需求 14/14   B 边界与歧义 10/10   C 非生信提问 10/10
D 对抗与脏输入 13/13       E 越权与信息类 6/6   F 癌种与队列 8/8
G 样本角色 4/4             H 自由参数申报 3/3
```

`probe_privacy_and_kind` 20/20，`probe_graph_grounded` 23/23（G/N/X/L 四组各自全过）。

### 6.2 已知的非确定性（LLM 抖动，非本轮引入）

**这一轮 151 题全绿，但下面几条不能因此就算"修好了"**——它们本来就不是每次都挂。

* **F08**（跨癌种队列绑定）：这次跑过了，属于会抖的那批。上一轮挂的时候查过成因：
  `candidate_count=0`，链回退根本没跑，`diff_expr_go` / `diff_expr_kegg` 两条推荐是
  LLM 自己给的，所以推荐回退的 `not values` 闸门压根没轮到求值。确认与本轮改动无关。
* **K06**：约 1/40 的概率抖动。
* **S02**、以及 study 范围的能力类提问，会在 `unsupported`/rec=0 与 `information`/rec=3
  之间交替。

这三条记在这里而不是"修掉"，因为它们的成因是 LLM 输出本身有方差；用确定性规则去
压平它，就是第 3 节那个 bug 的成因——那次正是"想让同一道题别在 ready 和 information
之间跳"的回退，把一次正确的拒答改写成了错误的 ready。

---

## 7. 文件

| 文件 | 内容 |
| --- | --- |
| `all_test_questions.json` | 151 道题的全量清单，含每题期望值 |
| `probe_30_graph.json` | 30 题逐条跑分 |
| `probe_robustness_graph.json` | 68 题逐条跑分 |
| `probe_privacy_kind_graph.json` | 20 题逐条跑分 |
| `probe_graph_grounded.json` | 23 题逐条跑分 |
| `probe_30.json` / `probe_privacy.json` | 图谱接上**之前**的旧跑分，留作对照 |

复跑：

```bash
python3 scripts/collect_test_questions.py
```

```bash
env $(cat /tmp/local_graph.env | xargs) DATA_MATCHER_MODE=neo4j python3 -m unittest discover -s tests -t tests
```
