# Demo 数字最终版（可引用）

> 生成时间：2026-07-24（UTC）  
> 来源脚本：见每节说明。本节为演示时可引用的唯一权威数字，其他报告中的数字如有冲突，以本节为准。

---

## 1. 工具目录

来源：`scripts/python/demo_preflight.py`

| 指标 | 数值 |
|---|---|
| atomic 工具数 | 12 |
| pipeline/task_pipeline 数 | 12 |
| 工具节点总数 | 24 |
| NEXT data 边 | 11 |
| NEXT order 边 | 3 |
| Neo4j 连通状态 | 连通 |

---

## 2. 数据规模

来源：`scripts/gen_demo_facts.py` → `docs/demo_facts.md`

| 指标 | 数值 |
|---|---|
| study 数 | 14 |
| individual 数 | 3,494 |
| sample 数 | 6,918 |
| T1 文件数 | 13,772 |
| T11 文件数 | 15,484 |
| T2 文件数 | 86 |
| T11 中未被 T1 覆盖 | 1,712（HRA000122 696 条 fq.gz + HRA000021 1,016 条 bam） |
| 格式/角色疑似矛盾项 | 0（当前扫描规则未覆盖 T2 的目录错标） |

---

## 3. Study × Pipeline 可行性格子

来源：`scripts/gen_demo_facts.py`（当前修复后版本，状态 ③）

| pipeline | 可行 study 数 | 涉及 study 数 |
|---|---|---|
| `cellranger_workflow` | 2 | 13 |
| `diff_expr_go` | 4 | 13 |
| `diff_expr_kegg` | 4 | 13 |
| `driver_gene_gender_analysis` | 1 | 13 |
| `her2_pfs_survival` | 0 | 13 |
| `immune_infiltration_iobr` | 0 | 13 |
| `paired_fastq_to_unmapped_bam` | 7 | 13 |
| `rnaseq_singletask` | 4 | 13 |
| `rnaseq_unsupervised_cluster` | 4 | 13 |
| `survival_analysis` | 1 | 13 |
| `tmb_survival_analysis` | 1 | 13 |
| `wes_somatic_maf_landscape` | 9 | 13 |
| `wes_somatic_pair` | 2 | 13 |
| `wgcna` | 0 | 13 |
| **合计** | **39 / 182** | — |

### 三个状态对照（供内部说明，演示时只说 39/182）

| 状态 | 可行格数 | 口径 |
|---|---|---|
| ① Round 3 assay 校验前 | 59 | `feasibility_truth_table.md`， assay 未实施，存在 20 个 assay 假阳性 |
| ② 本轮修复前 | 5 | `gen_demo_facts.py` 直接读原始 T11.csv，是 bug |
| ③ 本轮修复后 | 39 | `gen_demo_facts.py` 改用 `matcher.t1 + matcher.t2` |

---

## 4. 零覆盖 Pipeline

来源：`scripts/gen_demo_facts.py`

- `her2_pfs_survival`
- `immune_infiltration_iobr`
- `wgcna`

---

## 5. 可用体细胞 WES 配对

来源：直接调用 `assess_feasibility` + `_assess_wes_somatic_cases`，基于 `matcher.t1`。

| study | 合格配对 case 数 | 状态 |
|---|---|---|
| `HRA000873` | 1,015 | 已登记角色规则，可用 |
| `HRA006499` | 13 | 已登记角色规则，可用 |
| **合计** | **1,028** | 演示时引用此数 |

> 未登记角色规则的 WES study（如 HRA000071、HRA001272、HRA003107、HRA007169）不计入。若后续经人工确认补录规则，该数字可能上涨。

---

## 6. 七条演示查询的绑定与状态

来源：`docs/demo_queries.json`（`DEMO_REPLAY=1` 三次回放，全部稳定）

| 查询 | workflow_mode | 绑定 study | study strategy | selection / orchestration |
|---|---|---|---|---|
| 配对肿瘤正常 WES | custom | `HRA000873` | WES | no_match / no_match |
| trim_to_fastp | custom | `HRA000074` | RNA-Seq | draft / draft |
| 双端 FASTQ RNA-seq 上游 | standard | `HRA000074` | RNA-Seq | ready / ready |
| TPM 聚类 | standard | `HRA000074` | transcriptomic（T2） | missing_assets / missing_data |
| GO+KEGG 富集 | standard | `HRA000074` | transcriptomic（T2） | ready / ready |
| 单样本 WES FASTQ | custom | `HRA000071` | WES | draft / draft |
| MAF 能力 | capability | N/A | N/A | information / information |

### 与覆盖率表的交叉验证

- RNA-seq 类查询（2、3）绑定 `HRA000074` / RNA-Seq ✅ 与 `rnaseq_singletask` 可行一致。
- 配对 WES 查询（1）绑定 `HRA000873` / WES ✅ 与 `wes_somatic_pair` 可行一致。
- 此前“查询 3 ready 但 `rnaseq_singletask` 零覆盖”的矛盾已消除。

---

## 7. 测试与回放

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单元测试 | `python -m unittest discover -s tests` | **64 OK, skipped=3** |
| 演示回放 | `python scripts/a4_verify_replay.py` | **7/7** |
| 环境预检 | `python scripts/python/demo_preflight.py` | **7/7** |

---

## 8. 演示黑名单（D10 最终版）

来源：`docs/demo_readiness_full.md`

| 查询/类型 | 原因 |
|---|---|
| 依赖 `wes_somatic_maf_landscape` / TMB / 生存分析的查询 | `T2` 中部分目录被错标为 `format=maf`，存在假阳性 |
| hello / 你好 / “我有数据” / 超长输入 | 回答 generic，不能体现系统能力 |
| “用 SuperTool2000 分析我的数据” | LLM 没识别为伪造工具，gap 不够果断 |

已从黑名单移除：

- **“配对肿瘤正常 WES FASTQ”**：修复后绑定 `HRA000873`，并稳定输出 gatk 缺少配对输入槽的 `decomposition_gaps`，可现场演示。
- **“单样本 WES FASTQ 想做变异检测和注释”**：绑定到 `HRA000071` / WES 是正确行为；`project.data_types` 是项目级聚合字段，文件级 `T1.strategy` 更具体，系统用后者。

---

## 9. 保留的已知风险

| 风险 | 影响 | 当前处理 |
|---|---|---|
| `T2` 中 `format` 错标 | MAF 类 pipeline 假阳性 | 未自动拦截，已在 `docs/round2_report.md` 扫描 |
| `T2.strategy` 存在错填值 | 未来若纳入 assay 校验会误判 | 当前不参与 assay 校验 |
| `HRA000071` 元数据冲突 | 单样本 WES 查询绑定到矛盾 study | 已列入黑名单 |
| `HRA001272/000071/003107/007169` 未登记角色规则 | 可用 somatic case 数停留在 1,028 | 需人工确认是否补录规则 |
