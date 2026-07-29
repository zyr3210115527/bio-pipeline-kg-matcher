# 最终交付审核

审核日期：2026-07-22

## 交付结论

当前版本可以稳定区分三类请求：

1. `standard`：一个或多个 Neo4j 标准 pipeline 可以原样完整覆盖需求；
2. `custom`：用户明确替换、删除、插入或重排内部步骤，模型只能从 Neo4j atomic tool 闭集组装；
3. `capability`：回答“能做什么”“有哪些流程/工具”“哪些流程需要某类输入”等非执行问题。

显式个性化修改优先于能力问答和标准流程。程序会复核模型判定，避免把内部修改误判为预制菜，也避免把多个完整 pipeline 的组合误拆成 atomic tool。运行参数与执行端参考资源不影响编排状态；只有用户样本数据缺失会进入 `missing_assets`。历史实现风险继续返回给执行端，但不阻断编排。

## 当前 Neo4j 真源

- Neo4j：Community `2026.06.0`，数据库 `neo4j`；
- 24 个 tool：12 个 atomic tool、11 个 pipeline tool、1 个 task-pipeline；
- 14 条审核后的 `NEXT`；
- `rnaseq_singletask`：7 条锁定 `HAS_STEP`；
- `paired_fastq_to_unmapped_bam`：当前无 `HAS_STEP`，按 1 个 pipeline-level tool 返回；
- WDL 仅保留为历史审查材料，不参与运行时工具发现、预制菜或自助餐。

当前 Neo4j 只登记了 12 个标准 pipeline/task-pipeline，不是早期 WDL 目录中的 14 个。系统不会为尚未登记的两个流程或未拆解步骤伪造工具。

## 关键规则

- “有哪些流程处理 MAF”是 `capability`；“我的 MAF 该选哪个流程”是一次路由；
- “有哪些流程能把 RSEM 换成 Salmon”因包含内部替换而进入 `custom`；
- “不用管运行参数”不会触发 `custom`；
- `FASTQ + RNA-seq + 表达矩阵/计数`保守指向 `rnaseq_singletask`；
- “突变景观 -> TMB 生存”和“同时做 GO + KEGG/Reactome”按完整标准 pipeline 组合处理；
- STAR 主基因组输出为 `aligned_bam`，精确连接 `SAMtools.aligned_bam`；
- 未登记的 Salmon、FASTQ-to-uBAM atomic tool 等能力返回 decomposition gap，不使用近似工具替代。

## 真实回归结果

使用 `deepseek-v4-pro`、真实本机 Neo4j 和 `/api/ask` 完成发布矩阵：

| 用例 | 结果 | 工具/流程 |
| --- | --- | --- |
| 哪些流程处理 MAF | `capability / information` | 4 个 MAF pipeline |
| RNA-seq FASTQ 到表达矩阵选哪个 | `standard / ready` | `rnaseq_singletask` |
| 突变景观后做 TMB 生存 | `standard / missing_assets` | 两个标准 pipeline；缺少用户临床/MetaInfo 数据 |
| 完整 RNA 链去掉 RSEM | `custom / draft` | 6 个 atomic tool，契约校验通过 |
| RSEM 换成 Salmon | `custom / no_match` | 正确返回未拆解方法缺口 |

另有 4 个 FASTQ 高混淆问题全部通过真实 DeepSeek 路由；Neo4j 版本、目录数量、14 条 NEXT 和 7 条 RNA recipe 的真实集成测试通过。

## 自动验证

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py app.py intent.py pipeline_router.py \
  workflow_composer.py runtime_config.py neo4j_observability.py scripts/python/*.py
python3 scripts/python/validate_csv.py --project-root .
python3 scripts/python/run_live_regression.py --base-url http://127.0.0.1:8012
```

最终本地测试：56 项通过，3 项真实集成测试在普通测试命令中按设计跳过；真实凭证环境下已单独运行并通过。MCP `initialize`、`tools/list` 和 capability 路由的 stdout 均为合法 JSON。

## 安全与交付边界

- ZIP 不包含 `.env.local`、缓存、`.pyc`、`.claude` 本地设置或任何凭证；
- `.mcp.json` 不再覆盖旧 ModelBest 端点，运行时从 `.env.local` 或显式进程环境读取配置；
- 分发包只包含占位凭证示例 `.env.local.example`；
- Neo4j 运行时查询只读；同步和迁移脚本只会在人工显式执行时写入；
- 未执行网页浏览器测试，遵循本轮“不用网页测试”的要求；API、MCP 和静态 HTML 结构已验证。
