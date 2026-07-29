# 数据图验证报告

生成时间：2026-07-24T09:12:02.773948+00:00
目标 database：`datagraph-staging` (`AF76A4FDB2817F94BD15471B3956E277CD52659FC960C514A67345F59531F1EF`)
scope：`t1`；snapshot：`dg-b23135d49c950d0846a563bc`

## 结论

✅ 实质差异 0；已知表示差异 0。

## 六层验证

- ✅ **计数**：expected={'labels': {'cohort': 26, 'data_format': 28, 'data_format_row': 29, 'data_level': 4, 'data_modal': 8, 'individual': 3494, 'project': 11, 'run': 8354, 'sample': 6918, 'study': 14, 't1': 13772, 't2': 86}, 'relationships': {'DESCRIBES_FORMAT': 29, 'IN_FORMAT': 13857, 'IN_INDIVIDUAL': 6090, 'IN_LEVEL': 13847, 'IN_PROJECT': 14, 'IN_RUN': 13772, 'IN_SAMPLE': 7857, 'IN_STUDY': 17511, 'SUBCLASS_OF': 24}}; actual={'labels': {'cohort': 26, 'data_format': 28, 'data_format_row': 29, 'data_level': 4, 'data_modal': 8, 'individual': 3494, 'project': 11, 'run': 8354, 'sample': 6918, 'study': 14, 't1': 13772, 't2': 86}, 'relationships': {'DESCRIBES_FORMAT': 29, 'IN_FORMAT': 13857, 'IN_INDIVIDUAL': 6090, 'IN_LEVEL': 13847, 'IN_PROJECT': 14, 'IN_RUN': 13772, 'IN_SAMPLE': 7857, 'IN_STUDY': 17511, 'SUBCLASS_OF': 24}}
- ✅ **字段覆盖与逐值比较**：labels=12; known_representation_diffs=0
- ✅ **主键唯一性**：checked_labels=12; violations=0
- ✅ **关系完整性与悬空外键**：materialized=73001; explicitly_skipped=1269
- ✅ **确定性值级抽样**：tables=23; sampled_missing=0
- ✅ **CSV 往返全量 diff**：tables=23; differing_tables=0

## 悬空外键

策略：`skip_edge_and_report`；共 1269 条。

| 来源 | 关系 | 缺失端 | 数量 |
|---|---|---|---:|
| `relations/T2_in_format.csv` | `IN_FORMAT` | `end` | 1 |
| `relations/T2_in_level.csv` | `IN_LEVEL` | `end` | 11 |
| `relations/run_in_sample.csv` | `IN_SAMPLE` | `end` | 497 |
| `relations/sample_in_individual.csv` | `IN_INDIVIDUAL` | `end` | 541 |
| `relations/sample_in_individual.csv` | `IN_INDIVIDUAL` | `start` | 178 |
| `relations/sample_in_individual.csv` | `IN_INDIVIDUAL` | `start,end` | 41 |

## 特殊 study 抽样

| study | 权威范围可用 | 已检查 | 目标 | 短缺 |
|---|---:|---:|---:|---:|
| HRA000021 | 1530 | 20 | 20 | 0 |
| HRA000122 | 289 | 20 | 20 | 0 |
| HRA000321 | 69 | 20 | 20 | 0 |
| HRA000873 | 7114 | 20 | 20 | 0 |

四个指定 study 均已完成 20 条确定性抽样。
HRA000321 生产图额外 T1 的负向对照放在生产/隔离对照报告中完成。

## 差异

实质差异：0；已知表示差异：0。

## 实际导入过程

| 步骤 | 结果 |
|---|---|
| 生产备份 | 写入前已完成只读逻辑备份：34,838 节点、81,227 关系、16 约束、19 索引；SHA-256 `34025502...b2a7` |
| 隔离身份 | Neo4j Community 2026.06.0 独立实例，Bolt `7688`；目标 ID `AF76A4FD...F1EF`，与生产 `3B6484DB...C7B1` 不同；写入前 0 节点、0 工具节点。故意将 dry-run 连向生产但要求 staging ID 的负向测试返回码 1，在任何 schema/删除/写入前因 ID mismatch 拒绝 |
| dry-run | snapshot `dg-b23135d49c950d0846a563bc`；预期 32,744 节点、73,001 关系、1,269 条悬空外键 |
| canonical 导入 | 图指纹 `f14a565c755f8235ddd13b91223ea7be946d5539a255864c553594456b488afe` |
| 六层验证 | 计数、字段/逐值、主键、关系/悬空、确定性抽样、23 张源表全量往返全部 PASS |

## 可复现性

在最终脚本版本上对同一 canonical CSV 连续执行两次范围内全量替换：

| 比较项 | 第一次 | 第二次 | 结果 |
|---|---|---|---|
| 节点/关系计数 | 32,744 / 73,001 | 32,744 / 73,001 | 相同 |
| graph fingerprint | `f14a565c...afe` | `f14a565c...afe` | 相同 |
| reproducible fingerprint | `66d6a5b9748951556adcb7b01f41ec450127da83786cff3bf7c611d75a77d66e` | 同值 | 相同 |
| manifest `reproducible` 段 | 完整 JSON | 完整 JSON | 逐字段相等 |

`generated_at`、耗时和 URI 只在 `run_metadata` 中，不进入稳定指纹。

## 删除语义实测

在 `/tmp` 的 CSV 全量副本中删除 T2 `HRA000021::/hpcdisk1/cbb_group/data/analysis/HRA000021/BAM-files` 及它在三张 T2 关系表的行。重导后：

- T2 从 86 变为 85，目标节点计数为 0；
- `IN_STUDY/IN_FORMAT/IN_LEVEL` 各减 1；
- 临时快照六层 verifier 仍为 0 实质差异；
- 随后从未修改的 canonical `data/csv/` 重导，已恢复 86 个 T2 和 canonical 图指纹。

## Dump / restore 演练

隔离库正常停止后产出 Neo4j 原生 dump：`docs/backups/datagraph_staging_dump_20260724T090000Z/datagraph-staging.dump`，大小约 86 MiB，SHA-256 `1c606e01489a8d472d1a95f9d86f3437e5e2818ea08da61c8a41e56922ac3641`。

该 dump 已 load 到全新 Neo4j home，使用独立 Bolt `7689`、HTTP `7476`和独立认证。恢复后为 32,744 节点、73,001 关系、0 工具节点；六层 verifier 仍为 0 实质差异。Smoke query 返回 WES FASTQ 8,922 个/4,461 个 run，T2 表达、MAF、临床/元数据角色和 individual 多样本拓扑均可查。

## 判断

### 导入过程中遇到的最大意外

最大意外是第二次全量替换时，单事务 `DETACH DELETE` 32,744 个带较大 provenance 的节点触发 Neo4j `MemoryPoolOutOfMemoryError` 的 358.4 MiB 事务内存上限。该事务回滚，未影响生产。导入器已改为可配置的 500 节点分批删除，每批前重新执行隔离身份门禁。另一个环境意外是 Neo4j launcher 对含中文的 home 路径做了错误转义，因此 staging/restore 均改用 ASCII home。

### CSV 数据质量问题

导入时新确认 1,269 条悬空关系原行：`run_in_sample` 497，`sample_in_individual` 760，以及此前易忽略的 T2 空格式 1 和空 level 11。`formats.csv` 有 29 行但只有 28 个唯一名称，`Sample Metadata` 有两条不同描述。恢复后 smoke query 还显示两个 `Fusion` T2 被源关系标为 `Raw Counts`，部分 BAM/SpliceJunction 的语义格式也可疑。导入器忠实保留这些值，没有自行纠正。

### 非确定性来源

最终两次连续导入没有暴露输出非确定性。脚本中的节点、关系、源文件和悬空列表均在指纹前排序；`snapshot_id` 基于内容 hash；时间和耗时被隔离在非稳定 `run_metadata`。最终稳定 manifest 逐字段完全相等。

### 能否直接作为打包 gate

可以作为数据图本身的打包 gate：它有非零失败退出码、六层验证、全量往返 diff、manifest 和显式 allowlist，且已在 dump 恢复库上实证。要成为完整产品打包 gate，还需 CI 安全注入凭证/目标 ID、启动一次性 Neo4j 实例、审核 allowlist owner/expiry，并在下一轮加上 CSV/Neo4j matcher 双读合同对照。

### 下一轮 Neo4j matcher 风险

最可能出问题的是：新 `IN_FORMAT` 是语义格式而非生产旧图的物理格式；1,269 条悬空拓扑不能被当成“没有数据”而静默忽略；T2 角色不能仅信任有噪声的 format 边；`_role_of_file`、打分和失败文案仍应留在 Python；WES tumor/normal 必须通过 sample-individual 拓扑和同源 R1/R2 完整性共同判定。

### 其他关键问题

原生 dump 会保留 database store ID，因此在克隆恢复库上，仅核对 `CALL db.info().id` 不能证明连接的是哪个实例；还必须核对 URI/端口、进程 home、system database ID 和物理数据目录。此外，T1/T11 的 696 个 HRA000122 WES FASTQ 权威归属仍是数据负责人待确认项；本快照只可声称忠实复现当前 T1，不可声称已确定“最新最全”。
