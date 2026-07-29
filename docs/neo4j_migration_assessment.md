# 数据匹配从 CSV 迁移到 Neo4j 的评估

调查日期：2026-07-24。本文仅基于仓库文件和在线 Neo4j 的只读查询；未执行导入、`--apply`、建索引或任何写 Cypher。

## 摘要

技术上可行，但现在不能直接切换。在线图尚不是“最新最全”：当前 CSV 的 13,772 条 T1 虽然都能按 `(study, run, R1/R2)` 在图中找到，但 9,116 条缺 `strategy`，文件主键有历史后缀；T2 的当前 86 条都在图中，同时残留 13 条旧记录；`run -> sample` 少 497 条，`sample -> individual` 少 760 条；HRA000122 的 696 个 WES FASTQ 完全不在图中。更关键的是，仓库导入脚本使用大写标签和 camelCase 属性，而在线图使用小写标签和 snake_case 属性，当前脚本不是在线图的可复现来源。

性能不是迁移的主要收益。现有 CSV `match()` 中位数为 236.112 ms；复用连接后的三类 Neo4j 查询中位数分别为 19.642 ms、7.354 ms、31.110 ms。相对于 custom 请求 30-60 s 的端到端耗时，匹配只占约 0.39%-0.79%。迁移价值主要是统一运行时真源、可审计性和图拓扑查询，而不是用户可感知的提速。

建议先修复数据图的可复现导入和双读校验，不要先重写 matcher，更不要把现有 `RUN_CLEAR=true` 路径用于交付库。

## 阶段一：CSV 与 Neo4j 全量清点

### 1.1 CSV 侧

`data/csv/` 实际有 34 个文件，其中 33 个以 `.csv` 结尾，另有 `T2.1csv`。根目录的 `project.csv`、`sample.csv`、`study.csv` 分别与 `entities/` 对应文件逐字节相同。

#### 根目录和实体表

| 路径 | 数据行 | 完整列名 | 每行含义 |
|---|---:|---|---|
| `T11.csv` | 15,484 | `study_accession, sample_accession, run_accession, data_type, Read Pair, files, format, file_path, file_description, Experiment, Platform, data_level, pipeline-id, parameter` | 一个物理文件及其 study/sample/run、路径和旧版流程元数据 |
| `T2.1csv` | 99 | `study_accession, files, file_type, format, size, data_level, size_bytes, file_path, stragy` | 旧版处理后文件/目录；`stragy` 拼写错误，无 `t2_id` |
| `entities/T1.csv` | 13,772 | `studyAccession, individualAccession, individualName, sampleAccession, sampleDescription, sampleName, gender, runAccession, dataName, experimentAccession, platform, strategy` | 规范化的一条原始/一级数据文件实体 |
| `entities/T2.csv` | 86 | `study_accession, t2_id, files, file_type, format, size, data_level, size_bytes, file_path, strategy` | 规范化的一条处理后文件或目录实体 |
| `entities/individual.csv` | 3,494 | `project_accession, individual_accession, study_accession, individual_id, project_name, tumor_type, tumor_subtype, primary_tumor_site, primary_tumor_location, gender, country, race, age, family_history, smoking, tumor_grade, tumor_stage, pathologic_t, pathologic_n, pathologic_m, clinical_t, clinical_n, clinical_m, residual_tumor, lymphatic_invasion, vessel_invasion, nerve_invasion, treatment_intent_type, neoadjuvant_treatment_type, neoadjuvant_treatment_agents, tmb, msi_score, sample_type, specimen_types, overall_survival_status, overall_survival_days, overall_survival_time, progression_free_survival_status, disease_free_survival_time, gleason_score, neoadjuvant_treatment_outcome_pathological_response, adjuvant_treatment_agents, adjuvant_treatment_outcome_response, tmb_status, fraction_genome_altered, msi_status, dfs_status, overall_vital_status` | 一个个体及临床/生存属性 |
| `entities/project.csv` | 11 | `project_accession, project_name, project_code, relevance, project_description, data_types, organisms, sample_scope, individual_count, country, tumor_type, study_accession, type, health_conditions, organization, submission_date, release_date, information_source` | 一个项目 |
| `entities/sample.csv` | 6,918 | `study_accession, sample_accession, sample_name, sample_description, individual_accession, individual_name, biospecimen_anatomic_site, sample_type, specimen_types, strategy, tissue_type` | 一个生物样本 |
| `entities/study.csv` | 14 | `study_accession, title, study_description, study_type, tumor_type, individual_count, sample_count, information_source` | 一个研究/队列 |
| `entities/tool.csv` | 23 | `tool_id, tool_name, function, 语义输入格式 (Semantic Input), 输入格式, 语义输出格式 (Semantic Output), 输出格式, 下游工具, 适用组学` | 一条旧版工具/流程目录记录 |
| `project.csv` | 11 | 与 `entities/project.csv` 相同 | 根目录重复副本 |
| `sample.csv` | 6,918 | 与 `entities/sample.csv` 相同 | 根目录重复副本 |
| `study.csv` | 14 | 与 `entities/study.csv` 相同 | 根目录重复副本 |

#### 关系表

| 路径 | 数据行 | 完整列名 | 每行含义 |
|---|---:|---|---|
| `relations/T1_in_format.csv` | 13,772 | `files, format` | T1 文件到语义格式 |
| `relations/T1_in_level.csv` | 13,772 | `files, data_level` | T1 文件到数据层级 |
| `relations/T1_in_run.csv` | 13,772 | `files, run_accession` | T1 文件到 run |
| `relations/T1_in_study.csv` | 13,772 | `files, study_accession` | T1 文件到 study |
| `relations/T2_in_format.csv` | 86 | `t2_id, study_accession, files, format` | T2 到语义格式 |
| `relations/T2_in_level.csv` | 86 | `t2_id, study_accession, files, level` | T2 到数据层级；11 行 `level` 为空 |
| `relations/T2_in_study.csv` | 86 | `t2_id, study_accession, files` | T2 到 study |
| `relations/individual_in_study.csv` | 3,653 | `individual_accession, study_accession` | individual 到 study |
| `relations/run_in_sample.csv` | 8,354 | `run_accession, sample_accession` | run 到 sample |
| `relations/sample_in_individual.csv` | 6,850 | `sample_accession, individual_accession` | sample 到 individual |
| `relations/study_in_project.csv` | 14 | `study_accession, project_accession` | study 到 project |
| `relations/tool_has_function.csv` | 23 | `tool_id, function` | 工具到功能 |
| `relations/tool_input_format.csv` | 38 | `tool_id, 语义输入格式` | 工具到语义输入格式 |
| `relations/tool_output_format.csv` | 26 | `tool_id, 语义输出格式` | 工具到语义输出格式 |
| `relations/tool_relationship.csv` | 14 | `tool_id, next_tool_id, kind, output, input` | 工具的 NEXT 顺序及端口说明 |

#### 参考表

| 路径 | 数据行 | 完整列名 | 每行含义 |
|---|---:|---|---|
| `reference/cohort_subclass.csv` | 24 | `child, parent` | cohort 子类边 |
| `reference/cohorts.csv` | 26 | `status, description` | 一个 cohort 本体概念 |
| `reference/data_level.csv` | 4 | `level, name, description` | 一个数据层级 |
| `reference/formats.csv` | 29 | `语义格式, description` | 一个语义文件格式；29 行、28 个不同名称 |
| `reference/function.csv` | 23 | `function, description` | 一个工具功能 |
| `reference/multimodal.csv` | 8 | `modal, description` | 一个组学模态 |
| `reference/tool_types.csv` | 3 | `type, description` | 旧版工具类型：workflow/application/toolkit |

### 1.2 Neo4j 侧

在线库当前有 34,838 个节点、81,227 条关系。大写标签是部分小写目录节点的附加标签，不是完整的第二套节点，例如 24 个 `Tool` 与 24 个 `tool_id` 是同一批节点。

下表中 `属性=非空数/节点数` 即非空率；未列出的 CSV 空列在图中可能根本没有属性键。

| 标签 | 节点数 | 属性非空率 |
|---|---:|---|
| `t1` | 15,692 | `files, study_accession, sample_accession, run_accession, individual_accession, read_pair, format, data_level, experiment_accession, platform=15692/15692`; `strategy=4656/15692` |
| `t2` | 99 | `t2_id, study_accession, files, file_type, format, size, size_bytes, file_path=99/99`; `data_level=75/99`; `strategy=86/99` |
| `run` | 8,354 | `run_accession=8354/8354` |
| `sample` | 6,918 | 除 `sample_type=6276/6918`, `strategy=6128/6918` 外，其余 9 个 CSV 属性均 `6918/6918` |
| `individual` | 3,494 | 主键 `3494/3494`；主要字段：`study_accession=3494`, `project_accession=3429`, `gender=3398`, `age=3429`, `tumor_type=3428`, `specimen_types=3419`, `overall_survival_days=2912`, `overall_vital_status=3165`; 完整低覆盖字段包括 `tmb=1`, `msi_score/msi_status=10`, `adjuvant_treatment_agents=10`；CSV 的 `gleason_score, nerve_invasion, residual_tumor, tmb_status` 全空，图中无属性键 |
| `study` | 14 | 8 个 CSV 属性均 `14/14` |
| `project` | 11 | 除 `project_code=10/11` 外，18 个 CSV 属性均 `11/11` |
| `cohort` | 26 | `status, description=26/26` |
| `level` | 4 | `level, name, description=4/4` |
| `modal` | 8 | `modal, description=8/8` |
| `format` | 27 | `format=27/27`, `description=15/27` |
| `Format` | 18 | `format=18/18`, `description=6/18`；均同时带 `format` 标签 |
| `function` | 35 | `function=35/35`, `description=11/35` |
| `Function` | 24 | `function=24/24`；均同时带 `function` 标签 |
| `tool_id` / `Tool` | 24 | 同一批节点；`catalog_id, catalog_source, description, omics, tool_id, tool_kind, tool_name=24/24`; `input_format, output_format=11/24` |
| `io_slot` | 99 | `slot_id, slot_name, tool_id, direction, description, required=99/99`; `catalog_source=44/99`, `one_of_group=2/99` |
| `IOSlot` | 44 | `catalog_source, description, direction, required, slot_id, slot_name, tool_id=44/44`; `one_of_group=2/44` |
| `artifact_type` | 33 | `artifact_type, description=33/33`; `is_generic=24/33` |
| `ArtifactType` | 14 | `artifact_type, description=14/14`; `is_generic=5/14` |

为避免总览压缩隐藏字段，以下是逐标签的完整属性全集。格式为 `属性:非空数/节点数`：

- `t1`: `data_level:15692/15692, experiment_accession:15692/15692, files:15692/15692, format:15692/15692, individual_accession:15692/15692, platform:15692/15692, read_pair:15692/15692, run_accession:15692/15692, sample_accession:15692/15692, strategy:4656/15692, study_accession:15692/15692`
- `t2`: `data_level:75/99, file_path:99/99, file_type:99/99, files:99/99, format:99/99, size:99/99, size_bytes:99/99, strategy:86/99, study_accession:99/99, t2_id:99/99`
- `run`: `run_accession:8354/8354`
- `sample`: `biospecimen_anatomic_site:6918/6918, individual_accession:6918/6918, individual_name:6918/6918, sample_accession:6918/6918, sample_description:6918/6918, sample_name:6918/6918, sample_type:6276/6918, specimen_types:6918/6918, strategy:6128/6918, study_accession:6918/6918, tissue_type:6918/6918`
- `individual`: `adjuvant_treatment_agents:10/3494, adjuvant_treatment_outcome_response:3419/3494, age:3429/3494, clinical_m:379/3494, clinical_n:481/3494, clinical_t:480/3494, country:3429/3494, dfs_status:2404/3494, disease_free_survival_time:866/3494, family_history:1170/3494, fraction_genome_altered:1015/3494, gender:3398/3494, individual_accession:3494/3494, individual_id:3429/3494, lymphatic_invasion:182/3494, msi_score:10/3494, msi_status:10/3494, neoadjuvant_treatment_agents:1144/3494, neoadjuvant_treatment_outcome_pathological_response:753/3494, neoadjuvant_treatment_type:1158/3494, overall_survival_days:2912/3494, overall_survival_status:10/3494, overall_survival_time:2954/3494, overall_vital_status:3165/3494, pathologic_m:922/3494, pathologic_n:908/3494, pathologic_t:909/3494, primary_tumor_location:3429/3494, primary_tumor_site:3429/3494, progression_free_survival_status:327/3494, project_accession:3429/3494, project_name:3143/3494, race:3429/3494, sample_type:3429/3494, smoking:1910/3494, specimen_types:3419/3494, study_accession:3494/3494, tmb:1/3494, treatment_intent_type:2016/3494, tumor_grade:2645/3494, tumor_stage:2220/3494, tumor_subtype:3421/3494, tumor_type:3428/3494, vessel_invasion:1130/3494`
- `study`: `individual_count:14/14, information_source:14/14, sample_count:14/14, study_accession:14/14, study_description:14/14, study_type:14/14, title:14/14, tumor_type:14/14`
- `project`: `country:11/11, data_types:11/11, health_conditions:11/11, individual_count:11/11, information_source:11/11, organisms:11/11, organization:11/11, project_accession:11/11, project_code:10/11, project_description:11/11, project_name:11/11, release_date:11/11, relevance:11/11, sample_scope:11/11, study_accession:11/11, submission_date:11/11, tumor_type:11/11, type:11/11`
- `cohort`: `description:26/26, status:26/26`
- `level`: `description:4/4, level:4/4, name:4/4`
- `modal`: `description:8/8, modal:8/8`
- `format`: `description:15/27, format:27/27`; `Format`: `description:6/18, format:18/18`
- `function`: `description:11/35, function:35/35`; `Function`: `function:24/24`
- `tool_id` 和 `Tool`: `catalog_id:24/24, catalog_source:24/24, description:24/24, input_format:11/24, omics:24/24, output_format:11/24, tool_id:24/24, tool_kind:24/24, tool_name:24/24`
- `io_slot`: `catalog_source:44/99, description:99/99, direction:99/99, one_of_group:2/99, required:99/99, slot_id:99/99, slot_name:99/99, tool_id:99/99`; `IOSlot`: `catalog_source:44/44, description:44/44, direction:44/44, one_of_group:2/44, required:44/44, slot_id:44/44, slot_name:44/44, tool_id:44/44`
- `artifact_type`: `artifact_type:33/33, description:33/33, is_generic:24/33`; `ArtifactType`: `artifact_type:14/14, description:14/14, is_generic:5/14`

关系类型和方向如下，合计 81,227：

| 关系 | 方向 | 数量 |
|---|---|---:|
| `IN_RUN` | `t1 -> run` | 15,692 |
| `IN_SAMPLE` | `run -> sample` | 7,857 |
| `IN_INDIVIDUAL` | `sample -> individual` | 6,090 |
| `IN_STUDY` | `t1/t2/individual -> study` | 19,444（15,692 + 99 + 3,653） |
| `IN_PROJECT` | `study -> project` | 14 |
| `IN_FORMAT` | `t1/t2 -> format` | 15,791（15,692 + 99） |
| `IN_LEVEL` | `t1/t2 -> level` | 15,767（15,692 + 75） |
| `SUBCLASS_OF` | `cohort -> cohort` | 24 |
| `HAS_FUNCTION` | `tool_id -> function` | 35 |
| `INPUT` / `OUTPUT` | `tool_id -> format` | 21 / 37 |
| `HAS_INPUT_SLOT` / `HAS_OUTPUT_SLOT` | `tool_id -> io_slot` | 49 / 50 |
| `ALLOW_FORMAT` | `io_slot -> format` | 155 |
| `REQUIRES` / `PRODUCES` | `io_slot -> artifact_type` | 49 / 50 |
| `MANIFEST_AS` | `artifact_type -> format` | 81 |
| `NEXT` | `tool_id -> tool_id` | 14 |
| `HAS_STEP` | `tool_id -> tool_id` | 7 |

26 个 `cohort` 只有 24 条彼此间的 `SUBCLASS_OF`，与数据实体没有连接，因而都是数据图视角的孤立本体节点。

### 1.3 逐表覆盖对照

以下为全部 34 个文件，不截断。“逻辑覆盖”会对在线 T1 文件名末尾的 ` (N bytes)` 做与 matcher 相同的清理；“精确”则比较原始键和值。

| CSV 表 / 行数 | Neo4j 对应 | 字段覆盖与数量差异 | 影响 |
|---|---|---|---|
| `T11.csv` / 15,484 | `t1` / 15,692 | 逻辑覆盖 14,788：当前 T1 的 13,772 + HRA000021 BAM 1,016；缺 HRA000122 FASTQ 696；图另有 HRA000321 FASTQ 904。精确文件名仅重合 2,160。图无 `file_path, file_description, pipeline-id, parameter`；`data_type` 仅部分映射为 `strategy` | 不能把 T11 直接替换为在线 `t1`；缺路径会使 agent_input 无法物化 |
| `T2.1csv` / 99 | `t2` / 99 | 以 `study_accession::file_path` 生成主键后 99/99 精确对应；CSV 列 `stragy` 映射 `strategy`；图添加 `t2_id` | 在线 T2 明显来自旧版 T2.1，而非只来自当前 T2 |
| `entities/T1.csv` / 13,772 | `t1` / 15,692 | 13,772/13,772 按 `(study, run, R1/R2)` 覆盖；清理大小后文件名也全相等。原始文件名仅 1,144 相等。共同字段除 `strategy` 外逐值一致；图有 9,116 条 `strategy` 为空。CSV 的 `individualName, sampleDescription, sampleName, gender` 无图属性；图多 `format, data_level, read_pair`。图额外 HRA000021 1,016 + HRA000321 904 | 数据身份可覆盖，但不能按当前 `files` 主键直接 diff；assay 过滤会漏数 |
| `entities/T2.csv` / 86 | `t2` / 99 | 86/86 主键存在；图多 13 条旧 Clinical/MetaInfo。共同字段仅 `strategy` 有 9 条图中为空 | 矩阵、MAF、临床、VCF 目录没有迁移阻断；必须先删除/隔离 13 条陈旧记录并补 9 个 strategy |
| `entities/individual.csv` / 3,494 | `individual` / 3,494 | 主键完全相同；按空值等价比较 48 列零差异。4 个全空列未建属性键 | 内容覆盖完整 |
| `entities/project.csv` / 11 | `project` / 11 | 主键和 18 列逐值完全一致 | 完整 |
| `entities/sample.csv` / 6,918 | `sample` / 6,918 | 主键和 11 列逐值完全一致 | 节点完整，但到 individual 的边不完整 |
| `entities/study.csv` / 14 | `study` / 14 | 主键和 8 列逐值完全一致 | 完整 |
| `entities/tool.csv` / 23 | `tool_id` / 24 | 23 个 `catalog_id` 全有；图多 `TASK_RNASEQ_SINGLETASK`。字段已转成工具目录新模型，不能逐列一一对应 | 不属于数据 matcher；由独立目录同步器维护 |
| 根 `project.csv` / 11 | `project` / 11 | 与规范化文件逐字节相同，覆盖同上 | 重复真源风险 |
| 根 `sample.csv` / 6,918 | `sample` / 6,918 | 与规范化文件逐字节相同，覆盖同上 | 重复真源风险 |
| 根 `study.csv` / 14 | `study` / 14 | 与规范化文件逐字节相同，覆盖同上 | 重复真源风险 |
| `T1_in_format.csv` / 13,772 | `t1-[:IN_FORMAT]->format` / 15,692 | CSV 是语义格式 `Raw FASTQ`，在线边指向物理格式 `fq.gz/bam`，精确边 0；每个 t1 都有一条物理格式边 | schema 语义不同，迁移前必须决定物理格式与 artifact/语义格式的分层 |
| `T1_in_level.csv` / 13,772 | 同名边 / 15,692 | 当前 13,772 逻辑记录均有 level 1；按原始文件名仅 1,144 边精确；图多 1,920 | 需规范化主键后对照 |
| `T1_in_run.csv` / 13,772 | 同名边 / 15,692 | 当前 13,772 逻辑记录均覆盖；原始文件名仅 1,144 精确；图多 1,920 | 同上 |
| `T1_in_study.csv` / 13,772 | 同名边 / 15,692 | 当前 13,772 逻辑记录均覆盖；原始文件名仅 1,144 精确；图多 1,920 | 同上 |
| `T2_in_format.csv` / 86 | `t2-[:IN_FORMAT]->format` / 99 | CSV 指语义格式，在线边指 `dir/tsv/maf/xls/xlsx` 等物理格式，精确边 0 | 同一关系名承载不同语义，不能直接复用 |
| `T2_in_level.csv` / 86 | 同名边 / 75 | 75 条非空 level 精确覆盖；11 个 CSV 空 level 无边；图的 13 条旧记录也无 level | 与 CSV 空值一致，不是 11 条有值数据丢失 |
| `T2_in_study.csv` / 86 | 同名边 / 99 | 当前 86 全覆盖；图多旧 T2 13 | 需清理陈旧节点及边 |
| `individual_in_study.csv` / 3,653 | 同名边 / 3,653 | 3,653 精确相同 | 完整 |
| `run_in_sample.csv` / 8,354 | 同名边 / 7,857 | 少 497。目标 sample 均不在 `sample.csv`：HRA000321 452、HRA006499 45 | 经拓扑查样本时漏 497 个 run；配对会静默减少 |
| `sample_in_individual.csv` / 6,850 | 同名边 / 6,090 | 少 760：目标 individual 不在实体表 582；源 sample 不在实体表 219；两类有 41 重叠。按 study/来源：HRA000071 286、HRA001749 178、HRA007167 77、缺失 sample 的 HRA000321 178 和 HRA006499 41 | 经拓扑按 individual 分组会漏配或漏样本 |
| `study_in_project.csv` / 14 | 同名边 / 14 | 14 精确相同 | 完整 |
| `tool_has_function.csv` / 23 | `HAS_FUNCTION` / 35 | 23 全覆盖；多 12 个 pipeline/task 功能边 | 工具目录扩展，非数据迁移缺口 |
| `tool_input_format.csv` / 38 | `INPUT` 21；slot-format 50 个不同组合 | 语义格式与当前物理格式模型无精确组合 | 旧表不能作为当前目录的接口真源 |
| `tool_output_format.csv` / 26 | `OUTPUT` 37；slot-format 66 个不同组合 | 同上 | 同上 |
| `tool_relationship.csv` / 14 | `NEXT` / 14 | 14 条按 `catalog_id` 精确相同 | 完整 |
| `cohorts.csv` / 26 | `cohort` / 26 | 25 个名称精确；CSV `Oligo鈥恆strocytoma` 与图 `Oligo-astrocytoma` 不同 | CSV 有编码污染；需确定规范值 |
| `cohort_subclass.csv` / 24 | `SUBCLASS_OF` / 24 | 23 精确；1 条同受上述名称差异影响 | 同上 |
| `data_level.csv` / 4 | `level` / 4 | 4 个键全覆盖 | 完整 |
| `formats.csv` / 29 | `format` / 27 | CSV 29 行/28 个语义格式；在线 27 个物理格式，名称交集为 0 | schema 不同，不是简单缺节点 |
| `function.csv` / 23 | `function` / 35 | 23 个功能全覆盖；图多 12 个 pipeline/task 功能 | 当前目录扩展 |
| `multimodal.csv` / 8 | `modal` / 8 | 8 个键全覆盖 | 完整 |
| `tool_types.csv` / 3 | 无对应标签 | 图没有 ToolType 节点；`tool_kind` 为 atomic 12、pipeline 11、task_pipeline 1，与旧值 workflow/application/toolkit 不是同一枚举 | 旧 schema 已废弃，但仓库导入脚本仍会创建它 |

#### 三个重点结论

1. **T2 不会直接卡死迁移**：当前 86 个 T2 主键在线全有，包括表达矩阵、MAF、临床表和 VCF/BAM 目录。但在线多 13 条旧 Clinical/MetaInfo，9 个当前 T2 的 `strategy` 未更新；格式边的语义也不一致。
2. **T11-only 记录只覆盖一部分**：HRA000021 的 1,016 个 BAM 在线全有；HRA000122 的 696 个 FASTQ 在线为 0。在线另有 CSV 两版都没有的 HRA000321 904 个 FASTQ。
3. **sample 的 828 个悬空 individual**：828 个 sample 行引用的 individual 不在 `individual.csv`，分布为 HRA000071 286、HRA000122 287、HRA001749 178、HRA007167 77。在线没有为这些 accession 创建 placeholder individual，也没有相应关系。HRA000122 的 287 个 sample 根本未进入 `sample_in_individual.csv`；其余 541 个虽在关系 CSV 中，在线边仍缺失。

## 阶段二：同步路径与可复现性

### 2.1 现有脚本做什么

| 脚本 | 读取/动作 | 结论 |
|---|---|---|
| `cypher/import/00_clear.cypher` | `MATCH (n) DETACH DELETE n`，再尝试删除一批旧名称索引/约束 | 清整个数据库，不区分工具目录和数据图；很多在线当前约束名不在删除清单中 |
| `01_import_reference.cypher` | 读 7 张 reference 表，建 `Function/ToolType/Modal/Format/DataLevel/Cohort` 与 cohort 层级 | 文件和列存在，但标签与在线图不同，cohort 边名也从在线 `SUBCLASS_OF` 写成 `IS_SUBTYPE_OF` |
| `02_import_entities.cypher` | 读 tool、T1、T2、study、project、individual、sample | 文件/列存在；T1 写 `:T1.dataName/runAccession`，在线是 `:t1.files/run_accession`；T1 不写物理路径、format、level、read pair |
| `03_import_ontology_relations.cypher` | 读 12 张实体关系表及 tool-function，建 run/placeholder 和 IN_* 边 | 会为悬空外键 `MERGE` placeholder；在线库却没有这些 placeholder，证明路径不同或未完整执行 |
| `04_import_workflow_relations.cypher` | 读 3 张旧工具关系表，建 `INPUT/OUTPUT/NEXT` | 与当前 slot/artifact 工具目录模型不等价 |
| `05_validation.cypher` | 计数、查无类型工具、T2 无格式、工具输入输出和 T1-run-sample 示例 | 只打印，不断言；使用大写标签、`T1.runAccession` 和旧 ToolType，无法验证在线 schema |
| `scripts/python/import_runner.py` | 可选 `--run-clear` 后依次跑 schema 和 01-05 | 没有事务级回滚、数据域选择或陈旧节点删除 |
| `scripts/shell/run_import.sh` | 可选 CSV 校验；只复制 `reference/ entities/ relations/`；`RUN_CLEAR=true` 传 `--run-clear`；可 `SKIP_VALIDATE=true` | 不复制 T11、T2.1 或根目录重复表；隐藏的危险开关是 `RUN_CLEAR/--run-clear`，验证还可被跳过 |

### 2.2 是否最新、能否重导

当前脚本与当前 CSV 的文件名和列名大体对得上，没有引用已删除的 CSV 或不存在列。问题不是“跑不起来”，而是**跑出来的 schema 不是在线运行时 schema**：大小写、属性命名、关系语义、工具目录模型都不同。

现在有一条形式上可执行的重导路径，但没有一条可安全交付的重导路径：

- 不带 `--run-clear`：`MERGE` 只能新增/更新，不能删除 HRA000021/HRA000321 的 T1、13 个旧 T2 或旧关系；还会在在线小写图旁建一套大写图。
- 带 `--run-clear`：可以得到相对干净的大写图，但会删除整个数据库的 24 个工具及当前 slot/artifact/NEXT/HAS_STEP 目录；之后旧 importer 也恢复不了当前工具目录。
- 要实现精确同步，确实需要对**数据图域**做 replace，或导入一个新 database 后原子切换；不需要也不应该清整个工具目录所在数据库。

工具目录由 `sync_neo4j_tool_catalog.py` 管；数据图没有对应的现行同步器、owner 或维护说明。节点无 `imported_at/source_version/csv_checksum` 等时间戳，无法从图判断最后导入时间。数据图负责人和最后导入时间均为**待确认**。

### 2.3 建议的可重导路径（方案，不实施）

1. 固定目标 schema：统一小写标签/snake_case；把 `physical_format` 与 artifact/语义格式分开，不再复用同一个 `IN_FORMAT` 表达两种概念。
2. 为一次数据快照生成 manifest：源文件 SHA-256、行数、schema version、生成时间、负责人；导入节点写 `snapshot_id` 或通过单一 Snapshot 节点关联。
3. 首选 blue/green database：在新 database 导入并验证，再切换应用配置。若许可证/部署不允许多 database，则仅删除带明确 `data_graph` provenance 的节点和关系，禁止 `MATCH (n) DETACH DELETE n`。
4. 导入顺序为 reference -> 实体 -> 关系 -> 约束/索引验证 -> 覆盖对照 -> 双读语料；所有计数与悬空外键必须是会失败的断言。
5. 数据图导入与工具目录同步彻底分开。完成数据图切换后，再只读验证工具目录 24 节点、14 NEXT、7 HAS_STEP 及 slot 契约未变化。

## 阶段三：CsvKGDataMatcher 逐函数拆解

范围为 `pipeline_router.py` 中 matcher 直接使用的 36 个函数，共 791 个物理行（含 docstring、注释和多行字面量）；其中 `CsvKGDataMatcher` 类方法 468 行。下表的“读表/列”写“传入记录”时，表示函数不自行读 CSV，但依赖上游从这些列构造的记录。

| 函数 / 行号 / LOC | 做什么 | 读表/列 | 类型 | Cypher | 迁移估计 |
|---|---|---|---|---|---:|
| `_norm` 267-268 / 2 | 空值转字符串并 trim | 任意传入值 | 规范化 | 能 | 0，保留 Python |
| `_lower` 271-272 / 2 | norm 后小写 | 任意传入值 | 规范化 | 能 | 0 |
| `_normalize_assay_tokens` 283-300 / 18 | assay 拆词、同义词归一 | T1/T2 `strategy/data_type/Experiment` | 解析 | 部分；Cypher regex 可做但难维护 | 10-20，建议留 Python |
| `_canonical_assay_set` 303-307 / 5 | 合并 assay 词集 | pipeline profile | 聚合 | 能 | 0-5 |
| `_data_profile` 310-339 / 30 | 取 pipeline 所需角色、格式、strategy、terms | 静态模板/intent | 配置 | 不能替代；不是数据查询 | 0，保留 Python |
| `_sample_role` 370-388 / 19 | 按 study 特定规则判 tumor/normal | sample `study_accession/specimen_types/sample_name` | 分类 | 能，用 CASE；规则仍应配置化 | 15-25 |
| `_assess_wes_somatic_cases` 391-409 / 19 | 按 individual 判断两侧各恰好一对 | T1 + sample 的 individual/role/read pair | 分组/拓扑 | 能，且更自然 | 20-35 Cypher |
| `_wes_somatic_infeasibility_reason` 412-460 / 49 | 区分未登记、单侧、多样本等失败原因 | 上述分组结果 | 聚合/消息 | 部分；状态可查，文案应留 Python | 20-35 Python |
| `_role_satisfies` 463-471 / 9 | expression 通用/子类兼容 | 推断角色 | 校验 | 能 | 0-10 |
| `_fastq_pair_key` 478-486 / 9 | sample、run、文件 stem 三级配对键 | `sample_accession/run_accession/files/file_path` | 分组键 | 部分；有图身份时无需文件 regex | 10-20 |
| `_paired_fastq_groups` 489-500 / 12 | 聚合并只保留完整 R1/R2 | `files/read_pair` + 配对键 | 分组 | 能 | 15-25 Cypher |
| `_role_of_file` 503-525 / 23 | 按文件名和 format 推断角色 | T1/T2 `files/format` | 分类 | 能，用 CASE/正则；推荐返回属性后在 Python 复用同一规则 | 15-30 |
| `assess_feasibility` 528-638 / 111 | 角色齐全、数量、assay、FASTQ 拓扑、WES 配对总校验 | 文件候选各角色/strategy/拓扑 | 校验/聚合 | 部分 | 50-80，图返回事实，Python 生成合同与文案 |
| `_contains_any` 660-669 / 10 | 子串命中词表 | 任意拼接文本 | 过滤 | 部分；普通 CONTAINS 可做，无全文索引会扫表 | 5-10 |
| `_read_csv` 672-676 / 5 | 读整张 CSV | 所有 matcher 表 | I/O | 不适用，迁移后删除 | 0 |
| `__init__` 680-718 / 39 | 加载 7 类 CSV、建 lookup | study/project/sample/individual/T11/T1/T2/study-project | 加载/连接 | 不直接翻译 | 25-40，变为 driver/repository 注入 |
| `_load_normalized_t1` 720-768 / 49 | 用 T1 主表限制全集，T11 补路径，关系表补 format/level | T1 全列；T11 路径描述；T1 format/level | 连接/适配 | 能查询连接；路径数据目前图中缺失 | 40-70，含 DTO 适配 |
| `_clean_data_name` 771-772 / 2 | 去掉在线历史 `(N bytes)` 后缀 | `files/dataName` | 规范化 | 能 | 2-5；最好导入时修正 |
| `_infer_format` 775-780 / 6 | 从扩展名推物理格式 | `files` | 分类 | 能 | 5-10 |
| `_guess_read_pair` 782-788 / 7 | 从文件名推 R1/R2 | `files` | 分类 | 能 | 5-10 |
| `match` 790-819 / 30 | 调 cohort/file/combo 并装返回合同 | intent + pipeline | 编排 | 部分；应留应用层 | 25-40 |
| `_required_data_hints` 821-840 / 20 | 从 pipeline/intent 生成策略、格式、词项 | 静态 profile、query_text | 配置 | 不能替代 | 0-10，保留 Python |
| `_disease_terms` 842-845 / 4 | 癌种别名展开 | 静态 aliases | 配置 | 不能替代 | 0 |
| `_required_file_count` 847-856 / 10 | pipeline 所需文件数 | 静态 pipeline 映射 | 配置 | 不能替代 | 0 |
| `_row_text` 858-865 / 8 | 拼文件、study、project 全字段供子串搜索 | T1/T2 + study + project 全列 | 连接/文本 | 部分；图连接能做，拼全字段不适合长期方案 | 10-20 |
| `_match_cohorts` 867-911 / 45 | disease 硬过滤、omics/strategy 打分排序 | study 全列、project 映射 | 过滤/打分/排序 | 部分；连接过滤能，业务打分宜 Python | 35-55 |
| `_match_files` 913-1002 / 90 | 扫 T1+T2，连接文本，按疾病/格式/assay/terms/角色打分并排序 | T1/T2、study、project；关键列见表 | 过滤/打分/排序 | 部分 | 80-130；Cypher 做候选集，Python 保持现有打分和稳定 tie-break |
| `_file_role` 1004-1005 / 2 | role wrapper | 文件记录 | 分类 | 能 | 0 |
| `_allowed_file_roles` 1007-1008 / 2 | 取 pipeline 允许角色 | profile | 配置 | 不能替代 | 0 |
| `_filter_files_for_pipeline` 1010-1021 / 12 | 按兼容角色筛文件并写 input_role | 文件候选 | 过滤 | 能 | 5-15，建议留 Python |
| `_primary_display_files` 1023-1028 / 6 | 优先组合内文件，否则回退候选 | 组合/候选 | 选择 | 部分 | 5-10 |
| `_with_input_role` 1030-1033 / 4 | 补 input_role | 文件候选 | 变换 | 能 | 0-5 |
| `_trim_to_required_count` 1035-1045 / 11 | 去重后按 pipeline 截断 | 候选 | 聚合/截断 | 能 | 0-10 |
| `_dedupe_files` 1047-1056 / 10 | 按文件名/路径去重且保序 | `files/file_path` | 去重 | 能，保稳定排序需明确键 | 5-15 |
| `_pair_wes_somatic_cases` 1058-1099 / 42 | 按 individual 组 tumor/normal，各取唯一完整读对并打角色 | T1/sample/individual 拓扑与角色列 | 分组/连接/聚合 | 能，Cypher 更自然 | 35-60 |
| `_build_combinations` 1101-1169 / 69 | 按 study 构 FASTQ、表达+临床、MAF+临床 bundle | 所有候选角色和 study | 分组/组合 | 部分 | 55-90，查询事实 + Python 合同组装 |

按 791 LOC 粗分：可严格直接表达为 Cypher 的约 248 LOC（31%）；可部分下推但需 Python 保留业务规则/输出合同的约 294 LOC（37%）；应留在 Python 的配置、文案和编排约 249 LOC（32%）。因此“把 400 行全翻译成一个 Cypher”不是合适边界。预计新 Neo4j matcher 本体为 Python 320-480 LOC + 参数化 Cypher 140-220 LOC；双读、测试和导入修复另计。

### 难点判断

- `_role_of_file`：Cypher `CASE WHEN toLower(f.files) CONTAINS ...` 可以逐字表达，但这会在数据库、Python feasibility 和 diff 三处复制规则。短期应让 Cypher只返回 `files/format`，在共享 Python 函数中判角色；长期给数据节点写经版本化导入产生的 `asset_role`，查询只读该属性。
- 打分排序：连接、硬过滤和粗候选下推到 Cypher；现有分值、理由文本、稳定 tie-break 留 Python。这样最容易做到双读逐字段一致，也避免无全文索引的全图拼字符串搜索。
- `_pair_wes_somatic_cases`：图中从 file/run/sample/individual 聚合很自然，尤其可直接计算每个 role 的完整 sample 对数。但当前关系缺口会让正确 Cypher 得到错误结果，必须先修边。
- `assess_feasibility`：角色存在性、assay 和拓扑事实可由一个或数个参数化查询返回；“未知 assay 的兼容处理”、pipeline profile、失败原因优先级和用户文案应留 Python。

## 阶段四：性能实测

### 4.1 方法

- 机器和网络为当前本地环境，Neo4j 通过 `.env.local` 连接。
- `CsvKGDataMatcher` 实例只构造一次；构造/读 CSV 用时 141.212 ms，随后直接调用 `match()` 10 次，不走 LLM。
- `match()` 没有真正的“无限返回”模式：签名 `limit: int = 10`。本次不显式传 limit，即默认 10；但函数内部固定调用 `_match_files(..., limit=None)`，所以核心文件扫描和排序确实不截断，只有最终展示结果截断。
- Neo4j 使用 `READ_ACCESS`、同一 driver/session，每条查询完整消费结果；第 1 次包含连接/查询计划/缓存冷启动，后续为复用连接。

### 4.2 10 次分布

CSV 基准使用 demo 的配对 WES FASTQ intent，pipeline 为 `paired_fastq_to_unmapped_bam`；每次返回 cohort 10、主文件 2、备选 10、组合 1。

| 测试 | 返回行 | 10 次耗时 ms（执行顺序） | min / p50 / p95 / max ms |
|---|---:|---|---|
| CSV `match()` | 2 主候选 | `246.593, 231.183, 238.934, 237.438, 231.779, 230.570, 236.559, 248.218, 234.412, 235.665` | `230.570 / 236.112 / 247.405 / 248.218` |
| Neo4j `RETURN 1` 往返 | 1 | `90.922, 0.779, 0.414, 0.339, 0.418, 0.312, 0.257, 0.282, 0.269, 0.251` | `0.251 / 0.325 / 45.851 / 90.922` |
| 按测序类型筛 RNA-Seq FASTQ | 1,480 | `85.904, 24.987, 24.750, 20.630, 20.091, 19.193, 18.764, 18.823, 18.537, 18.512` | `18.512 / 19.642 / 55.445 / 85.904` |
| 按 matcher 规则筛 T2 MAF 角色 | 22 | `70.612, 10.532, 26.005, 6.334, 9.194, 5.098, 4.325, 8.373, 5.133, 4.052` | `4.052 / 7.354 / 48.309 / 70.612` |
| HRA000873 按 individual 配 tumor/normal | 1,015 | `123.590, 42.082, 32.096, 31.048, 28.364, 27.272, 31.851, 28.992, 31.172, 30.151` | `27.272 / 31.110 / 82.836 / 123.590` |

首轮连接成本约 70-124 ms；连接复用后的纯往返约 0.25-0.78 ms。返回 1,480 行的耗时主要是结果生成、排序和传输，不是网络 RTT。

### 4.3 索引

在线已有唯一索引/约束：`study.study_accession`、`individual.individual_accession`、`sample.sample_accession`、`run.run_accession`、`project.project_accession`、`t1.files`、`t2.t2_id`；另有 `t1.strategy` 和 `individual.tumor_type` 普通索引。没有 `t1.study_accession`、`t1.individual_accession`、`t1.sample_accession`、`t1.format` 或 T2 的 study/format 索引。

通过已索引实体节点再沿关系展开，accession 查询已有索引支撑。只读 PROFILE 对照如下（同一值、10 次 p50）：

| 查找 | 直接扫 `t1` 属性 | 从唯一索引实体沿边 | 倍数 | PROFILE 证据 |
|---|---:|---:|---:|---|
| study HRA000873，4,060 文件 | 10.128 ms | 1.615 ms | 6.3x | 直接路径 `AllNodesScan` 34,839 hits；实体路径 `NodeUniqueIndexSeek` + Expand |
| sample HRS169394，2 文件 | 7.811 ms | 0.699 ms | 11.2x | 直接 34,839 scan hits；实体 seek 2 hits 后展开 |
| individual HRI104775，4 文件 | 8.580 ms | 0.863 ms | 9.9x | 直接 34,839 scan hits；实体 seek 2 hits 后展开 |

不建索引无法实测“建后”数字；基于上面对照，若坚持按 `t1.*_accession` 直查，新增索引对选择性查询预计约 5-12 倍、落到 0.5-2 ms 量级，属于**估算**。更好的模型是修完整关系后利用现有实体唯一索引，不重复给 T1 的三个外键建索引。当前关系不完整时，沿边查询虽快却会静默漏记录，这是准确性问题，优先级高于索引。

### 4.4 端到端影响

当前 30-60 s custom 请求中，CSV 匹配中位数 0.236 s，只占约 0.39%-0.79%。三类 Neo4j 查询在热连接下顺序执行的 p50 合计约 58 ms，加上 Python 打分、DTO 组装和一次实际候选查询，合理预算为 80-150 ms；冷连接预算约 200-350 ms。若其他环节不变，custom 端到端约从 30-60 s 变成 **29.8-59.9 s**，不构成可感知提速。应复用长生命周期 driver，避免每次请求承担约 90 ms 冷连接。

## 阶段五：双读对照方案

### 5.1 接口和调用方

最小抽象为：

```python
class DataMatcher(Protocol):
    def match(
        self,
        intent: dict[str, Any],
        pipelines: Sequence[dict[str, Any]],
        limit: int = 10,
    ) -> dict[str, Any]: ...
```

直接调用方是 `PipelineRouter.route()`：`pipeline_router.py:1211` 调 `self.matcher.match(intent, matched[:1])`；`PipelineRouter.__init__` 在 1177 行默认构造 `CsvKGDataMatcher`。下游 `build_agent_input`/composer 消费 `cohort_candidates`、`file_candidates`、`backup_file_candidates`、`data_combinations` 和 `query_constraints`，所以新 matcher 必须保持整个返回合同，而不只是文件列表。

建议三个实现：

- `CsvKGDataMatcher`：原样保留，作为基准。
- `Neo4jKGDataMatcher`：相同签名和 DTO；只读 repository 封装参数化 Cypher，业务角色/打分尽量复用现有纯 Python helper。
- `DualReadDataMatcher`：同一输入顺序调用或并行调用两者；compare 模式仍把 CSV 结果交给生产调用方，只旁路写结构化 diff，直到 gate 通过再把主结果切到 Neo4j。

开关建议为 `DATA_MATCHER_MODE=csv|compare|neo4j`，默认 `csv`；不要复用工具目录的 bootstrap/apply 开关。Neo4j 超时在 compare 模式记录 `neo4j_error` 而不影响 CSV 主结果；neo4j 模式必须 fail closed，不能静默回退。

### 5.2 对照报告

先规范化再 diff，避免把已知表示差异当成数据差异：T1 去 `(N bytes)`，空属性与空字符串等价，集合按稳定身份比较，排序单独比较。稳定身份建议：cohort=`study_accession`；T1=`study+run+read_pair`；T2=`t2_id`；combo=`pipeline_id+study+individual+kind+有序文件身份`。

```json
{
  "schema_version": "data-matcher-diff/v1",
  "case_id": "...",
  "intent": {},
  "pipeline_ids": [],
  "timing_ms": {"csv": 0, "neo4j": 0},
  "sections": {
    "file_candidates": {
      "csv_count": 0,
      "neo4j_count": 0,
      "only_csv": [],
      "only_neo4j": [],
      "field_diffs": [
        {"identity": {}, "field": "strategy", "csv": "WES", "neo4j": null}
      ],
      "rank_diffs": []
    }
  },
  "material_diff_count": 0,
  "known_representation_diff_count": 0
}
```

目录建议：`data_matcher/base.py`、`csv_matcher.py`、`neo4j_matcher.py`、`dual_read.py`；只读查询放 `cypher/data_matcher/*.cypher` 或集中 repository 常量；离线入口为 `scripts/python/compare_data_matchers.py`；报告输出到显式指定的构建产物目录，不写运行库。

### 5.3 对照语料与打包 gate

语料分四层：

1. 复用 64 个 unittest 中所有会到 matcher/agent_input 的用例，新增 golden normalization，但不改原 CSV 基准断言。
2. 提取 `docs/demo_queries.json`、`docs/demo_queries_six_check.json` 等真实 demo 问句，固定 intent 和 pipeline，避免 LLM 波动污染 matcher diff。
3. 生成 `14 studies x 12 registered pipelines` 的确定性矩阵；对不支持的组合也断言双方同为 no combination/missing role。
4. 专门加入 HRA000021、HRA000122、HRA000321、HRA000873 配对、T2 的 count/TPM/MAF/clinical/metainfo、悬空 run/sample/individual、文件大小后缀和 assay 空值边界。

可以且应该成为打包前验证：要求 material diff=0、图 snapshot manifest 与打包清单一致、所有悬空外键在批准的 allowlist 内、24 工具目录不变。排序 tie 或表示差异只能通过有 owner、原因和到期时间的 allowlist 放行，不能笼统忽略。验证通过后再生成 Neo4j dump/backup 交付物；dump 的恢复演练和只读 smoke test 也是 gate 一部分。

## 阶段六：权威全集问题

### 6.1 1,712 条 T11-only 画像

| study | 文件数 | 文件/层级 | run / sample | read pair | 路径与质量信号 | 在线图 |
|---|---:|---|---:|---|---|---:|
| HRA000021 | 1,016 | 全为 WGS BAM，data_level=2 | 1,016 / 1,016 | `Read Pair` 被填成去掉首字母 H 的 run 号，如 `R067347`，不是合法 read role | 文件名、路径唯一；`file_description=#VALUE!`；pipeline-id/parameter 空 | 1,016/1,016，但图错误写 data_level=1、read_pair=`bam`，无 strategy |
| HRA000122 | 696 | 全为 WES `fq.gz`，data_level=1 | 348 / 287 | 348 个完整 R1/R2 对 | 696 文件名和路径唯一；描述正常；Illumina HiSeq X Ten；pipeline-id/parameter 空 | 0/696 |

两组都没有重复文件名；HRA000122 每个 run 恰好两个文件，没有缺 mate，61 个 sample 对应多个 run 是合理的多 run 结构，不能仅据此认定质量不合格。HRA000021 的 `Read Pair` 和 description 有明显元数据质量问题，但 BAM 本身不需要 R1/R2 配对。

### 6.2 能否从数据推断 T1 排除规则

只能推断出一条**部分规则**：规范化 T1 全部是 data_level=1 FASTQ，所以 HRA000021 的 level-2 BAM 被排除符合“T1 只收一级测序文件”的解释。

无法从数据推断 HRA000122 的排除规则。它同样是 level-1、成对、格式正常的 WES FASTQ。HRA000122 的 287 个 sample 引用 165 个不在 individual 实体表的 accession，且没有 sample-individual 关系；但 HRA000071、HRA001749、HRA007167 也有同类悬空 individual，其 FASTQ 仍进入 T1。因此“外键必须完整”不是一致的排除规则。是否因授权、质控、版本、队列撤回或人工名单被排除，均为**待确认**。

需要数据负责人明确回答：

1. T1 的业务定义是“一级原始文件”、 “可用于 matcher 的合格文件”，还是某次人工快照？
2. HRA000122 是否有访问授权、样本质控、撤回或重复队列问题？若有，判据和证据字段是什么？
3. HRA000021 BAM 应属于 T1、T2，还是只保留在存储清单？在线 data_level=1 是否错误？
4. HRA000321 为何只在在线图和关系表中出现，而不在 T1/T11/sample 实体表？它是应补入 CSV 的新数据，还是应清除的旧残留？
5. `sample_in_individual.csv` 中 219 个源 sample 不在 sample 实体表、582 个目标 individual 不在 individual 实体表，placeholder 是正式模型还是导入补丁？
6. 权威全集的版本号、生成脚本、owner、更新频率和下线/删除语义是什么？

在这些问题确认前，Neo4j 既不应装“简单并集”，也不应只装 T1；权威全集定义为**待确认**。

## 最终判断

### 值不值得做

值得做，但理由是统一运行时真源、可追溯、关系查询和交付一致性，不是性能。当前 CSV matcher 已足够快；若没有 snapshot、删除语义和双读 gate，把数据搬进 Neo4j 只会把两个真源变成一个不可信真源。

### 最大风险

最大风险是**静默漏配/错配**，不是迁移脚本报错。在线图的缺边会让按拓扑实现的 Cypher 合法地返回不完整结果；T1 的 strategy 空值会漏 assay；T2 旧记录会改变排序；路径缺失会产生看似匹配但不可执行的资产。现有 importer 又无法复现在线 schema，出错后难以审计来源。

### 分阶段第一步

第一步应是“数据图可复现性”，不是 matcher 重写：确定权威全集和目标 schema，写数据域独立的 snapshot importer，在隔离 database 中导入，做到 34 张表的计数、字段、主键、关系和悬空外键验证全部可重复。随后实现只查询候选集的 Neo4j matcher，并以 CSV 为主结果跑双读。

### 离“最新最全”还有多远

节点属性层面，study/project/sample/individual 已与当前 CSV 高度一致；T1/T2 和拓扑层面仍未达到：缺 HRA000122 696 T1，额外 HRA000021/HRA000321 1,920 T1，T1 strategy 缺 9,116，额外旧 T2 13、当前 T2 strategy 缺 9，run-sample 缺 497、sample-individual 缺 760，物理/语义 format 混用，T1 物理路径未入图，且无导入时间/版本。补齐需要权威集决策、目标 schema、关系修复、路径/provenance、精确 replace 同步、双读全量对照和恢复验证。

### 另外一个关键问题

Neo4j 交付物不是只有数据 dump。还必须冻结 Neo4j 版本、插件、database/约束/索引定义、导入 manifest、恢复命令、只读账号权限和恢复后 smoke test；否则“打包后可恢复”无法证明。另一个容易忽略的问题是删除语义：当前 `MERGE` 导入只能加不能删，任何权威 CSV 下线记录都会永久残留。迁移验收必须包含删除/撤回用例。
