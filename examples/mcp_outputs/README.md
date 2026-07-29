# MCP 真实输出实例（前端联调用）

这里是 **MCP 服务在真实 Neo4j 后端上跑出来的真实返回**，直接拿去做前端 mock / 联调，不用先把后端跑起来。

每个 `.json` 就是前端要渲染的业务数据（即 MCP 返回里的 `structuredContent` 那一层，已经帮你拆出来了）。

> 注意：真到了直连 MCP 联调时，收到的是带 JSON-RPC 信封的完整返回，业务数据在 `result.structuredContent` 里——和这里的 `.json` 内容一致，取那一层即可。

## 场景清单

| 文件 | 工具 | `selection_status` | 用来测什么 UI |
|---|---|---|---|
| `route_pipeline_request.rnaseq.json` | `route_pipeline_request` | `information` | **主力成功态**：有 pipeline 推荐 + 选中的真实数据（双端 FASTQ）。渲染推荐卡片、I/O 槽、数据资产表 |
| `route_pipeline_request.wes_somatic.json` | `route_pipeline_request` | `no_candidate` | **空结果态**：没匹配上，`recommendations`/`candidates` 都空。测"无结果"占位 |

## 主力实例 `route_pipeline_request.rnaseq.json` 长什么样

- 顶层：`schema_version="tool-chain/v2"`、`selection_status`、`recommendations[]`、`candidates[]`、`intent`、`planner_metadata`
- `recommendations[0].tool` —— 选中的 pipeline（`rnaseq_singletask`）及其 `inputs[]`/`outputs[]` 槽
- `recommendations[0].data.assets[]` —— **选中的真实数据**：一对双端测序文件
  `HRR1402797_f1.fastq.gz` / `HRR1402797_r2.fastq.gz`，带 study/sample/run/individual 溯源
- 字段完整语义见仓库 `docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md` 和
  正式 schema `docs/mcp_delivery/schemas/tool_chain_output.schema.json`

## 前端快速加载示例

```js
// 直接 import 结构化层即可渲染
import res from "./examples/mcp_outputs/route_pipeline_request.rnaseq.json";

res.recommendations.forEach(rec => {
  console.log(rec.pipeline_id, rec.tool.name);
  rec.data.assets.forEach(a =>
    console.log("  data:", a.file_name, a.format, a.study_accession));
});
```

## 说明

- 这批 fixture 由 `route_pipeline_request` 在 `FORCE_RULE=1`（确定性规则路由，不依赖 LLM）下生成，
  所以结果稳定、可复现，适合做测试基线。
