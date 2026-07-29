# MCP 真实输出实例（前端联调用）

这里是 **MCP 服务在真实 Neo4j 后端上跑出来的真实返回**，直接拿去做前端 mock / 联调，不用先把后端跑起来。

每个 `.json` 就是前端要渲染的业务数据（即 MCP 返回里的 `structuredContent` 那一层，已经帮你拆出来了）。

> 注意：真到了直连 MCP 联调时，收到的是带 JSON-RPC 信封的完整返回，业务数据在 `result.structuredContent` 里——和这里的 `.json` 内容一致，取那一层即可。

## 场景清单（3 种 UI 状态）

| 文件 | `selection_status` | 用来测什么 UI |
|---|---|---|
| `route_pipeline_request.rnaseq.json` | `information` | **成功态·单样本**：`rnaseq_singletask` 流程 + 选中一对双端 FASTQ（`matched_count=2`）。渲染推荐卡片、I/O 槽、数据资产表 |
| `route_pipeline_request.wes_somatic.json` | `information` | **成功态·配对**：`wes_somatic_pair` 流程 + 选中肿瘤/正常配对的 4 个 FASTQ（`matched_count=4`）。测多资产/配对样本的渲染 |
| `route_pipeline_request.survival_unsupported.json` | `unsupported` | **能力边界态**：生存分析尚未原子化，`recommendations`/`candidates` 都空，`unsupported_reason` 有中文原因。测"暂不支持"提示 |

> 三个都是**真实 LLM 路由 + 真实 Neo4j 数据匹配**跑出来的快照。

## 主力实例 `route_pipeline_request.rnaseq.json` 长什么样

- 顶层：`schema_version="tool-chain/v2"`、`selection_status`、`recommendations[]`、`candidates[]`、`intent`、`planner_metadata`
- `recommendations[0].tool` —— 选中的 pipeline（`rnaseq_singletask`）及其 `inputs[]`/`outputs[]` 槽
- `recommendations[0].data.assets[]` —— **选中的真实数据**：双端测序文件，带 study/sample/run/individual 溯源
- `unsupported` 态则 `recommendations=[]`，只读 `unsupported_reason`（见 survival 那个文件）
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

- 这批 fixture 由 `route_pipeline_request` 走**真实 LLM 路由 + 真实 Neo4j 数据匹配**生成，是某次真实调用的快照。
- 数据匹配部分是确定性的；路由（选哪个 pipeline）由 LLM 生成，换一次调用措辞可能略有不同，但这三个文件已是**校验过 `selection_status` 的稳定快照**，适合直接做前端基线。
