# MCP Readiness Report

## 现状盘点

- 入口：`server.py`
- 协议：MCP `2024-11-05`，JSON-RPC 2.0 over stdio
- SDK：未使用第三方 MCP SDK；服务端为依赖无关的同步 stdio 实现
- 服务版本：`1.0.0`
- transport：stdio，一行一个 JSON-RPC message；stdout 仅协议消息，日志走 stderr
- progress：调用方提供 `_meta.progressToken` 时发送 `notifications/progress` 的 started/completed

## Tool 清单

| Tool | 输入重点 | 输出/业务状态 | 调用链 |
|---|---|---|---|
| `route_pipeline_request` | query, top_k, force_custom, data_matcher_mode, include_internal | `tool-chain/v1` | MCP -> WorkflowComposer -> PipelineRouter -> matcher/catalog |
| `list_pipeline_capabilities` | detail, data_matcher_mode | 12 pipeline 摘要或完整合同 | MCP -> Neo4j RegisteredMethodCatalog |
| `list_workflow_methods` | detail, data_matcher_mode | 12 atomic + decomposition | MCP -> Neo4j RegisteredMethodCatalog |
| `validate_tool_chain` | steps | `tool-chain-validation/v1` | MCP -> 原 `_validate_custom_steps` |
| `query_data_availability` | intent + pipeline_ids 或 steps（二选一）, limit | `data-availability/v1` | MCP -> validator -> matcher -> assess_feasibility |
| `health_check` | 无 | `mcp-health/v1` | MCP -> Neo4j read-only health/snapshot/count |
| `render_pipeline_answer` | result | 中文字符串 | MCP -> render_pipeline_answer |

只校验、目录、数据可用性和健康检查均不调用 LLM。`force_custom` 已暴露；调用方可用 `validate_tool_chain` 完全绕过内部 LLM。

## 实测

每个冒烟 case 都新启一个 Python 进程，数字包含冷启动。热进程探测中，Neo4j matcher 已加载后的 route/data match 为 141-146 ms。

| Tool/场景 | 冷启动 ms | 返回字符 |
|---|---:|---:|
| health | 437.8 | - |
| pipeline capabilities | 1,790.2 | - |
| workflow methods | 1,724.5 | - |
| validate-only | 1,837.6 | - |
| data availability | 1,993.3 | - |
| deterministic route | 1,941.4 | - |
| render | 36.3 | - |

完整 detail 曾达到 60-94 KB；现改为 summary 默认，route 默认删除 nested analysis/debug，仍可用 `detail=full` 或 `include_internal=true` 获取。

历史真实 LLM 探测：standard 中位约 10-15 秒；custom 中位 32.8-42.2 秒、最大 61.4 秒。matcher 约 0.17 秒，只占 custom 的约 0.3%-0.6%。MCP 协议不规定统一 tool timeout；具体客户端默认值未从官方文档确认，标为待集成方确认。建议非 LLM 工具 10 秒、standard route 30 秒、custom route 120 秒。

## 错误语义

| 场景 | 表达 |
|---|---|
| 参数非法 | JSON-RPC error `-32602`, `category=invalid_parameters` |
| Neo4j/依赖不可用 | JSON-RPC error `-32001`, `category=dependency_unavailable` |
| 未登记能力 | 成功 tool result, `status=capability_gap` |
| 数据不齐 | 成功 tool result, `not_available`/`missing_assets` |
| LLM 不可用 | 成功业务状态 `no_match`，或依赖异常时 `-32001` |

Agent 应先判断 JSON-RPC `error`，再读 `selection_status/status`，最后检查 `agent_input.feasibility` 和 `workflow_plan.validation`。业务不满足不是协议错误。

## 判断

工具粒度现在可用：agent 可先查目录和数据，再自行规划并只校验，不必让巨型路由工具包办一切。最大残余问题仍是 custom LLM 延迟和 pipeline 目录未全部原子化；progress 能说明仍在运行，但不能消除客户端硬超时。同步 stdio 对当前规模足够，未引入未授权的异步队列。
