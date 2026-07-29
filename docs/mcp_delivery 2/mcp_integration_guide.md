# Bio Pipeline MCP Integration Guide

## 能力边界

本 MCP 把自然语言或结构化请求转换为生信工具链合同，并从统一 Neo4j 图中匹配数据。它只做目录查询、流程选择/组链、合同校验和数据可用性判断，**不执行 FASTQ、BAM、VCF、表达矩阵或任何生信分析**。

custom 只能使用目录登记的 12 个 atomic tool、精确具名槽和 NEXT 边。未拆解的方法会诚实阻断。参考基因组、GTF、索引和 WES `interval_list` 由执行端托管，不是本服务的数据资产。

## 从零启动

1. 按 `datagraph_restore_guide.md` 恢复 `neo4j/datagraph-staging.dump`。
2. 创建 Python 3.10+ venv。
3. 安装依赖：

```bash
python -m venv .venv
.venv/bin/pip install -r app/requirements-neo4j.txt -r app/requirements-llm.txt
```

4. 根据 `.env.example` 配置环境变量。`NEO4J_PASSWORD` 必需；LLM key 可选。
5. 启动 stdio 服务：

```bash
set -a; . ./.env; set +a
.venv/bin/python app/server.py
```

stdio 服务没有 HTTP 端口。验证存活应通过 MCP `initialize`、`ping` 或 `health_check`，不要等待终端提示符。

## 无 LLM 时

`health_check`、两个目录工具、`query_data_availability` 和 `validate_tool_chain` 完全不需要 LLM。`route_pipeline_request` 的确定性标准流程仍可工作；需要新 custom 规划时会 fail closed。对方 agent 已自带模型时，推荐：

1. `list_workflow_methods`
2. agent 自己生成 steps
3. `validate_tool_chain`
4. `query_data_availability`，把同一组已验证 `steps` 原样传入

这条路径绕开 30-60 秒的内部两阶段 LLM。

## Tools

### `health_check`

无入参。只有 `ready=true`、`snapshot_id=dg-b23135d49c950d0846a563bc`、`tool_count=24` 时才继续。

### `list_pipeline_capabilities`

列 12 个 pipeline-level 能力。`detail=summary|full`，默认 summary。未登记 HAS_STEP 的 pipeline 仍是一个不可拆的 pipeline tool。

### `list_workflow_methods`

列 atomic 闭集、精确 input/output 名和 decomposition status。agent 生成链时必须逐字使用这些名称。

### `validate_tool_chain`

入参 `steps`。返回 `valid`、原校验器的 errors/warnings、规范化 steps。它不调用 LLM、不匹配数据、不执行工具。

### `query_data_availability`

入参 `intent`，并且必须在 `pipeline_ids` 和 `steps` 中二选一；可选 `limit`、`data_matcher_mode`、`include_backup_candidates`。返回 cohort/file/combination 和 feasibility。

- `pipeline_ids` 保留原接口行为，只接受已登记的 pipeline-level ID。
- `steps` 先经过与 `validate_tool_chain` 相同的严格校验，再从正式 input 槽推导所需资产角色。非法链返回 JSON-RPC `-32602`；合法但没有满足数据时返回 `status=not_available`。
- 不要同时传 `pipeline_ids` 和 `steps`，也不要两者都不传。

### `route_pipeline_request`

入参：`query` 必需；`top_k=1..14`；`force_custom`；`expand_standard_steps`；`data_matcher_mode=csv|compare|neo4j`；`include_internal`。交付默认 Neo4j。Neo4j 异常不回退 CSV。

`expand_standard_steps` 默认 `true`。`rnaseq_singletask` 有锁定的 7 步 HAS_STEP recipe，因此 `agent_input.tool_chain` 默认返回 atomic steps，每步标记 `decomposition_status=expanded_locked_recipe`；传 `false` 可取旧的单 pipeline 节点形状。其余 11 个流程没有 recipe，仍返回单 pipeline 节点，并通过结构化字段 `decomposition_status=pipeline_level_unexpanded`、`expandable=false` 明示未拆解，系统不会猜内部步骤。

### 槽、配对和变体语义

- FASTQ 资产携带 `mate=r1|r2`；配对样本同时携带 `sample_role=tumor|normal`、individual/sample/run 标识。执行端必须保留这些字段，不得按数组位置推断。
- paired fastp 使用 `raw_fastq_read_r1`、`raw_fastq_read_r2`，输出 `clean_fastq_read_r1`、`clean_fastq_read_r2`；BWA 对应消费 `clean_fastq_read_r1`、`clean_fastq_read_r2`。
- SAMtools 除 `sorted_dedup_bam` 外还输出 `bai`。paired GATK 必须完整绑定 `tumor_bam`、`tumor_bai`、`normal_bam`、`normal_bai`；缺任一项均失败关闭。
- fastp 变体为 `single_end` 或 `paired_end`；GATK 变体为 `single` 或 `paired`。校验器从已绑定槽唯一推导变体；缺槽、混用变体或无法唯一判断时拒绝。
- 兼容期仍保留 legacy generic fastp/BWA 槽和 GATK `sorted_dedup_bam` 单样本槽；新配对链应使用上述具名槽。

### MultiQC

MultiQC 现在是可见 atomic step。`rnaseq_singletask` 的锁定 recipe 以 MultiQC 结束；custom 规划也可在存在登记 NEXT 的情况下追加它。上游到 MultiQC 是 order-only `depends_on`，当前不声称消费尚未登记的报告输出。不要假设执行端会在链外自动运行 MultiQC，也不要因为它可选就把 `steps`/`match_id` 当稳定字段。

### `render_pipeline_answer`

把历史路由结果渲染为中文；agent 集成通常不需要。

## 返回值判断顺序

1. JSON-RPC 是否有 `error`。`-32602` 是调用参数；`-32001` 是 Neo4j/依赖问题，禁止执行。
2. `selection_status/status`。`no_match`、`capability_gap`、`not_available` 均不可执行。
3. `workflow_plan.validation.ok` 和 `execution_status`。blocked 时不可执行。
4. `agent_input.feasibility.status`/`missing_assets`。数据不齐时先补数据。
5. 仅 `ready` 或明确允许的 custom `draft` 才交给执行端物化；本 MCP 从不替执行端运行工具。

## Timeout 与体积

MCP 协议没有统一客户端 timeout。请在接入方确认其默认值。建议：目录/健康/校验/数据查询 10 秒，standard route 30 秒，custom route 120 秒。传 `_meta.progressToken` 可接收 started/completed，但客户端硬超时仍会终止调用。

summary 返回实测 0.1-16 KB；`detail=full`/`include_internal=true` 可到 60-94 KB。常规 agent 调用不要开启 full。

## 数据范围

当前 `scope=t1`，T1 13,772、T2 86。HRA000122 的 696 条 FASTQ 和 HRA000021 的 T11-only BAM 不在范围内；权威全集由数据负责人待确认。图中记录 1,269 条悬空外键，matcher 按属性值而非不完整拓扑匹配。

## 排查

- health `ready=false`: 核对 URI/database/password/snapshot，先跑统一图验证。
- route `-32001`: Neo4j 或 matcher 初始化失败；Neo4j 模式不会回退。
- custom `no_match`: 查 validation/decomposition gap，不要绕过闭集。
- `missing_assets/not_available`: 这是业务结果，不是服务故障。
- 调用超时但 progress 已 started: 增大客户端 tool timeout，或改用 validate-only 路径。

验证命令：

```bash
.venv/bin/python scripts/python/mcp_smoke_test.py
.venv/bin/python scripts/python/mcp_smoke_test.py --offline --cassette mcp_smoke_cassette.json
```

## 已知限制

- 只有 `rnaseq_singletask` 有锁定的多步 HAS_STEP recipe；其余 pipeline 是不可拆的 pipeline-level tool。
- custom LLM 的输出仍可能因模型波动而变化，合同校验是最终门禁。
- MultiQC 可能被模型合法追加，因此调用方应以合同校验和核心数据绑定为准，不依赖 custom step 数量或 `match_id` 恒定。
