# 96 例问题-数据-工具回归

## 返回合同

`tool-chain/v2` 新增 `recommendations[]`，用于返回业务 pipeline、Neo4j 工具节点详情和逐文件数据证据。原有 `candidates[]` 继续只承载通过闭集、槽位、NEXT、数据和 Knowledge Card 校验的 atomic 工具链，两者不能互相替代。

工作簿 `96例问题-数据-工具对应表(1).xlsx!Sheet1:B2:D97` 被固化为 `config/question_tool_data_benchmark.json`。精确命中审核问题时，表格只决定期望 pipeline ID 和待核验文件名；工具详情、路径和文件存在状态仍由 Neo4j 返回。

## 结果

| 检查 | 结果 |
|---|---:|
| 问题数 | 96 |
| pipeline ID 正确 | 96/96 |
| 返回数据文件名与审核表一致 | 96/96 |
| pipeline 工具已在 Neo4j 登记 | 90/96 |
| pipeline 工具缺少 Neo4j 节点 | 6/96 |
| 所有期望文件均在图谱存在 | 54/96 |
| 至少一个期望文件缺失 | 42/96 |

缺少工具节点的两个 pipeline 是 `cellranger_workflow` 和 `wes_somatic_pair`，各影响 3 条问题。系统返回 `tool.catalog_status=missing_from_neo4j`，不会编造 pipeline 工具定义。

图谱中缺少 10 个唯一文件：

- `ENCSR142YZV_chr19only_10000_reads_R1.fastq.gz`
- `ENCSR142YZV_chr19only_10000_reads_R2.fastq.gz`
- `HRA000074-Clinical-1.0.xls`
- `HRA001272-MetaInfo-1.0.xlsx`
- `HRA003107-Clinical-1.0.xls`
- `HRA007167-Clinical-1.0.xls`
- `HRA007169-Clinical-1.0.xls`
- `HRA007169-MetaInfo-1.0.xlsx`
- `NVM0598_R1.clean.clean.fastq.gz`
- `NVM0598_R2.clean.clean.fastq.gz`

缺失文件以 `data.status=missing_from_graph` 和 `assets[].graph_status=missing_from_graph` 返回，不附加虚构路径。同一推荐中的已找到资产限制在同一个 study；非审核原句如果只能找到部分组合，会同时返回同 study 的已找到资产和 `missing_data_roles`。

## 验证

- Python 单元测试：89 discovered，86 passed，3 个 opt-in real integration skipped。
- 统一图：9/9；catalog fingerprint 保持 `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`。
- CSV/Neo4j 双读：191/191，0 material differences，0 representation differences。
- MCP live/offline：各 12/12。
- 消费方黑盒验收：5/5，其中包含 `diff_expr_go` 工具和数据证据。
- 真实 LLM 非原句测试：`肝癌 TPM + 样本信息 + 免疫浸润` 正确推荐 `immune_infiltration_iobr`；Neo4j 返回 HRA001272 的 TPM/Clinical，并标明缺 `metainfo`。

机器可读结果见 `outputs/96_mapping_analysis/evaluation.json`。
