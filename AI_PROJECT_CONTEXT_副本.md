# bio-pipeline-kg-matcher — AI 上下文文档

> 本文档面向 AI 读者（代码助手/代理），目标是提供**完整、精确、可操作**的项目上下文，而不是人类导读。
> 所有事实以 2026-07-23 的代码状态为准，关键结论附 `文件:行号`。修改代码前请先读完第 1、4、8、10 节。

---

## 1. 项目是什么

自然语言 → 生信工作流编排器。用户用中文/英文描述需求（"我有双端 FASTQ 想做 RNA-seq 上游分析"），系统输出一份**工具链编排契约**（`tool-chain/v1`），供下游执行端（agent）物化执行。系统本身**不执行任何生信任务**，只做：意图理解、流程选择/组链、结构校验、数据资产匹配。

核心设计约束（不可违反）：

1. **Neo4j 是工具目录的唯一运行时真源**。本地 CSV 只用于数据资产匹配和显式同步（`sync_neo4j_tool_catalog.py`）。Neo4j 不可用时工具目录为空，系统失败关闭（fail closed），不回退到任何本地 WDL/旧实现。
2. **工具闭集**：LLM 只能从 Neo4j 登记的 12 个 atomic tool 组链，程序会做闭集校验；任何编造 tool_id、编造 input/output 名、编造 NEXT 边的输出都会被拒绝。
3. **pipeline 拆解进行中**：12 个 pipeline 目前只有 `rnaseq_singletask` 被同事拆解成 7 步锁定 recipe（HAS_STEP）。其余 pipeline 是 pipeline-level tool。要修改未拆解 pipeline 的内部步骤时，系统必须返回 `blocked_by_incomplete_method_decomposition`，**不得编造拆分**。
4. **运行参数不属于编排**：线程数、内存等运行参数由执行端负责，系统不收集、不展示、不影响编排状态。只有**用户样本数据**（FASTQ、矩阵、MAF、Clinical/MetaInfo）缺失才会产生 `missing_assets`。GTF、参考基因组、STAR/RSEM 索引属于执行端托管资源（`EXECUTION_MANAGED_ASSET_ROLES = {"reference_file"}`，`workflow_composer.py:60`）。

## 2. 顶层结构

```
bio-pipeline-kg-matcher/
├── workflow_composer.py      # 2038 行。核心编排器：三类请求路由、两阶段 LLM 协议、custom 校验、资产绑定
├── pipeline_router.py        # 1682 行。意图→pipeline 打分匹配、CSV 数据资产匹配、可行性评估、agent_input 装配
├── intent.py                 # 641 行。LLM 调用封装（OpenAI 兼容接口）、意图抽取、JSON 容错解析
├── runtime_config.py         # 122 行。.env.local 加载、LLM/Neo4j 配置默认值、健康状态
├── server.py                 # 203 行。MCP stdio server（无第三方依赖），暴露 4 个工具
├── app.py                    # 265 行。HTTP 后端（标准库），服务 demo.html：GET /、POST /api/ask、GET /api/health
├── neo4j_observability.py    # 385 行。Neo4jClient：只读连通性、目录观测
├── run_bench_deepseek.py     # 93 行。DeepSeek bench 入口
├── run_bench_full.py         # 121 行。全量 bench 入口
├── requirements-llm.txt      # requests>=2.31,<3
├── requirements-neo4j.txt    # neo4j==5.28.4
├── .env.local                # 私密配置（LLM_API_KEY、NEO4J_PASSWORD），不进版本库；模板见 .env.local.example
├── .mcp.json                 # MCP 客户端注册配置
├── 项目说明.md / README.md    # 人类文档（本文件是 AI 文档）
├── MCP连接文档.md             # MCP 接入说明
├── FINAL_DELIVERY_AUDIT.md   # 交付审计
├── demo.html / demo-original.html  # 交互演示页（app.py 服务）
├── cypher/
│   ├── import/               # 00_clear → 05_validation：从 CSV 建【数据图】（study/sample/run/T1/T2 等）
│   ├── schema/  maintenance/ # schema 与维护脚本
│   └── query_templates/      # ⚠️ 已过时：schema 与现行图脱节（详见第 10 节），运行时不引用
├── data/csv/
│   ├── entities/             # 规范化 KG 实体：study/project/individual/sample/tool.csv + 旧版 T1/T2 平铺表
│   ├── relations/            # 关系表；tool_relationship.csv 是 curated NEXT 边（工具图）的真源
│   └── reference/            # 参考/枚举数据
├── scripts/python/           # validate_csv.py、sync_neo4j_tool_catalog.py、import_runner.py、
│                             # fix_bam_artifact_contracts.py、fix_qc_report_contracts.py、run_live_regression.py
├── scripts/shell/            # run_import.sh/.ps1、RecursiveClean-CSV.ps1
├── tests/                    # test_workflow_composer.py（主力，63 个用例）、test_runtime_integrations.py（真实集成，默认跳过）
├── docs/                     # agent_tool_chain_contract.md（契约说明）、agent_tool_chain_schema.example.json、
│                             # bio_pipelines_bug_report.md（质量 gate 来源）、model_routing_examples.md、
│                             # neo4j_next_relationship_review.md、image_four_questions_live_results_*.json
└── incoming/bio_pipelines_repo/  # 上游 pipeline 仓库副本（历史审查用，运行时不读）
```

## 3. 请求生命周期（`WorkflowComposer.plan()`，`workflow_composer.py`）

一次 `plan(nl_text, top_k=5, force_custom=False)` 的完整路径：

1. **capability 短路**：`_capability_intent()`（`:700-790` 附近）先做确定性规则判定——是否为目录浏览（"能做什么"/"有哪些流程处理 MAF"/"有哪些原子工具"）。命中则走 `_capability_plan()`（`:912`），直接查 Neo4j 目录，不调 LLM，返回 `selection_status=information`。注意：含"选哪个流程/用哪个"等 `RECOMMENDATION_HINTS` 的问句**不是** capability，是单项路由。
2. **stage-one LLM（标准流程选择）**：`_llm_decision()`（`:377`）构造闭集提示词，只提供 12 个 pipeline/task-pipeline 的菜单，要求 LLM 输出 `{mode, reason, requirements, pipeline_ids, reference_pipeline_ids, pipeline_assessments, uncovered_requirements}`。`FORCE_RULE=1` 时跳过 LLM，返回 `(None, {"used": False})`。
3. **模式校正**（`:466-496`，按优先级）：
   - `_explicit_customization()` 检出显式内部修改（换/删/插/重排步骤）→ 强制 `mode=custom`；
   - 否则 `_known_standard_pipeline_ids()` 的保守组合规则（`:807-856`：突变景观+TMB、GO+KEGG 联合、RNA FASTQ 完整上游、FASTQ→uBAM 四种已知组合）可确认 `mode=standard`。**2026-07-23 起：LLM 实际跑通时（`stage_one_metadata.used=True`）不再清空 `pipeline_assessments`/`uncovered_requirements`**，只确认 mode 和 ids；
   - `_standard_has_coverage_gap()`（`:661`）：任一被选中 pipeline 的 assessment 出现 `input_match=mismatch`、`functional_coverage∈{partial,none}`、`output_match∈{partial,mismatch}`，或存在 `uncovered_requirements` → 降级为 custom，`pipeline_ids` 移入 `reference_pipeline_ids`。
4. **stage-two LLM（仅 custom）**：提供 12 个 atomic tool 的完整契约菜单（input/output 名、artifact、formats、allowed_next_tool_ids），要求输出 `{steps, decomposition_gaps}`。prompt 内含大量防混淆规则（`:501-553`）：uBAM≠比对后 BAM、transcriptome_bam≠genomic aligned_bam、STAR 主输出名是 `aligned_bam`、MultiQC 用 `depends_on` 且不解析表达矩阵等。
5. **分支装配**：
   - standard → `_standard_plan()`（`:1023`）：按 pipeline_ids 查契约、附 `quality_gate`。**LLM 判 standard 但没给 ID 时，只有规则兜底路径才允许取 router 候选第一名（`:1043`）**；
   - custom → `_custom_plan()`（`:1105`）：`_validate_custom_steps()` 校验（见第 5 节）。
6. **agent_input 装配**（`pipeline_router.build_agent_input:1479` + composer `_apply_agent_contract`）：路由数据匹配结果 → `_build_assets()`（角色化）→ `_standard_tool_chain()`/`_custom_tool_chain()` 绑定资产 → feasibility → 最终 `selection_status`/`orchestration_status`。

## 4. Neo4j 工具图（运行时真源）

### 4.1 节点与规模

- 24 个工具节点（`:Tool` + `:tool_id` 标签）：12 atomic + 11 pipeline + 1 task_pipeline。
- 另有数据图节点（由 `cypher/import/` 建立）：`t1`(15692)、`run`(8354)、`sample`(6918)、`individual`(3494)、`study`(14)、`project`(11)、`cohort`(26) 等。注意库中存在**两套平行工具图**（`cypher/import/02-04` 建的 `(:Tool {tool_id:'T01'})` 与 sync 脚本建的 `(:tool_id:Tool {tool_id:'fastp', catalog_id:'T01'})`），运行时只读后者。

### 4.2 12 个 atomic tool（custom 闭集）

| tool_id | 功能 | 语义输入 → 语义输出 |
|---|---|---|
| fastqc | 测序数据质量评估 | raw/clean FASTQ → QC report |
| fastp | FASTQ 质控/修剪/UMI | raw FASTQ → clean FASTQ |
| trim_galore | 接头/低质量修剪 | raw FASTQ → clean FASTQ |
| bwa | DNA 比对 | clean FASTQ + 参考 → aligned BAM |
| star | RNA 比对/去 rRNA/融合 | clean FASTQ + 注释 → aligned_bam / transcriptome_bam / clean FASTQ |
| samtools | BAM 排序/索引/去重 | aligned BAM → sorted_dedup BAM |
| rsem | 基因/转录本定量 | transcriptome BAM + 注释 → TPM/FPKM |
| featurecounts | 基因水平计数 | sorted_dedup BAM + GTF → raw counts |
| gatk | BQSR/变异检测 | sorted_dedup BAM + 参考 → unfiltered VCF |
| bcftools | VCF 过滤/标准化 | unfiltered VCF → filtered (PASS) VCF |
| snpeff | 变异功能注释 | filtered VCF + 数据库 → annotated VCF |
| multiqc | 汇总质控报告 | QC report → QC report（terminal） |

### 4.3 21 条 curated NEXT 边（2026-07-23 同步后）

```
fastp   → fastqc, bwa, star, multiqc
fastqc  → bwa, trim_galore, multiqc
trim_galore → star
bwa     → samtools
star    → rsem, samtools, multiqc
samtools→ gatk, featurecounts, multiqc
gatk    → bcftools, multiqc
bcftools→ snpeff
rsem / featurecounts / snpeff → multiqc
```

真源是 `data/csv/relations/tool_relationship.csv`（T01=fastp … T12=MultiQC），经 `scripts/python/sync_neo4j_tool_catalog.py --apply` 写入 Neo4j，边带 `source='curated-next-csv'` 属性；`--apply` **只**增删该来源的 NEXT 边，不碰工具定义、slot 或其他关系。custom 校验中 `from`/`depends_on` 的每条衔接都必须存在于这张表。

### 4.4 12 个 pipeline tool（standard 闭集）

| pipeline_id | 输入（必需） | 主要输出 | 拆解状态 |
|---|---|---|---|
| rnaseq_singletask | 双端 FASTQ（+托管参考） | aligned BAM、count 矩阵、TPM/FPKM、QC | **已拆解**：fastqc→trim_galore→star→{rsem, samtools→featurecounts}→multiqc（7 步 HAS_STEP 锁定 recipe） |
| paired_fastq_to_unmapped_bam | 双端 FASTQ | uBAM | pipeline-level |
| diff_expr_go | 表达矩阵（FPKM/TPM） | 差异表、GO 富集 | pipeline-level |
| diff_expr_kegg | 表达矩阵 | 差异表、Reactome 富集（⚠️ 名字叫 KEGG 实际做 Reactome，目录数据待同事更正） | pipeline-level |
| rnaseq_unsupervised_cluster | **raw count 矩阵** | 聚类分配、稳定性 | pipeline-level |
| wgcna | **raw count 矩阵** + clinical + metainfo | 模块/hub 基因 | pipeline-level |
| immune_infiltration_iobr | TPM 矩阵 + clinical + metainfo | CIBERSORT 组分 | pipeline-level |
| her2_pfs_survival | TPM 矩阵 + 生存 clinical + metainfo | KM、log-rank | pipeline-level |
| wes_somatic_maf_landscape | somatic MAF | oncoplot、统计、过滤后 MAF | pipeline-level |
| survival_analysis | MAF + 生存 clinical + metainfo | KM、Cox | pipeline-level |
| tmb_survival_analysis | MAF + 生存 clinical + metainfo | TMB 表、KM | pipeline-level |
| driver_gene_gender_analysis | MAF + 含性别 clinical + metainfo | 性别分层统计/图 | pipeline-level |

（`wes_somatic_pair`、`cellranger_workflow` 在数据 profile 和 quality gate 中有登记，但是否在 Neo4j 目录以运行时查询为准。）

## 5. custom 校验规则全集（`_validate_custom_steps`，`workflow_composer.py:1161`）

LLM 给的每个 step 依次校验，任何一条失败 → `validation.ok=False`：

1. `step_id` 唯一且匹配 `^[A-Za-z_][A-Za-z0-9_.-]*$`（纯数字 ID 会被 `_normalize_custom_step_ids` 规范化为 `step_N` 并记 warning）；
2. `tool_id` 必须在 12 个 atomic tool 闭集内；
3. input 名必须逐字匹配该工具的注册 input；字符串绑定自动规范化为 `{"asset_role": ...}`；
4. `from` 只能引用**已出现**的 step（前序引用/自引用/环在构造上不可能通过）；
5. `from` 的 output 名必须逐字匹配源工具注册 output；artifact 必须相同，唯一登记的子类兼容是 `ARTIFACT_COMPATIBILITY = {("sorted_dedup_bam", "aligned_bam")}`（`:62`）；
6. 每个 `from` 和每个 `depends_on` 都必须满足 `(source_tool, target_tool) ∈ NEXT 边集`；
7. **连通性（2026-07-23 新增）**：非首步必须至少有一个 `from` 或 `depends_on`；纯 `asset_role` 绑定的非首步报错"未与前序输出衔接"。这堵住了"全 asset 绑定拼假链"的绕过路径；
8. 未绑定的必需 File 输入进入 `required_external_inputs`（warning，不是 error；`reference_file` 角色除外——执行端托管）；
9. `decomposition_gaps` 非空 → 强制 `ok=False`，`execution_status=blocked_by_incomplete_method_decomposition`；
10. `metadata.used=False`（LLM 没跑）→ 强制 `ok=False`，不伪造自助餐链。

## 6. 资产角色体系与数据匹配（`pipeline_router.py` + composer）

### 6.1 角色（2026-07-23 起细分 count/TPM）

文件角色由 `_role_of_file()`（`pipeline_router.py:359`）按文件名/格式推断：`fastq`、`clinical`、`metainfo`、`maf`、`bam`、`vcf`、`expression_count`（文件名含 count/counts/featurecounts/htseq）、`expression_abundance`（含 fpkm/tpm/rsem/abundance）、`expression`（仅 "genes" 等通用信号）、`other`。

兼容规则 `_role_satisfies()`（`:319`）：**通用 `expression` 与两个子类型互相兼容；`expression_count` 与 `expression_abundance` 互不兼容**。也就是说 TPM 矩阵喂不了要 raw counts 的聚类/WGCNA，count 矩阵也喂不了要 TPM 的免疫浸润/diff_expr——此前这是静默通过的。

pipeline 侧需求由 `DATA_PROFILE_TEMPLATES`（`:136`）+ `PIPELINE_DATA_PROFILE_KEYS`（`:185`）定义：`count_matrix` profile 要 `expression_count`；`expression_only`（diff_expr_go/kegg）要 `expression_abundance`；`expression_clinical`（wgcna/immune/her2）要 `expression` + clinical + metainfo；`mutation_only`/`mutation_clinical` 要 maf（±clinical/metainfo）；`paired_fastq` 要 fastq。

### 6.2 composer 资产角色（`_contract_asset_role`，`:1701`）

把路由层角色映射为契约角色：`count_matrix`、`expression_matrix`、`expression_file`（无 count/丰度信号的通用表达文件）、`clinical_file`、`sample_metadata`、`maf_file`、`fastq_r1`/`fastq_r2`/`fastq_file`、`bam_file`、`vcf_file`、`reference_file`、`data_file`。`_select_asset()`（`:1867`）只允许：精确角色匹配；`fastq_file` 可回退到 r1/r2；`count_matrix`/`expression_matrix` 可回退到**通用 `expression_file`**；`data_file` 回退到任意资产。**count 与 abundance 之间禁止互相降级**。

### 6.3 R1/R2 配对（2026-07-23 修复）

`_paired_fastq_groups()`（`pipeline_router.py:345`）：配对键 = `sample_accession` 或 `run_accession`，缺失时退化为文件名主干（去掉 `_f1/_r2/read1` 等后缀和扩展名）。只有同键的 R1+R2 才算成对——不再按列表位置凑对（此前 tumor R1 可能配到 normal R2）。`assess_feasibility()`（`:384`）对 paired 流程要求至少 1 对（`wes_somatic_pair` 2 对）同源读对；两个 R1 文件不再算"数据齐全"。

### 6.4 数据图与匹配

`CsvKGDataMatcher`（`:492`）读 `data/csv/`：规范化实体（entities/）为准，旧 T1/T2 平铺表只补 `file_path` 等字段。匹配按 strategy（WES/RNA-Seq）、组学描述、format 打分，产出 cohort/file 候选和 data_combinations。已知噪声：`pipeline_router.py:577-600` 有针对特定 HRA 编号的硬编码加分（demo 调优痕迹）；HRA000071/HRA000074 是疑似重复的 CGGA 队列；bulk 查询可能匹配到 scRNA-seq 队列。

## 7. 对外接口

### 7.1 MCP stdio（`server.py`）

4 个工具：`route_pipeline_request`（主入口）、`list_pipeline_capabilities`、`list_workflow_methods`、`render_pipeline_answer`。输出遵循 `TOOL_CHAIN_OUTPUT_SCHEMA`：`schema_version="tool-chain/v1"` + `selection_status` + `intent` + `agent_input`。stdout 只输出 JSON-RPC，日志全走 stderr（有测试锁定）。

### 7.2 HTTP（`app.py`）

`POST /api/ask {"query": "...", "top_k": 5}`；`GET /api/health` 返回 LLM 配置状态 + Neo4j 只读连通性。默认 `127.0.0.1:8000`。

### 7.3 Python API

```python
from workflow_composer import WorkflowComposer
result = WorkflowComposer().plan(nl_text, top_k=5, force_custom=False)
# 或模块级：compose_workflow_request(nl_text) / list_workflow_methods()
from pipeline_router import route_pipeline_request, assess_feasibility, render_pipeline_answer
```

### 7.4 结果关键字段

- `workflow_mode` / `selection_status`：`ready`（链+数据齐）、`missing_assets`（链定但缺用户样本数据）、`draft`（custom 草案校验通过，待执行端物化）、`no_match`、`information`（capability）、`requires_review`（兼容旧调用端）；
- `orchestration_status`：`ready`/`missing_data`/`draft`/`no_match`/`information`；
- `workflow_plan.execution_status`（custom）：`draft_requires_pipeline_materialization` 或 `blocked_by_incomplete_method_decomposition`；
- `agent_input`：执行端契约：`execution_kind`（`tool_chain`/`information`）、`assets`（含 `path_verified`）、`tool_chain`（每步 `asset_id` 或 `from` 绑定）、`feasibility`、`extensions.quality_gates`；
- `quality_gate`：来自 `docs/bio_pipelines_bug_report.md` 的静态审查，critical 级也**不阻断** `orchestration_status`（有意设计，见 `test_execution_quality_risk_does_not_block_orchestration_status`）；
- `llm_metadata` / `planner_metadata`：LLM 调用次数、token、模型。LLM 降级默认静默（`LLM_REQUIRED=0`），只能从这里发现。

## 8. 环境变量（`runtime_config.py`，`.env.local` 不覆盖进程环境）

| 变量 | 默认 | 说明 |
|---|---|---|
| `FORCE_RULE` | `0` | `1` 时完全不调 LLM，走规则兜底（custom 必然失败关闭） |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | — / deepseek 端点 / `deepseek-v4-pro` | OpenAI 兼容接口 |
| `LLM_REQUIRED` | `0` | `1` 时 LLM 不可用直接报错而不是静默降级 |
| `LLM_TIMEOUT` / `LLM_THINKING` / `LLM_REASONING_EFFORT` / `LLM_MAX_TOKENS` | 60 / enabled / high / 8000 | LLM 调用参数 |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | `bolt://127.0.0.1:7687` / neo4j / — / neo4j | 运行时真源 |
| `NEO4J_CONNECT_TIMEOUT` / `NEO4J_QUERY_TIMEOUT` / `NEO4J_HEALTH_CACHE_TTL` | 2 / 2 / 30 | 连接参数 |

## 9. 测试与日常命令

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-neo4j.txt -r requirements-llm.txt
.venv/bin/python -m unittest discover -s tests          # 63 个用例；需 Neo4j 在线（目录真源）
.venv/bin/python scripts/python/validate_csv.py --project-root .   # 改 CSV 后必跑
.venv/bin/python scripts/python/sync_neo4j_tool_catalog.py --apply # 同步工具目录+NEXT 边到 Neo4j
```

- `tests/test_workflow_composer.py`：主体。`setUp` 强制 `FORCE_RULE=1`；测 LLM 路径的用例用 `patch("workflow_composer._lazy_call_llm", ...)` mock 两阶段返回，或 `patch.dict(os.environ, {"FORCE_RULE": "0"})`。
- `tests/test_runtime_integrations.py`：3 个真实集成用例默认跳过，需 `RUN_REAL_INTEGRATION=1` + 有效凭证，会真实调 LLM/Neo4j。
- bench：`run_bench_deepseek.py`、`run_bench_full.py`；`scripts/python/run_live_regression.py` 做真实回归。

## 10. 已知边界（AI 读者必须知道）

**2026-07-23 已修复**（对应回归测试在 `test_workflow_composer.py` 末尾）：
1. 已知组合规则不再抹掉 LLM 的覆盖评估；LLM 无 ID 时不再用 router 低置信兜底充数；
2. custom 链非首步强制 `from`/`depends_on` 连通；
3. count/TPM 子类型贯穿 `_role_of_file`→feasibility→combinations→资产绑定，禁止交叉降级；
4. R1/R2 同源配对；
5. capability 数据过滤按语境分输入/输出侧（"从 FASTQ 得到表达矩阵"不再返回空）；
6. NEXT 边补全 7 条（fastp→bwa/star/multiqc、fastqc/samtools/gatk/star→multiqc），已同步 Neo4j（共 21 条）。

**仍未修（不要去"顺手修"，各有归属）**：
- `cypher/query_templates/` 与现行图 schema 全面脱节（`Format{name}` vs `Format{format}`、`NEXT_TOOL` vs `NEXT` 等），`find_workflow_end_tools.cypher` 条件写反。运行时不引用；要么整体对齐要么标注废弃；
- `diff_expr_kegg` 实际做 Reactome 富集（命名归属同事的目录数据）；
- 多 pipeline 串联时第二个 pipeline 的数据资产不参与匹配（`pipeline_router.py:876` 的 `matched[:1]`）；standard 串联的 artifact 衔接不查 `ARTIFACT_COMPATIBILITY`；
- `intent.py:108-115` JSON 非贪婪回退可能取到内层碎片；`pipeline_router.py:24-31` 吞 import 异常；LLM 静默降级（第 7.4 节）；
- capability 的 io_scope、质量 gate 不阻断 ready 是有意设计，改动前先看对应测试。

**给 AI 的硬性规则**：
- 不要为绕过 `blocked_by_incomplete_method_decomposition` 而硬编码任何 pipeline 的内部步骤——拆解是同事进行中的工作，目录以 Neo4j 为准；
- 不要绕过 `_validate_custom_steps` 的任何校验去"帮用户通过"；校验失败 + 如实 reason 是设计目标（fail closed）；
- 改 `data/csv/` 后必须跑 `validate_csv.py`；改 NEXT 边后必须由人确认再跑 `sync_neo4j_tool_catalog.py --apply`；
- `path_verified` 为 false 的资产路径指向执行端机器（`/hpcdisk1/...`、`/mnt/...`），在本机不存在是正常的，不要"修复"它。
