# MCP 连接与运行指南（基于 Neo4j）

> 本文面向 **agent 端同门**：从 GitHub clone 本仓库后，如何在本机跑起一个**基于 Neo4j** 的完整
> MCP 服务，并把它接入你的 agent 客户端。全流程走 Neo4j 后端，不使用 CSV 兜底模式。
>
> 配套文档：
> - 恢复细节：[`docs/mcp_delivery/datagraph_restore_guide.md`](mcp_delivery/datagraph_restore_guide.md)
> - 返回值契约（tool-chain/v2）：[`docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md`](mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md)

---

## 0. 架构一图流

```
┌────────────┐   MCP (JSON-RPC 2.0 / stdio)   ┌─────────────────────┐   Bolt    ┌───────────────────────┐
│  你的 Agent │ ─────────────────────────────▶ │  server.py (本仓库)  │ ────────▶ │ Neo4j 2026.06.0        │
│  (客户端)   │ ◀───────────────────────────── │  MCP 编排/数据匹配   │ ◀──────── │ database: datagraph-  │
└────────────┘        7 个 tools               └─────────────────────┘           │ staging (由 dump 恢复) │
                                                                                   └───────────────────────┘
```

- **MCP 只做流程编排 + 数据匹配，不执行生信任务。**
- 数据后端 = Neo4j 里的统一图 `datagraph-staging`（本仓库自带 dump，可本地一键恢复）。
- 工具目录（24 个 atomic 工具 + pipeline 工具）随图一起在 Neo4j 中。

---

## 1. 前置条件

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.9+ | 跑 `server.py` |
| Neo4j Community | **2026.06.0** | 必须与 dump 创建版本一致，否则 `database load` 可能不兼容 |
| Java | 21 | Neo4j 2026.06.0 运行时依赖 |
| git | 任意 | clone 仓库（仓库含 90MB dump，clone 会稍慢） |

Neo4j 下载：https://neo4j.com/deployment-center/ （选 Community 2026.06.0）。

---

## 2. 获取代码

```bash
git clone <本仓库的 GitHub 地址>
cd bio-pipeline-kg-matcher
```

仓库自带后端 dump：`docs/mcp_delivery/neo4j/datagraph-staging.dump`
（SHA-256 `07572b120251d549062890c29e64a3f9ac2f5ea95dc5d0c517ec3a768c8017a9`）。

---

## 3. 安装 Python 依赖

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-neo4j.txt   # neo4j 驱动（必装）
pip install -r requirements-llm.txt      # requests，走 LLM 路由时才需要（可选）
```

> `route_pipeline_request` 默认会调用一次 LLM 做路由；**没有 LLM key 也能跑**（自动回退到
> 规则路由）。其余 6 个工具完全不依赖 LLM。想要更准的 pipeline 推荐再配 `LLM_API_KEY`。

---

## 4. 恢复 Neo4j 后端（主路径）

> 目标：把 `datagraph-staging.dump` 恢复进一个**全新的** Neo4j home，数据库名必须是
> `datagraph-staging`（与 dump 文件名一致，否则报 `No matching archives`）。

### 4.1 校验 dump

```bash
shasum -a 256 docs/mcp_delivery/neo4j/datagraph-staging.dump
# 必须等于 07572b120251d549062890c29e64a3f9ac2f5ea95dc5d0c517ec3a768c8017a9
```

### 4.2 准备全新 home 的 conf

在新 Neo4j home 的 `conf/neo4j.conf` 中至少设置：

```properties
initial.dbms.default_database=datagraph-staging
server.default_listen_address=127.0.0.1
server.bolt.listen_address=127.0.0.1:7687
server.http.listen_address=127.0.0.1:7474
dbms.security.auth_enabled=true
```

### 4.3 设初始密码（首次启动前）

```bash
NEO4J_HOME=/path/to/new-home NEO4J_CONF=/path/to/new-home/conf \
  /path/to/neo4j/bin/neo4j-admin dbms set-initial-password 'replace-me'
```

### 4.4 载入 dump（数据库名必须为 datagraph-staging）

```bash
NEO4J_HOME=/path/to/new-home NEO4J_CONF=/path/to/new-home/conf \
  /path/to/neo4j/bin/neo4j-admin database load datagraph-staging \
  --from-path="$(pwd)/docs/mcp_delivery/neo4j" \
  --overwrite-destination=true
```

> `--overwrite-destination` 只对确认过的**全新** home 使用。

### 4.5 启动 Neo4j

```bash
NEO4J_HOME=/path/to/new-home NEO4J_CONF=/path/to/new-home/conf \
  /path/to/neo4j/bin/neo4j console
```

启动后 Bolt 应监听 `bolt://127.0.0.1:7687`。

---

## 5. 配置 `.env.local`

在仓库根目录复制模板并填写：

```bash
cp .env.local.example .env.local
```

`.env.local` 关键项（**指向你刚恢复的库**）：

```ini
# —— Neo4j 后端 ——
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=replace-me          # 4.3 里设的密码
NEO4J_DATABASE=datagraph-staging   # ★ 恢复 dump 时用这个库名，别写成 neo4j

# —— 运行模式 ——
DATA_MATCHER_MODE=neo4j            # 走 Neo4j，不用 CSV
DATAGRAPH_SCHEMA_MODE=auto         # 自动识别 managed / legacy 两种 schema
DATAGRAPH_SNAPSHOT_ID=dg-b23135d49c950d0846a563bc   # datagraph-staging 的快照 ID

# —— LLM（可选，不填则规则路由）——
# LLM_API_KEY=sk-...
# LLM_BASE_URL=https://api.deepseek.com/chat/completions
# LLM_MODEL=deepseek-v4-flash
LLM_REQUIRED=0
```

> `.env.local` 已被 `.gitignore` 排除，不会误传到 GitHub；里面的 key/密码不会外泄。

---

## 6. 启动并自检 MCP

### 6.1 单独跑一次 health_check（最快确认后端连通）

```bash
source .venv/bin/activate
printf '%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"health_check","arguments":{}}}' \
  | python3 server.py
```

`health_check` 返回里应看到（关键字段）：

```json
{
  "connected": true,
  "version": "2026.06.0",
  "database": "datagraph-staging",
  "snapshot_id": "dg-b23135d49c950d0846a563bc",
  "datagraph_node_count": 32744,
  "tool_count": 24,
  "ready": true
}
```

`ready: true` = 后端合同校验通过，可以正式接 agent。

### 6.2 完整统一图验证（可选，九项 PASS）

```bash
export RESTORE_NEO4J_PASSWORD='replace-me'
python scripts/python/verify_unified_graph.py \
  --expectations config/unified_graph_expectations.json \
  --uri bolt://127.0.0.1:7687 --database datagraph-staging \
  --user neo4j --password-env RESTORE_NEO4J_PASSWORD \
  --output restore_unified_graph_verification.json
```

预期：数据图 32,744 节点 / 73,001 关系，工具目录 233 节点 / 601 关系，跨域关系 0。

---

## 7. 接入 Agent 客户端

MCP 走 **stdio + JSON-RPC 2.0**，启动命令统一是 `python3 server.py`（在仓库根目录、且已
`source .venv/bin/activate` 或用绝对 python 路径）。

### 7.1 Claude Code / 支持 `.mcp.json` 的客户端

仓库根目录已带 [`.mcp.json`](../.mcp.json)：

```json
{
  "mcpServers": {
    "bio-pipeline-kg-matcher": {
      "command": "python3",
      "args": ["${CWD}/server.py"],
      "env": { "DATA_MATCHER_MODE": "neo4j", "FORCE_RULE": "0", "LLM_REQUIRED": "0" }
    }
  }
}
```

在仓库根目录启动 Claude Code 即可自动加载；`.env.local` 里的 `NEO4J_*` 会被 `server.py` 读入。

### 7.2 Claude Desktop

编辑 `claude_desktop_config.json`（macOS 在
`~/Library/Application Support/Claude/`），加入：

```json
{
  "mcpServers": {
    "bio-pipeline-kg-matcher": {
      "command": "/绝对路径/bio-pipeline-kg-matcher/.venv/bin/python3",
      "args": ["/绝对路径/bio-pipeline-kg-matcher/server.py"],
      "env": {
        "DATA_MATCHER_MODE": "neo4j",
        "NEO4J_URI": "bolt://127.0.0.1:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "replace-me",
        "NEO4J_DATABASE": "datagraph-staging",
        "DATAGRAPH_SNAPSHOT_ID": "dg-b23135d49c950d0846a563bc"
      }
    }
  }
}
```

> Claude Desktop 不读 `.env.local`，所以 `NEO4J_*` 要直接写进 `env`。重启 Claude Desktop 生效。

### 7.3 通用 MCP stdio 客户端 / 自研 agent

握手顺序：`initialize` → （可选 `notifications/initialized`）→ `tools/list` → `tools/call`。
每行一个 JSON。返回值同时出现在 `result.structuredContent` 和 `result.content[0].text`，
**优先读结构化值**。

### 7.4 Python 直连示例

```python
import json, subprocess, sys
p = subprocess.Popen([sys.executable, "server.py"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
def call(obj):
    p.stdin.write(json.dumps(obj) + "\n"); p.stdin.flush()
    return json.loads(p.stdout.readline())

call({"jsonrpc":"2.0","id":1,"method":"initialize",
      "params":{"protocolVersion":"2024-11-05","capabilities":{},
                "clientInfo":{"name":"demo","version":"0"}}})
print(call({"jsonrpc":"2.0","id":2,"method":"tools/call",
      "params":{"name":"route_pipeline_request",
                "arguments":{"query":"双端 RNA-seq FASTQ 生成表达丰度和 count 矩阵",
                             "top_k":3,"data_matcher_mode":"neo4j"}}}))
```

---

## 8. 七个工具速查

| 工具 | 作用 | 是否调用 LLM | 关键参数 |
|---|---|---|---|
| `route_pipeline_request` | 规划（不执行）：给 1-3 条业务 pipeline 推荐 + 已验证原子链 | 一次 | `query`（必填）, `top_k` 1-3 |
| `query_data_availability` | 匹配 cohort / 文件 / 完整数据组合 | 否 | `intent`（必填）+ `pipeline_ids` 或 `steps` 二选一 |
| `validate_tool_chain` | 校验原子链是否满足闭集/槽位/NEXT/资产合同 | 否 | `steps`（必填） |
| `list_pipeline_capabilities` | 列 pipeline 级能力与 I/O 槽 | 否 | `detail` summary/full |
| `list_workflow_methods` | 列 Neo4j 闭集工具目录（原子 + pipeline） | 否 | `detail` summary/full |
| `health_check` | 检查 Neo4j 连通 + 统一图快照/计数/24 工具合同 | 否 | 无 |
| `render_pipeline_answer` | 把一次路由结果渲染成中文摘要 | 否 | `result`（必填） |

> 返回值 `tool-chain/v2` 的完整字段含义、`ready` 语义、配对 WES 规则、无结果分支等，见
> [`MCP_AGENT_INTEGRATION_ZH.md`](mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md)。每次调用可传
> `data_matcher_mode` 覆盖后端；本指南统一用 `neo4j`。

---

## 9. 备选：连接师姐的远程服务器（生产路径）

如果不想本地恢复 dump，而是直接连师姐已经部署好的 Neo4j 服务器：

```ini
# .env.local
NEO4J_URI=bolt://<她的服务器地址>:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<她给的口令>
NEO4J_DATABASE=<她的数据库名>      # 常见是 neo4j；以她实际为准
DATA_MATCHER_MODE=neo4j
DATAGRAPH_SCHEMA_MODE=auto         # ★ 自动识别大小写标签(Project/project…)，两种导入都能读
```

> `DATAGRAPH_SCHEMA_MODE=auto` 已做过大小写标签自适配和计数容差：无论她的库是大写标签
> (`Project/Study/…`) 还是小写标签 (`project/study/…`)、节点数是否与契约完全一致，MCP 都能
> 读入并给出告警而不崩溃。先跑一次 `health_check` 确认 `connected: true` 再接 agent。

---

## 10. 常见问题排查

| 现象 | 原因 / 处理 |
|---|---|
| `health_check: connected=false, error=connection_timeout` | Neo4j 没起 / URI 端口错 / 防火墙。先 `nc -z 127.0.0.1 7687`。 |
| `No matching archives` | `database load` 的库名必须是 `datagraph-staging`，且 `--from-path` 指到含 dump 的目录。 |
| `database is in use` | dump/load 要在目标实例**停止**时执行。 |
| `authentication_failed` | 初始密码要在新实例**第一次启动前** `set-initial-password`；`.env.local` 密码要一致。 |
| `Neo4j data matcher is not configured` | `.env.local` 缺 `NEO4J_URI` / `NEO4J_DATABASE` / `NEO4J_PASSWORD` 其一。 |
| `ready=false` 但 connected=true | 快照/库/计数不符合合同：确认 `NEO4J_DATABASE=datagraph-staging`、`DATAGRAPH_SNAPSHOT_ID=dg-b23135…`。 |
| `unsupported_reason` 非空 / `selection_status=unsupported` | 需求依赖尚未原子化的能力（差异表达、GO/KEGG、WGCNA、生存分析等），属正常返回，不是报错。 |
| clone 很慢 | 仓库含 90MB Neo4j dump，属正常。 |

---

## 11. 参考文档

- [`docs/mcp_delivery/datagraph_restore_guide.md`](mcp_delivery/datagraph_restore_guide.md) — 恢复细节与九项验证
- [`docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md`](mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md) — tool-chain/v2 返回契约
- [`docs/mcp_delivery/PACKAGE_MANIFEST.md`](mcp_delivery/PACKAGE_MANIFEST.md) — 交付物清单与哈希
- [`config/unified_graph_expectations.json`](../config/unified_graph_expectations.json) — 快照/计数期望值
