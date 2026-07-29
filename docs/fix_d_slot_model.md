# Stage D Slot Model and Binding Report

## 结论

阶段 D 已作为一个整体发布到隔离 staging，未留下“只有槽、没有绑定/variant”的中间态。生产 `7687/neo4j` 全程只读。最终目录为 233 节点、601 关系，fingerprint `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`；其中 24 tools、58 input slots、53 output slots、28 NEXT、7 HAS_STEP。

## 五处耦合改动

| 项 | 实现 | 关键位置 |
|---|---|---|
| D1 槽身份 | canonical `io_slot.csv` 独立保存 `slot_id/slot_name/artifact/required/dimension/dimension_value/variant`，同 artifact 的具名槽不折叠 | `data/csv/catalog/io_slot.csv`; `sync_neo4j_tool_catalog.py:177-250` |
| D2 NEXT 四元组 | data 边以 source tool/output/target tool/input 区分；菜单目标去重，运行时 data edge 保留四元组 | `sync_neo4j_tool_catalog.py:253-290`; `workflow_composer.py:175-189` |
| D3 配对资产 | `wes_somatic_pair` 数据 profile 取得同个体四条 FASTQ；`read_pair/sample/run/individual/sample_role` 进入 `file_details` 和 assets | `pipeline_router.py:1235-1303,1980-1992`; `workflow_composer.py:2183-2219` |
| D4 维度绑定 | asset 选择同时按 step sample role 与 slot mate 精确过滤；无精确候选返回 missing，不复用最后候选 | `workflow_composer.py:2515-2559,2580-2634` |
| D5 条件必需性 | fastp 和 GATK 使用完整输入变体集合；validator 和 agent contract 均唯一推导，部分/混合变体失败关闭 | `workflow_composer.py:1803-1831`; `tool_id.csv` |

额外发现：原连通性规则只允许一个根节点，无法忠实表达 tumor/normal 两条并行链。现只允许一种双根拓扑：两个根的 sample role 必须恰为 tumor/normal，工具相同且输入形状相同；其他断链仍报错。这是收紧后的显式配对拓扑，不是一般性放宽。

## 目录增量

- fastp：具名 R1/R2 input/output；single_end 与 paired_end 两个 variant；旧 generic 槽保留为 single-end compatibility alias。
- BWA：具名 clean R1/R2 input；旧 generic 槽保留。具名槽不设全局 required，是否使用由上游链和精确 NEXT 四元组决定。
- SAMtools：新增 `bai` output。
- GATK：新增 `tumor_bam/tumor_bai/normal_bam/normal_bai` 和 execution-managed `interval_list`；旧 `sorted_dedup_bam` 保留为 single variant。
- 新增 artifact/format：`bai`、`interval_list`。
- 新增 6 条 data NEXT 四元组；B 阶段 22 条增至 28 条。

## 原子发布

bootstrap 原先先提交 canonical 目录、再逐条写 NEXT，不满足本阶段原子性。现 `_replace_catalog_and_next` 在同一 Neo4j write transaction 内完成目录替换、端点检查与 NEXT 替换。隔离库故障注入使用不存在的端点 `DOES_NOT_EXIST`，事务在目录重建后报错；前后 fingerprint 均为 `2ec21a69...5c903`，证明完整回滚。

## 7.4 验证

### A. 配对 WES 实跑

原句“我有肿瘤和正常配对的 WES FASTQ,想做体细胞变异检测并注释”在真实 LLM + CSV matcher + Neo4j catalog 下生成两条独立 `fastp -> bwa -> samtools` 链，再汇合到 GATK、bcftools、SnpEff。

| 检查 | 结果 |
|---|---|
| tumor/normal 双链 | PASS |
| GATK 四个 input 都有 from | PASS |
| BAM/BAI 来自对应侧 SAMtools | PASS |
| 跨样本连接 | 0 |
| 四条 FASTQ 的 sample_role/mate/individual | 全部保留且绑定正确 |
| R1/R2 均被引用 | PASS |
| plan/contract validation | true/true |
| execution_status | `draft_requires_pipeline_materialization`，不再 blocked |

第一次五连跑门禁为 4/5：第 5 次发生外部 API 连接失败，配对请求的生成重试额外给出一条非法 MultiQC 链，validator 正确返回 `no_match`。未把它算作通过。第二轮第 6-10 次核心绑定、GATK 四路来源、validation 均 5/5 通过。第 9 次合法追加了 order-only MultiQC，因此不稳定字段为 `steps`、`match_id` 和模型请求重试次数；核心 9 步及所有数据绑定稳定。

### B. 打乱与破坏性测试

`tests/test_slot_model.py` 对四资产使用 5 个不同排列，四次精确归位均一致。交换 tumor/normal 标签后 contract validation 失败；交换 R1/R2 mate 后 contract validation 失败。没有列表位置回退。

### C-D. 单样本与 variant 边界

| Case | 结果 |
|---|---|
| 单样本 WES，GATK `sorted_dedup_bam` | PASS，variant=single |
| fastp 旧 generic 单端 | PASS |
| fastp 具名 R1 单端 | PASS |
| tumor fastp 缺 R2 | FAIL CLOSED |
| GATK paired 缺 normal/BAI | FAIL CLOSED |
| GATK single + paired 混用 | FAIL CLOSED |

### E. 全量门禁

- CSV schema/FK/variant/NEXT 四元组校验：PASS。
- 隔离 catalog gate：两次 bootstrap 幂等，233/601，fingerprint 不变。
- unittest：81 OK，3 个既有真实集成跳过。
- staging 双读：191 cases，material diff 0。
- unified graph：9/9。
- 六条完整 composer CSV/Neo4j 对照：6/6，差异 0。
- MCP：staging 在线/离线各 12/12。
- 新 dump 恢复到全新 home：9/9、191/191、MCP 在线/离线各 12/12。

## 保守选择

旧 fastp/BWA generic 槽和 `samtools.sorted_dedup_bam -> gatk.sorted_dedup_bam` 边全部保留。generic fastp 只映射到 single-end R1，不允许它伪装 paired-end。BWA 的具名槽不设全局 required，以免旧调用方突然缺两个新槽；新配对链仍必须通过具名四元组连接。这个兼容策略值得后续在 tool-chain/v2 中讨论废弃期，但本轮不破坏既有合同。
