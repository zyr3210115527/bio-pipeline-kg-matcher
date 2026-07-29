# Dual-read Report

## 结论

CSV 与 Neo4j matcher 的全量确定性对照达到实质差异 0，允许从双读门禁进入 MCP 的 Neo4j 默认配置。报告 schema 为 `data-matcher-diff-suite/v1`，每个 case 内嵌 `data-matcher-diff/v1` 的集合、字段和排序差异。

## 实现边界

`Neo4jKGDataMatcher` 只替换数据加载层：通过 READ_ACCESS 和参数化 Cypher 读取 `datagraph/v1`，再复用 `CsvKGDataMatcher` 的过滤、打分、角色推断、R1/R2 分组、tumor/normal 配对、assay 校验和组合构建。它不依赖不完整的图拓扑。Neo4j 模式配置或 snapshot 不匹配时直接失败，不回退 CSV。

`compare` 模式以 CSV 结果为主返回值，Neo4j 异常写为 `neo4j_error`；`neo4j` 模式 fail closed。运行时默认仍可显式切回 `csv`，交付 MCP 配置默认 `neo4j`。

## 对照合同

- cohort identity: `study_accession`
- T1 identity: `study_accession + run_accession + read_pair`
- T2 identity: `t2_id`
- combination identity: `pipeline_id + study + individual + kind + ordered file identities`
- 规范化：空字符串/null 等价；历史 ` (N bytes)` 后缀移除；集合成员和排序分别检查
- allowlist：两条规则均有 `owner=data-catalog-owner` 和具体理由；本轮实际命中 0

## 语料与结果

| 层 | case 数 | 实质差异 |
|---|---:|---:|
| matcher/agent_input 回归提炼 | 6 | 0 |
| `docs/demo_queries.json` | 7 | 0 |
| 14 study x 12 registered pipeline | 168 | 0 |
| HRA/T2/assay/后缀边界 | 10 | 0 |
| 合计 | 191 | 0 |

六条完整 composer demo 另做递归逐字段对照，6/6、差异 0，见 `docs/demo_mode_comparison.json`。

## 性能

| 指标 | CSV | Neo4j |
|---|---:|---:|
| 初始化 | 227.675 ms | 2,354.097 ms |
| match p50 | 169.656 ms | 170.887 ms |
| match p95 | 241.975 ms | 244.366 ms |
| match max | 392.858 ms | 361.703 ms |

Neo4j 初始化读取 32,744 个节点中的 matcher 所需实体，服务进程会缓存 matcher。初始化后，两端执行相同 Python 逻辑，耗时近似。custom 端到端 30-60 秒的瓶颈仍是两阶段 LLM，不是 matcher。

最终 D dump 恢复库上重复 191 case 仍为 0 差异；Neo4j match p50 173.757 ms。原始报告为 `docs/data_matcher_diff_results.json` 和 `docs/restore_data_matcher_diff_results.json`。
