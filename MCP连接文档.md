# MCP 连接文档

> 当前接口已经升级为 `tool-chain/v2`。本文件第 4 节之后保留的是历史 v1 示例，不应再用于新接入；正式合同以 `docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md` 和 `docs/mcp_delivery/schemas/tool_chain_output.schema.json` 为准。v2 使用 `recommendations[]` 返回业务 pipeline 与 Neo4j 数据证据，使用 `candidates[]` 返回严格校验后的 atomic 工具链。

本文档说明如何将 **Bio Pipeline KG Matcher** 作为 MCP（Model Context Protocol）服务，接入 Claude、Codex 等支持 MCP 的客户端。

---

## 1. 服务概述

- **协议**：MCP，基于 **JSON-RPC 2.0 over stdio**（标准输入输出）；
- **服务名**：`bio-pipeline-kg-matcher`，版本 `0.2.0`；
- **协议版本**：`2024-11-05`；
- **依赖**：Python 3 与真实 Neo4j 工具目录；LLM 模式额外需要 `requests`。无第三方 MCP 运行时依赖。

服务入口为 `server.py`，通过 stdin 逐行读取 JSON-RPC 请求，通过 stdout 逐行返回响应。

---

## 2. 环境准备

### 2.1 依赖检查

```bash
python3 --version        # 需 Python 3.7+
python3 -c "import requests" 2>/dev/null && echo "requests OK" || echo "如需 LLM 模式请: pip install requests"
```

> `FORCE_RULE=1` 不需要 `requests`，但仍需 Neo4j。自助餐方法编排需要 LLM；标准流程在 LLM 不可用时可规则回退。任何模式都不会回退到 WDL 工具。

### 2.2 环境变量

| 变量 | 说明 | 默认 |
|------|------|------|
| `FORCE_RULE` | `1` 强制规则模式（仅用于显式离线诊断）；`0` 使用 LLM | `server.py` 内默认设为 `0` |
| `LLM_REQUIRED` | `1` 禁止 LLM 失败后规则兜底；`0` 允许标准流程回退 | 默认 `0` |
| `LLM_MODE` | `api`（OpenAI 兼容接口）或 `local`（Ollama） | `api` |
| `LLM_API_KEY` | LLM 接口密钥 | 无 |
| `LLM_BASE_URL` | LLM 接口地址 | `https://api.deepseek.com/chat/completions` |
| `LLM_MODEL` | 模型名 | `deepseek-v4-pro` |
| `LLM_TIMEOUT` | LLM 请求超时（秒） | `60` |
| `NEO4J_URI` | Neo4j Bolt 地址 | `bolt://127.0.0.1:7687` |
| `NEO4J_USER` | Neo4j 用户 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | 无 |
| `NEO4J_DATABASE` | Neo4j 数据库 | `neo4j` |
| `ROUTER_NL_SUMMARY` | `0` 关闭 `selection_summary` 的 LLM 生成，改用确定性模板句 | 开启（LLM 模式下） |
| `OLLAMA_URL` | 本地 Ollama 地址（`LLM_MODE=local` 时） | `http://localhost:11434/api/generate` |
| `LOCAL_MODEL` | 本地模型名 | `qwen2.5:7b` |

> **安全**：密钥只通过环境变量注入，切勿写入代码或提交到版本库。

---

## 3. 客户端接入配置

### 3.1 Claude Code / Claude Desktop

在 MCP 配置文件中添加以下条目（Claude Code 为项目根的 `.mcp.json`，Claude Desktop 为 `claude_desktop_config.json`）：

**规则模式（仅关闭 LLM，Neo4j 仍必需）：**

```json
{
  "mcpServers": {
    "bio-pipeline-kg-matcher": {
      "command": "python3",
      "args": ["/绝对路径/bio-pipeline-kg-matcher/server.py"],
      "env": {
        "FORCE_RULE": "1",
        "LLM_REQUIRED": "0"
      }
    }
  }
}
```

**LLM 增强模式：**

```json
{
  "mcpServers": {
    "bio-pipeline-kg-matcher": {
      "command": "python3",
      "args": ["/绝对路径/bio-pipeline-kg-matcher/server.py"],
      "env": {
        "FORCE_RULE": "0",
        "LLM_REQUIRED": "0",
        "LLM_MODE": "api",
        "LLM_BASE_URL": "https://api.deepseek.com/chat/completions",
        "LLM_MODEL": "deepseek-v4-pro",
        "LLM_TIMEOUT": "60"
      }
    }
  }
}
```

> 本仓库已附带一份无密钥的 `.mcp.json` 示例，使用 `${CWD}/server.py` 相对当前工作目录定位。轮换后的 `LLM_API_KEY` 与 `NEO4J_PASSWORD` 放在项目根目录 `.env.local`，不要写入 MCP 配置。正式接入时建议把 `server.py` 改为绝对路径以避免歧义。

### 3.2 Codex

Codex 使用仓库内的 `.mcp.json`。确认 `args` 中的路径能正确解析到 `server.py`，并按需设置 `env` 内的运行模式与凭证即可。

### 3.3 通用客户端

任何支持"启动子进程 + stdio 通信"的 MCP 客户端均可接入，核心三要素：

- **command**：`python3`
- **args**：`["<server.py 的绝对路径>"]`
- **env**：按上表设置运行模式

---

## 4. 提供的工具（Tools）

服务通过 `tools/list` 暴露以下四个工具。

### 4.1 `route_pipeline_request`

先判断需求属于标准 pipeline 组合（预制菜）还是方法级定制（自助餐），再匹配本地 KG 数据候选。**核心工具**。

**入参：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | 是 | 自然语言需求描述 |
| `top_k` | integer | 否 | 返回标准流程数上限，范围 1–14，默认 5 |

**返回**：顶层遵循 `tool-chain/v1`，必含 `schema_version`、`selection_status`、`intent`、`agent_input`。`agent_input.tool_chain[].inputs` 通过 `asset_id` 或 `from.step_id/from.output` 表达依赖；扩展字段 `workflow_mode` 和 `workflow_plan` 给出预制菜/自助餐的解释、质量门禁和调试信息。

`standard` 中每个 pipeline 都附带 Neo4j `HAS_STEP` 锁定步骤；未拆解的 pipeline 显示为一个 pipeline 级 Neo4j tool。`custom` 只能使用 Neo4j atomic tool 与校正后的 NEXT，`agent_input.pipeline_id=null`；本服务不判断执行参数是否齐全。`capability` 用于“能做什么/有哪些流程或工具”等非执行问答，直接返回 Neo4j 目录，`tool_chain=[]` 且不进行数据可行性判断。

#### 4.1.1 `agent_input` —— 面向执行接口的输入

系统按 agent 端 `tool-chain/v1` 契约装配资产和步骤依赖：

| 字段 | 说明 |
|------|------|
| `execution_kind` | 固定为 `tool_chain` |
| `workflow_mode` | `standard`（预制菜）或 `custom`（自助餐） |
| `match_id` | 本次选择的稳定标识 |
| `study_accession` | 匹配队列；无法确定时为 `null` |
| `assets` | 已匹配资产；每项包含 `asset_id`、`role`、`path`、`format` |
| `tool_chain` | 正式工具调用；每项包含唯一 `step_id`、Neo4j 登记的 `tool_id` 和 `inputs` |
| `feasibility` | 只表示用户样本数据是否齐全，包含 `status`、`missing_assets` 和 `data_ready`；不包含运行参数或执行端托管的 GTF/参考索引 |
| `selection_reason` | 为什么选择这条工具链 |
| `extensions` | 质量门禁、规划/契约校验等扩展信息 |

工具输入来自资产：

```json
{
  "count_tsv": {"asset_id": "HRA00XXXX-counts"}
}
```

工具输入来自上游正式输出：

```json
{
  "logcpm_tsv": {
    "from": {"step_id": "preprocess", "output": "normalized_logcpm_tsv"}
  }
}
```

`selection_status` 除契约给出的 `ready`、`missing_assets`、`no_match` 外，扩展支持 `draft`（自助餐待物化）与 `information`（能力目录问答）；`requires_review` 仅为旧调用端兼容值。质量风险继续返回，但不阻断编排。完整说明见 `docs/agent_tool_chain_contract.md`。

### 4.2 `list_pipeline_capabilities`

列出 Neo4j 中全部可用标准流程、slot 与锁定步骤。**无入参。**

### 4.3 `list_workflow_methods`

返回 Neo4j 中的统一工具目录：12 个 atomic tool、11 个完整 pipeline tool 和 1 个 task pipeline，以及校正后的 NEXT 与 `HAS_STEP` recipe。旧 WDL task 不进入运行时目录。**无入参。**

### 4.4 `render_pipeline_answer`

将一次路由结果渲染为适合组会 / 用户阅读的中文摘要。

**入参：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `result` | object | 是 | `route_pipeline_request` 返回的 `result` 对象 |

---

## 5. 验证与调试

### 5.1 用管道手动验证

可以直接通过 stdio 发送 JSON-RPC 请求验证服务是否正常。以下命令依次发送 `initialize` 和一次工具调用：

```bash
cd /绝对路径/bio-pipeline-kg-matcher
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"route_pipeline_request","arguments":{"query":"我有食管癌的MAF文件，想做肿瘤突变负荷生存分析","top_k":3}}}' \
  | FORCE_RULE=1 python3 server.py
```

预期：每行输入对应一行 JSON 响应，第三条返回推荐的 `tmb_survival_analysis` 流程及数据候选，`agent_input.feasibility.ok` 反映数据是否齐全。

> **生产模式提示**：设 `FORCE_RULE=0` 并配好 `LLM_*` 后，意图提取走 LLM（`intent.source="llm"`），`selection_summary` 也由 LLM 生成；`FORCE_RULE=1` 时二者均走确定性规则/模板，便于离线复现。

### 5.2 JSON-RPC 消息示例

**初始化：**

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
```

响应：

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"bio-pipeline-kg-matcher","version":"0.2.0"}}}
```

**调用工具：**

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"route_pipeline_request","arguments":{"query":"...","top_k":5}}}
```

### 5.3 常见问题

| 现象 | 排查方向 |
|------|---------|
| 客户端连不上 | 确认 `command`/`args` 路径正确，`python3` 在 PATH 中 |
| 一直走规则模式 | 检查外部环境是否显式设置了 `FORCE_RULE=1`；`server.py` 默认值为 `0` |
| LLM 未生效 | 查看进程 stderr 的 `[LLM]` 日志，确认 `api_key`/`base_url` 是否缺失、HTTP 状态码是否 200 |
| 返回 `no_pipeline` | 需求超出 Neo4j 标准 pipeline 与 atomic tool 闭集，或未形成合法链路 |
| 数据候选为空 | 目标数据不在本地 CSV 覆盖范围内 |
| `feasibility.ok=false` | 匹配到的文件未覆盖流程必需角色（如生存分析缺 clinical），按 `message` 补数据后重试——这是设计内的拦截，不是故障 |

> LLM 调用会在标准错误输出打印 `[LLM]` 前缀的诊断日志（含脱敏后的密钥、模型名、状态码、失败原因），便于排查。

---

## 6. 协议方法支持一览

| 方法 | 支持 | 说明 |
|------|------|------|
| `initialize` | ✅ | 返回协议版本与服务信息 |
| `notifications/initialized` | ✅ | 通知，无响应 |
| `ping` | ✅ | 返回空结果 |
| `tools/list` | ✅ | 列出四个工具及其 inputSchema |
| `tools/call` | ✅ | 调用指定工具 |
| 其他方法 | ❌ | 返回 `-32601 Unknown method` |
