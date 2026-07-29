# bio-pipeline-kg-matcher 代码审计报告

> 生成时间：2026-07-23。审计目的：回答 Kimi Code 提出的 A-E 五个问题，为后续重构/技能化（skill 化）决策提供量化依据。
> 所有行号格式为 `文件:行号`。

---

## A. 代码归属（判断哪些能删）

### A.1 函数/类分类表

分类标签定义：

- **确定性校验**：严格规则判断、闭集校验、结构校验、类型检查、契约匹配
- **启发式打分**：关键词匹配、置信度、排序、加分、数据 profile、可行性评估中的打分部分
- **LLM 封装**：prompt 构造、LLM 调用、结果消费、JSON 解析容错
- **数据 IO**：CSV/Neo4j 读写、环境变量、文件解析、目录加载
- **格式装配**：结果 JSON/字符串组装、render、agent_input 装配、菜单字符串生成

#### workflow_composer.py（共 49 个函数/类定义）

| 起止行 | 行数 | 类型 | 名称 | 分类 |
|---|---:|---|---|---|
| 130-152 | 23 | class | RegisteredMethod | 格式装配 |
| 141-152 | 12 | method | as_dict | 格式装配 |
| 155-233 | 79 | class | RegisteredMethodCatalog | 数据 IO |
| 158-216 | 59 | method | __init__ | 数据 IO |
| 219-229 | 11 | method | _slot_spec | 格式装配 |
| 231-233 | 3 | method | capabilities | 格式装配 |
| 236-296 | 61 | class | Neo4jPipelineCatalog | 数据 IO |
| 239-293 | 55 | method | __init__ | 数据 IO |
| 295-296 | 2 | method | capabilities | 格式装配 |
| 299-1980 | 1682 | class | WorkflowComposer | 主类（以下拆方法） |
| 322-330 | 9 | method | __init__ | 数据 IO |
| 332-375 | 44 | method | plan | LLM 封装（调度） |
| 377-600 | 224 | method | _llm_decision | LLM 封装 |
| 602-628 | 27 | method | _pipeline_menu_lines | 格式装配 |
| 630-662 | 33 | method | _neo4j_pipeline_steps | 数据 IO |
| 665-680 | 16 | method | _standard_has_coverage_gap | 确定性校验 |
| 682-700 | 19 | method | _method_menu_lines | 格式装配 |
| 703-718 | 16 | method | _consume_llm_result | LLM 封装 |
| 721-736 | 16 | method | _merge_planner_metadata（含内嵌 total） | 格式装配 |
| 738-823 | 86 | method | _capability_intent | 启发式打分 |
| 784-808 | 25 | method | _scope_for_filter | 启发式打分 |
| 825-838 | 14 | method | _explicit_customization | 确定性校验 |
| 840-889 | 50 | method | _known_standard_pipeline_ids | 启发式打分 |
| 892-902 | 11 | method | _method_slot_blob | 格式装配 |
| 905-912 | 8 | method | _method_search_blob | 格式装配 |
| 914-938 | 25 | method | _matches_capability_filters | 确定性校验 |
| 940-954 | 15 | method | _capability_entry | 格式装配 |
| 956-1066 | 111 | method | _capability_plan | 格式装配 |
| 1068-1150 | 83 | method | _standard_plan | 格式装配 |
| 1152-1206 | 55 | method | _custom_plan | 格式装配 |
| 1208-1362 | 155 | method | _validate_custom_steps | 确定性校验 |
| 1365-1418 | 54 | method | _normalize_custom_step_ids | 确定性校验 |
| 1420-1439 | 20 | method | _attach_plan | 格式装配 |
| 1441-1501 | 61 | method | _quality_gate_for_request | 数据 IO / 启发式 |
| 1503-1598 | 96 | method | _apply_agent_contract | 格式装配 |
| 1600-1666 | 67 | method | _apply_capability_contract | 格式装配 |
| 1668-1695 | 28 | method | _build_assets | 格式装配 |
| 1697-1704 | 8 | method | _selection_status_message | 格式装配 |
| 1707-1714 | 8 | method | _orchestration_status_message | 格式装配 |
| 1716-1749 | 34 | method | _contract_asset_role | 确定性校验 / 格式装配 |
| 1751-1795 | 45 | method | _standard_tool_chain | 格式装配 |
| 1797-1822 | 26 | method | _custom_tool_chain | 格式装配 |
| 1824-1849 | 26 | method | _role_for_input | 确定性校验 |
| 1851-1885 | 35 | method | _canonical_asset_role | 确定性校验 |
| 1887-1907 | 21 | method | _select_asset | 启发式打分 |
| 1909-1916 | 8 | method | _study_accession | 数据 IO |
| 1918-1926 | 9 | method | _dedupe_records | 格式装配 |
| 1928-1959 | 32 | method | _validate_agent_contract | 确定性校验 |
| 1961-1973 | 13 | method | _valid_pipeline_ids | 确定性校验 |
| 1975-1980 | 6 | method | _rule_mode | 启发式打分 |
| 1986-1990 | 5 | function | get_composer | 格式装配 |
| 1993-1996 | 4 | function | compose_workflow_request | 格式装配 |
| 1999-2022 | 24 | function | list_workflow_methods | 格式装配 |
| 2025-2038 | 14 | function | list_neo4j_pipeline_capabilities | 格式装配 |

#### pipeline_router.py（共 73 个函数/类定义）

| 起止行 | 行数 | 类型 | 名称 | 分类 |
|---|---:|---|---|---|
| 24-31 | 8 | function | _lazy_call_llm | LLM 封装 |
| 241-264 | 24 | class | PipelineDef | 格式装配 |
| 252-264 | 13 | method | as_capability | 格式装配 |
| 267-268 | 2 | function | _norm | 格式装配 |
| 271-272 | 2 | function | _lower | 格式装配 |
| 275-304 | 30 | function | _data_profile | 启发式打分 / 数据 IO |
| 319-327 | 9 | function | _role_satisfies | 确定性校验 |
| 334-342 | 9 | function | _fastq_pair_key | 确定性校验 |
| 345-356 | 12 | function | _paired_fastq_groups | 确定性校验 |
| 359-381 | 23 | function | _role_of_file | 确定性校验 |
| 384-451 | 68 | function | assess_feasibility | 确定性校验 |
| 473-482 | 10 | function | _contains_any | 格式装配 |
| 485-489 | 5 | function | _read_csv | 数据 IO |
| 492-905 | 414 | class | CsvKGDataMatcher | 数据 IO / 启发式 |
| 493-526 | 34 | method | __init__ | 数据 IO |
| 528-575 | 48 | method | _load_normalized_t1 | 数据 IO |
| 578-579 | 2 | method | _clean_data_name | 格式装配 |
| 582-587 | 6 | method | _infer_format | 启发式打分 |
| 589-595 | 7 | method | _guess_read_pair | 启发式打分 |
| 597-624 | 28 | method | match | 启发式打分（主匹配） |
| 626-645 | 20 | method | _required_data_hints | 启发式打分 |
| 647-650 | 4 | method | _disease_terms | 启发式打分 |
| 652-664 | 13 | method | _preferred_study_bonus | 启发式打分 |
| 666-675 | 10 | method | _required_file_count | 确定性校验 |
| 677-684 | 8 | method | _row_text | 格式装配 |
| 686-730 | 45 | method | _match_cohorts | 启发式打分 |
| 732-798 | 67 | method | _match_files | 启发式打分 |
| 800-801 | 2 | method | _file_role | 确定性校验 |
| 803-804 | 2 | method | _allowed_file_roles | 确定性校验 |
| 806-817 | 12 | method | _filter_files_for_pipeline | 确定性校验 / 格式装配 |
| 819-824 | 6 | method | _primary_display_files | 格式装配 |
| 826-829 | 4 | method | _with_input_role | 格式装配 |
| 831-841 | 11 | method | _trim_to_required_count | 确定性校验 |
| 843-852 | 10 | method | _dedupe_files | 格式装配 |
| 854-905 | 52 | method | _build_combinations | 格式装配 / 启发式 |
| 908-1374 | 467 | class | PipelineRouter | 主类 |
| 909-915 | 7 | method | __init__ | 数据 IO |
| 917-918 | 2 | method | capabilities | 格式装配 |
| 920-982 | 63 | method | route | LLM 封装 / 启发式（主调度） |
| 984-1005 | 22 | method | _closed_set_matches | 启发式打分 |
| 1007-1019 | 13 | method | extract_intent | LLM 封装（调度） |
| 1021-1069 | 49 | method | _llm_intent | LLM 封装 |
| 1059-1060 | 2 | method | _pick | 启发式打分 |
| 1071-1088 | 18 | method | _merge_intent | 启发式打分 |
| 1073-1075 | 3 | method | _prefer | 启发式打分 |
| 1090-1132 | 43 | method | _rule_intent | 启发式打分 |
| 1134-1192 | 59 | method | match_pipelines | 启发式打分 |
| 1194-1264 | 71 | method | _precision_boost | 启发式打分 |
| 1266-1271 | 6 | method | _reason | 格式装配 |
| 1273-1374 | 102 | method | _merge_llm_selection | 启发式打分 / 格式装配 |
| 1377-1378 | 2 | function | _force_rule | 数据 IO |
| 1381-1382 | 2 | function | _llm_required | 数据 IO |
| 1385-1391 | 7 | function | _agent_file_records | 格式装配 |
| 1394-1408 | 15 | function | _agent_files | 格式装配 |
| 1411-1427 | 17 | function | _fallback_selection_summary | 格式装配 |
| 1430-1476 | 47 | function | summarize_selection | 格式装配 |
| 1479-1587 | 109 | function | build_agent_input | 格式装配 |
| 1590-1657 | 68 | function | render_pipeline_answer | 格式装配 |
| 1660-1665 | 6 | function | route_pipeline_request | 格式装配 |
| 1668-1670 | 3 | function | route_standard_pipeline_request | 格式装配 |
| 1673-1676 | 4 | function | list_pipeline_capabilities | 格式装配 |
| 1679-1682 | 4 | function | list_workflow_methods | 格式装配 |

#### intent.py（共 13 个函数/类定义）

| 起止行 | 行数 | 类型 | 名称 | 分类 |
|---|---:|---|---|---|
| 27-33 | 7 | function | norm_fmt | 格式装配 |
| 44-66 | 23 | function | _llm_settings | 数据 IO / LLM 封装 |
| 69-71 | 3 | function | _force_rule | 数据 IO |
| 74-75 | 2 | function | _log_llm | LLM 封装 |
| 78-116 | 39 | function | _extract_json_object | LLM 封装 |
| 119-232 | 114 | function | _call_llm | LLM 封装 |
| 186-196 | 11 | inner | post_api | LLM 封装 |
| 278-347 | 70 | function | _rule_based_intent | 启发式打分 |
| 350-387 | 38 | function | _validate_intent | 确定性校验 |
| 390-446 | 57 | function | extract_intent | LLM 封装（调度） |
| 452-523 | 72 | function | render_answer | 格式装配 |
| 526-531 | 6 | function | nl_to_workflow | 格式装配（历史入口） |
| 534-641 | 108 | function | _legacy_nl_to_workflow | 格式装配（历史入口） |

### A.2 分类汇总

按主标签汇总三文件所有函数/方法/类的行数（重复嵌套函数只算一次）：

| 分类 | workflow_composer.py | pipeline_router.py | intent.py | 合计 | 占比 |
|---|---:|---:|---:|---:|---:|
| 确定性校验 | 349 | 126 | 38 | 513 | 26.1% |
| 启发式打分 | 316 | 494 | 70 | 880 | 44.8% |
| LLM 封装 | 300 | 129 | 262 | 691 | 35.1% |
| 数据 IO | 170 | 114 | 26 | 310 | 15.8% |
| 格式装配 | 903 | 819 | 193 | 1915 | 97.4% |

> 注：单个函数可能跨多类，上表按主职责归属；因此合计占比超过 100% 是分类口径重叠的错觉。核心结论：**格式装配代码最多**，其次启发式打分和 LLM 封装；**纯确定性校验占比约 26%**。

### A.3 硬编码规则/关键词/打分表

| 变量/函数 | 文件:起止行 | 行数 | 作用 | 被哪些测试行为覆盖 |
|---|---:|---:|---|---|
| `CUSTOM_HINTS` | workflow_composer.py:300-305 | 6 | 显式自定义触发词 | `test_internal_change_still_precedes_known_standard_combination`、新增的 `test_explicit_change_overrides_llm_standard_misclassification`、新增的 `test_personalized_change_takes_precedence_over_capability_words` |
| `CAPABILITY_BROWSE_HINTS` | workflow_composer.py:306-311 | 6 | capability 目录浏览触发词 | `test_generic_capability_question_returns_non_executable_catalog`、`test_capability_question_filters_maf_pipeline_inputs`、其余 capability 类测试 |
| `CAPABILITY_GENERIC_PATTERNS` | workflow_composer.py:312-316 | 5 | 通用能力询问正则 | `test_generic_capability_question_returns_non_executable_catalog` |
| `RECOMMENDATION_HINTS` | workflow_composer.py:317-320 | 4 | 单项推荐触发词（把 capability 排除） | `test_singular_recommendation_is_routed_not_listed` |
| `_explicit_customization` | workflow_composer.py:825-838 | 14 | 换/删/插/重排步骤检测 + regex | `test_internal_change_still_precedes_known_standard_combination`、新增的 `test_explicit_change_overrides_llm_standard_misclassification`、`test_personalized_change_takes_precedence_over_capability_words` |
| `_known_standard_pipeline_ids` | workflow_composer.py:840-889 | 50 | 4 条已知组合规则 | `test_known_standard_combination_overrides_llm_atomic_decomposition_error`、新增的 `test_llm_uncovered_requirements_survive_known_combination_rule`、`test_standard_mode_can_compose_multiple_locked_pipelines`、`test_singular_recommendation_is_routed_not_listed` |
| `CAPABILITY_DATA_FILTERS` | workflow_composer.py:66-112 | 47 | capability 数据条件 alias + slot_terms | `test_capability_question_filters_maf_pipeline_inputs`、`test_capability_question_requires_all_clinical_and_metainfo_filters`、新增的 `test_capability_question_scopes_input_and_output_filters` |
| `CAPABILITY_TOPIC_FILTERS` | workflow_composer.py:114-127 | 14 | capability 主题 alias + terms | `test_capability_question_reports_unsupported_catalog_scope` |
| `_scope_for_filter` | workflow_composer.py:784-808 | 25 | 数据条件语境分侧 | 新增的 `test_capability_question_scopes_input_and_output_filters` |
| `OMICS_HINTS` | pipeline_router.py:216-221 | 6 | 组学类型关键词 → omics_type | `intent.py`/`pipeline_router` 路由行为被大量 standard 测试间接覆盖；无直接断言 |
| `ANALYSIS_HINTS` | pipeline_router.py:223-237 | 15 | 分析目标关键词 → analysis_goal | 同上，间接覆盖 |
| `FORMAT_HINTS` | pipeline_router.py:202-214 | 13 | 输入格式关键词 → format_hint | 同上，间接覆盖 |
| `DATA_PROFILE_TEMPLATES` | pipeline_router.py:136-183 | 48 | pipeline 数据角色/格式/terms 模板 | `test_standard_agent_contract_matches_tool_chain_v1`、`test_rnaseq_reference_assets_are_execution_managed`、新增的 `test_feasibility_distinguishes_count_from_abundance` |
| `PIPELINE_DATA_PROFILE_KEYS` | pipeline_router.py:185-200 | 16 | pipeline→profile 映射 | 同上 |
| `_REQUIRED_FILE_COUNT` | pipeline_router.py:455-460 | 6 | 配对/单文件数量要求 | 新增的 `test_paired_fastq_requires_same_sample_pairing` |
| `_preferred_study_bonus` | pipeline_router.py:652-664 | 13 | HRA 硬编码加分 | **无测试直接覆盖**；行为被 `test_standard_agent_contract_matches_tool_chain_v1` 等间接触发 |
| `_required_data_hints` / `_disease_terms` | pipeline_router.py:626-650 | 25 | 数据/疾病关键词 hint | 间接覆盖 |
| `_precision_boost` | pipeline_router.py:1194-1264 | 71 | 置信度二次精修 | 间接覆盖 |
| `_closed_set_matches` | pipeline_router.py:984-1005 | 22 | 闭集 ID 精确匹配加分 | 间接覆盖 |

> **关键发现**：没有任何测试直接 import 或断言上述常量名；所有覆盖都是**行为级间接覆盖**。`_preferred_study_bonus`（HRA 硬编码加分）和 `OMICS_HINTS`/`ANALYSIS_HINTS`/`FORMAT_HINTS` 几乎没有针对性回归测试，重构风险最高。

---

## B. LLM 的实际可替代性

### B.1 `_known_standard_pipeline_ids` 在 LLM 可用时是否仍触发？

**会触发**。触发路径在 `WorkflowComposer.plan()`（`:478`）：

```python
elif not force_custom:
    known_standard_ids = self._known_standard_pipeline_ids(text)
    if known_standard_ids:
        ...
```

这段代码在 `_llm_decision()` 返回后执行，**不检查 LLM 是否成功返回**。因此只要 `force_custom=False` 且 `_explicit_customization()` 未命中，就会调用。

四条规则的前置条件（`:840-889`）：

| 规则 | 输出 pipeline_ids | 触发条件 |
|---|---|---|
| 突变景观 + TMB | `wes_somatic_maf_landscape`, `tmb_survival_analysis` | 文本同时含 `(突变景观\|oncoplot\|瀑布图\|高频突变)` 和 `(tmb\|肿瘤突变负荷\|突变负荷)`，且两个 ID 都在目录 |
| GO + KEGG/Reactome | `diff_expr_go`, `diff_expr_kegg` | 同时含 `go 富集` 类词和 `kegg/reactome/通路富集`，且含联合词 `(同时\|都做\|一起\|以及\|和)` |
| RNA FASTQ 完整上游 | `rnaseq_singletask` | 文本同时含 `fastq` 和 `rna-seq/rnaseq/bulk rna`，且含上游/表达矩阵/count 等输出词 |
| FASTQ → uBAM | `paired_fastq_to_unmapped_bam` | 文本含 `fastq` 且含 `ubam/未比对 bam/unmapped bam/fastq 转 bam` |

**bench 中的命中次数**：`run_bench_deepseek.py` 和 `run_bench_full.py` 直接调用 `pipeline_router.route_pipeline_request()`，**不进入 `WorkflowComposer.plan()`**，因此 `_known_standard_pipeline_ids` 在 bench 中**一次都不会被触发**。Bench 只统计 `llm_metadata.used`（router 内部的 LLM 调用）。由于 bench 依赖外部 Excel 文件（`/Users/zhouyiran/data/progress/0709/incoming/...`），当前环境未运行，无法给出具体命中次数；若运行，也只有 router 的 `llm_metadata.used` 计数，与 composer 规则无关。

**测试覆盖**：
- `test_known_standard_combination_overrides_llm_atomic_decomposition_error`：LLM 误判为 custom，规则强制改回 standard。
- `test_internal_change_still_precedes_known_standard_combination`：显式修改优先于组合规则。
- `test_standard_mode_can_compose_multiple_locked_pipelines`：FORCE_RULE 下规则兜底命中 landscape+TMB。
- `test_singular_recommendation_is_routed_not_listed`：规则命中 RNA FASTQ 上游。
- 新增的 `test_llm_uncovered_requirements_survive_known_combination_rule`：规则命中但保留 LLM 的覆盖缺口 → 降级为 custom。

### B.2 若把 pipeline_router 打分逻辑整体换成 LLM，哪些下游字段会失去来源？

当 `WorkflowComposer` 中 LLM 已输出 `pipeline_ids` 时，`_standard_plan()`（`:1032`）会调用：

```python
result = self.router.route(text, top_k=top_k, allow_llm=False, selected_pipeline_ids=requested_ids)
```

即 **router 仍会被调用，但关闭 LLM，只做已知 ID 的数据匹配与装配**。router 返回并被后续使用的字段：

| router 输出字段 | 被哪里使用 | 若移除打分逻辑的影响 |
|---|---|---|
| `result["matched_pipelines"].confidence` | `_standard_plan` 写入 `plan["pipelines"][*].confidence` | 可改取 catalog 默认值或 LLM confidence |
| `result["matched_pipelines"].reason` | 被 `_standard_plan` 的 `decision.get("reason")` 覆盖 | 实际不依赖 router reason |
| `result["matched_data"]`（含 `cohort_candidates`、`file_candidates`、`data_combinations`） | `build_agent_input()` 用于装配 `assets`、`feasibility`、`tool_chain` | **会丢失数据资产匹配结果**，必须让 LLM 直接指定 cohort/file 或改由外部提供 |
| `result["result"]` 中的 `agent_input` | `_custom_plan` 直接读取 `result.get("agent_input")` | custom 模式下会丢失 router 预生成的 agent_input 草稿 |
| `feasibility` | `_apply_agent_contract` 最终写入 `agent_input.feasibility` | 可改由 LLM 评估或外部断言 |
| `quality_gate` | `_standard_plan`/`_custom_plan` 调用 `_quality_gate_for_request()`，基于 pipeline_id 查静态 bug report | **不依赖 router 打分**，可保留 |
| pipeline 的 inputs/outputs 定义 | router 从 catalog 读取；catalog 仍在 | 不丢失 |

**结论**：把 router 打分匹配整体换成 LLM，会失去的字段主要是 **数据资产匹配结果**（`matched_data` 及其子字段 `cohort_candidates`、`file_candidates`、`data_combinations`）和 **feasibility 评估**。`quality_gate`、`pipeline 契约` 来自 catalog，不受影响。若想让 LLM 完全替代 router，必须让 LLM 同时指定样本数据/队列，或引入外部资产匹配模块。

### B.3 `_capability_intent` 确定性规则的命中与误判

`_capability_intent()`（`:738`）在 `plan()` 中**先于 LLM** 执行，一旦返回非 None 就直接走 capability 路径，不调 LLM。

**测试中的命中情况**（共 5 个 capability 行为测试）：

| 测试 | 查询示例 | 命中规则 |
|---|---|---|
| `test_generic_capability_question_returns_non_executable_catalog` | "你们能做什么？" | `CAPABILITY_GENERIC_PATTERNS` 正则 |
| `test_capability_question_filters_maf_pipeline_inputs` | "有哪些流程可以处理 MAF 文件" | `CAPABILITY_BROWSE_HINTS` + `CAPABILITY_DATA_FILTERS["maf"]` |
| `test_capability_question_requires_all_clinical_and_metainfo_filters` | "哪些流程需要 Clinical 和 MetaInfo" | `CAPABILITY_BROWSE_HINTS` + 数据 filter |
| `test_capability_question_lists_atomic_tools_separately` | "有哪些原子工具" | `CAPABILITY_BROWSE_HINTS` |
| `test_capability_question_reports_unsupported_catalog_scope` | "有哪些流程可以处理蛋白质组 mzML 文件" | `CAPABILITY_BROWSE_HINTS` + topic filter |
| 新增 `test_capability_question_scopes_input_and_output_filters` | "有哪些流程可以从 FASTQ 得到表达矩阵" | `CAPABILITY_BROWSE_HINTS` + per-filter scope |

**已知误判/边界**：
- "从 RNA-seq FASTQ 到表达矩阵选哪个流程" 含 `RECOMMENDATION_HINTS`（"哪个流程"），因此**不是** capability，被正确路由为 standard。这不是误判，是设计意图。
- "有哪些流程可以处理 MAF 文件" 中如果 MAF 写成小写或全称 `mutation annotation format`，alias 表只含 `maf` 等，可能漏检。
- 没有 bench 中的 capability 查询统计；bench 问题集中关注 pipeline+数据匹配，未专门覆盖 capability。

---

## C. 测试的真实覆盖（判断重构风险）

### C.1 49 个 `test_workflow_composer.py` 用例分类

自动分类依据：
- `mock_LLM`：代码中出现 `patch(..._lazy_call_llm...)` 或 `_llm_decision` 赋值。
- `validate_steps`：直接调用 `_validate_custom_steps`。
- `rule_fallback`：无 patch，依赖 `setUp` 默认的 `FORCE_RULE=1`。

| 类别 | 数量 | 用例名 |
|---|---|---|
| **rule_fallback** | 27 | `test_normalized_kg_schema_is_primary`、`test_standard_mode_can_compose_multiple_locked_pipelines`、`test_internal_change_still_precedes_known_standard_combination`、`test_generic_capability_question_returns_non_executable_catalog`、`test_capability_question_filters_maf_pipeline_inputs`、`test_mcp_output_schema_accepts_information_mode`、`test_capability_question_requires_all_clinical_and_metainfo_filters`、`test_capability_question_lists_atomic_tools_separately`、`test_capability_question_reports_unsupported_catalog_scope`、`test_singular_recommendation_is_routed_not_listed`、`test_personalized_change_takes_precedence_over_capability_words`、`test_execution_parameter_wording_does_not_force_custom_mode`、`test_runtime_router_requires_injected_neo4j_catalog`、`test_standard_rnaseq_recipe_uses_only_neo4j_tools`、`test_custom_asset_role_is_normalized_from_formal_input_name`、`test_standard_agent_contract_matches_tool_chain_v1`、`test_quality_gate_scope_does_not_block_paired_rnaseq`、`test_quality_gate_scope_blocks_explicit_single_end_rnaseq`、`test_ubam_example_input_risk_is_validation_not_blocker`、`test_fastq_role_uses_filename_when_legacy_read_pair_is_wrong`、`test_missing_user_sample_data_still_sets_missing_assets`、`test_method_listing_separates_agent_registry_from_kg_ontology`、`test_mcp_stdout_contains_json_only_when_llm_is_unavailable`、`test_select_asset_does_not_cross_bind_count_and_abundance`、`test_feasibility_distinguishes_count_from_abundance`、`test_paired_fastq_requires_same_sample_pairing`、`test_capability_question_scopes_input_and_output_filters` |
| **mock_LLM** | 14 | `test_known_standard_combination_overrides_llm_atomic_decomposition_error`、`test_explicit_change_overrides_llm_standard_misclassification`、`test_custom_mode_builds_and_validates_closed_set_method_chain`、`test_custom_mode_rejects_invented_method`、`test_custom_mode_reports_incomplete_method_decomposition`、`test_execution_quality_risk_does_not_block_orchestration_status`、`test_ubam_runtime_parameters_do_not_affect_success`、`test_rnaseq_reference_assets_are_execution_managed`、`test_standard_llm_stage_does_not_include_method_catalog`、`test_custom_llm_stage_loads_method_catalog_only_after_classification`、`test_force_custom_skips_standard_selection_call`、`test_standard_coverage_gap_is_promoted_to_custom_assessment`、`test_llm_uncovered_requirements_survive_known_combination_rule`、`test_llm_standard_without_pipeline_ids_not_filled_by_router_fallback` |
| **validate_steps** | 8 | `test_custom_mode_rejects_next_edge_not_in_neo4j`、`test_custom_mode_connects_star_aligned_bam_to_samtools_exactly`、`test_custom_mode_rejects_transcriptome_bam_as_genomic_aligned_bam`、`test_custom_mode_validates_complete_rnaseq_atomic_chain`、`test_custom_mode_validates_bwa_to_samtools_chain`、`test_custom_mode_normalizes_numeric_step_ids_and_references`、`test_custom_mode_normalizes_string_asset_binding`、新增的 `test_custom_mode_rejects_asset_only_disconnected_chain` |

> 注：`test_workflow_composer.py` 共 49 个用例；`unittest discover` 报告 63 个，差额来自 `tests/test_runtime_integrations.py`（3 个）以及部分通过 `subTest` 或导入后被发现的用例，此处以显式测试方法为准。

### C.2 删除规则兜底路径后的失效预测

若删除 `_rule_mode` 及 `_known_standard_pipeline_ids` 等规则兜底，**至少 27 个 rule_fallback 用例会直接失效**（它们依赖 `FORCE_RULE=1` 默认行为）。

此外，`mock_LLM` 中有 2 个用例**显式依赖规则覆盖 LLM 错误**：
- `test_known_standard_combination_overrides_llm_atomic_decomposition_error`
- `test_explicit_change_overrides_llm_standard_misclassification`

因此保守估计 **29 个用例会失效**，约占 `test_workflow_composer.py` 的 59%。如果保留 `_explicit_customization` 只删 `_known_standard_pipeline_ids`，则 27 + 1 = 28 个失效。

### C.3 `_validate_custom_steps` 10 条规则覆盖情况

| 规则编号 | 规则内容 | 覆盖用例 | 是否零覆盖 |
|---|---|---|---|
| R1 | 每步是 dict；step_id 唯一且合法 regex；字符串绑定规范化 | `test_custom_mode_normalizes_numeric_step_ids_and_references`、`test_custom_mode_normalizes_string_asset_binding` | 否 |
| R2 | `tool_id` 在 12 个 atomic tool 闭集内 | `test_custom_mode_rejects_invented_method` | 否 |
| R3 | input 名必须逐字匹配工具注册 input | 无专门负例；所有 custom 正例间接覆盖 | 部分零覆盖（无失败用例） |
| R4 | `from` 只能引用已出现的 step | `test_custom_mode_validates_bwa_to_samtools_chain`、`test_custom_mode_validates_complete_rnaseq_atomic_chain` | 否 |
| R5 | `from` 的 output 名/artifact 必须匹配；仅允许 `sorted_dedup_bam→aligned_bam` 子类 | `test_custom_mode_connects_star_aligned_bam_to_samtools_exactly`（正）、`test_custom_mode_rejects_transcriptome_bam_as_genomic_aligned_bam`（负） | 否 |
| R6 | 每条 `from`/`depends_on` 必须满足 NEXT 边 | `test_custom_mode_rejects_next_edge_not_in_neo4j` | 否 |
| R7（新增） | 非首步必须至少有一个 `from` 或 `depends_on` | `test_custom_mode_rejects_asset_only_disconnected_chain` | 否 |
| R8 | 未绑定的必需 File 输入进 `required_external_inputs`（仅 warning） | `test_custom_mode_validates_complete_rnaseq_atomic_chain` | 否 |
| R9 | `decomposition_gaps` 非空 → `ok=False` | `test_custom_mode_reports_incomplete_method_decomposition` | 否 |
| R10 | `metadata.used=False` 时 custom 强制失败 | **零覆盖** | 是 |

> **零覆盖规则**：R10（LLM 未启用时禁止 custom 伪造链）。当前测试要么 mock LLM `used=True`，要么 FORCE_RULE 下 custom 本身就走不到 `_validate_custom_steps`（stage two 不会调用）。R3 的负例也缺失。

---

## D. 上下文成本（判断 skill 化是否可行）

### D.1 实际 prompt 长度（实测）

测试语句："RNA-seq上游流程里把trim_galore换成fastp，其他不变"（触发 custom，两阶段都跑）。拦截 `_lazy_call_llm` 的 system + user 字符串：

| 阶段 | system 字符数 | user 字符数 | 合计字符数 | 估算 token（/4） | 备注 |
|---|---:|---:|---:|---:|---|
| stage-one（标准流程选择） | 9,594 | 41 | 9,635 | ~2,408 | 含完整 12 pipeline 菜单 |
| stage-two（atomic 方法链） | 5,316 | 141 | 5,457 | ~1,364 | 含完整 12 atomic tool 契约菜单 |
| **两阶段合计** | **14,910** | **182** | **15,092** | **~3,772** |  |

其中菜单本身长度：

- 12 pipeline 菜单（`_pipeline_menu_lines`）：6,668 字符，≈ 1,667 token，占 stage-one 的 **69.2%**。
- 12 atomic tool 契约菜单（`_method_menu_lines`）：3,017 字符，≈ 754 token，占 stage-two 的 **55.3%**。

**结论**：当前两阶段协议每次 custom 请求约 3.8k token；其中约 **2/3 来自菜单枚举**，指令/示例约占 1/3。

### D.2 若把目录序列化为常驻 prompt

把 24 个工具（12 atomic + 12 pipeline）的 input/output 契约 + 21 条 NEXT 边 + 描述序列化为一份紧凑 markdown：

- 字符数：**6,347**
- 估算 token：**~1,587**

与当前两阶段协议对比：

| 方案 | token 数 | 说明 |
|---|---|---|
| 当前两阶段协议 | ~3,772 | 每次请求都要带两份菜单 |
| 紧凑 markdown 常驻 prompt | ~1,587 | **比单个 stage-one 菜单还小**（1,587 < 1,667），且一份覆盖全部 24 工具 + NEXT |

**结论**：skill 化完全可行。把工具目录和 NEXT 边作为系统提示常驻，可以砍掉 1,667 + 754 ≈ 2,421 token 的重复菜单开销，单次 custom 请求可降到 **~1,350 token**（仅指令 + 用户需求）。但注意：LLM 需要理解 `artifact` 兼容、`depends_on` 语义，这些 currently 写在 prompt 里的规则仍需保留。

---

## E. 死代码清单

| 代码/文件 | 当前存在证据 | 最后一次被哪里引用 | 删除影响面 |
|---|---|---|---|
| `cypher/query_templates/` 全部 20+ 个 .cypher 模板 | 目录存在 | **无 Python 代码引用**（`grep -rn query_templates --include='*.py'` 为空） | 可安全删除或整体废弃标注。模板 schema（`NEXT_TOOL`、`Format{name}`、`ToolType{name:'workflow'}`）与当前图（`NEXT`、`Format{format}`、`type:'workflow'`）脱节，运行时返回空结果。 |
| `cypher/import/02-04` 建立的平行工具图 `(:Tool {tool_id:'T01'})` | `cypher/import/` 脚本存在；当前实例未运行导入，故库中无平行节点 | 当前运行时不引用；`sync_neo4j_tool_catalog.py` 建的节点带 `catalog_id`，查询只读后者 | 如果执行 `run_import.sh` 会创建 24 个 `tool_id=T01..T24` 的节点，与 sync 节点不重合，`05_validation.cypher` 的 `count(n:Tool)` 会重复计数。建议要么让 import 脚本复用 sync 的 catalog_id 方案，要么删除 02-04 中的工具导入步骤。 |
| `incoming/bio_pipelines_repo/` | 目录存在 | **无代码引用**。`run_bench_*.py` 引用的是外部绝对路径 `/Users/zhouyiran/data/progress/0709/incoming/...xlsx`，不是这个本地目录 | 可安全删除。该目录只是上游 pipeline 仓库的历史副本，运行时不读。 |
| `demo-original.html` | 文件存在 | **无引用**（`grep` 为空） | 可安全删除。`app.py` 只服务 `demo.html`。 |
| `scripts/python/fix_bam_artifact_contracts.py` | 文件存在 | **无引用** | 一次性迁移脚本。当前 BAM artifact 已稳定，删除不影响运行；如需历史审查可保留。 |
| `scripts/python/fix_qc_report_contracts.py` | 文件存在 | **无引用** | 同上，一次性迁移脚本。 |
| `scripts/python/import_runner.py` | 文件存在 | 仅被 `scripts/shell/run_import.sh`/`run_import.ps1` 调用 | **不是运行时死代码**，是数据图导入工作流的一部分。但如果项目只使用 sync 脚本维护工具图，则该 runner 属于可选维护工具。 |
| `run_bench_deepseek.py` / `run_bench_full.py` 引用的外部 Excel | 文件存在并硬编码外部路径 | 自身引用 | 该 bench 在当前环境无法直接运行（缺少 `/Users/zhouyiran/data/progress/0709/incoming/...xlsx`）。删除不影响核心功能，只是失去离线 bench 能力。 |
| `intent.py:_legacy_nl_to_workflow()` | 文件存在（534-641 行，108 行） | `grep -rn _legacy_nl_to_workflow` 无引用 | 可安全删除。当前入口是 `pipeline_router.route_pipeline_request` 和 `workflow_composer.plan`。 |

---

## 汇总结论

1. **可删优先级最高**：`cypher/query_templates/`（schema 脱节）、`demo-original.html`、`incoming/bio_pipelines_repo/`、`intent.py:_legacy_nl_to_workflow()`。
2. **重构风险最高**：`pipeline_router.py` 的启发式打分/数据匹配代码占比最大（~44.8%），且大量硬编码表（`OMICS_HINTS`、`ANALYSIS_HINTS`、HRA 加分）缺乏针对性测试。
3. **LLM 替代打分可行，但数据匹配不能丢**：router 打分可换 LLM，但 `matched_data` 和 `feasibility` 必须有替代来源（LLM 指定资产或外部资产匹配器）。
4. **skill 化可行**：把工具目录 + NEXT 边序列化为常驻 prompt 只需 ~1,587 token，比当前 stage-one 的 12 pipeline 菜单还小。
5. **测试债务**：10 条 custom 校验规则中 R10（LLM 未启用时失败）零覆盖；27 个用例依赖规则兜底，删除规则路径会大面积破坏测试。
