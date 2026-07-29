# 数据图验证报告

生成时间：2026-07-24T09:15:10.116316+00:00
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

## 判断

该报告是 dump/load 后的独立 gate 证据：32,744 节点、73,001 关系、23 张源表全量往返，0 实质差异。导入意外、CSV 质量问题、非确定性、打包 gate 边界和下一轮 matcher 风险的完整判断见 `docs/datagraph_verification_report.md`。
