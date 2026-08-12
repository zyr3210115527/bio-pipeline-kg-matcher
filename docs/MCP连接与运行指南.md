# MCP 连接与运行指南（基于 Neo4j）

> 本文面向 **agent 端同门**：从 GitHub clone 本仓库后，如何在本机跑起一个**基于 Neo4j** 的完整
> MCP 服务，并把它接入你的 agent 客户端。全流程走 Neo4j 后端，不使用 CSV 兜底模式。
>
> **2026-08-12 起数据后端换成 0812 图谱。** 有两条路，任选其一：
>
> - **连组内共享服务器**（最省事，不用装 Neo4j）：`bolt://192.168.130.24:7690`，
>   浏览器 `http://192.168.130.24:7480`，账号密码找组内要。这台已经是 0812 图，
>   跳过第 4 节直接配第 5 节即可。
> - **本机自建**：`data/0812/` 的 31 个 CSV 经 `scripts/python/import_0812.py` 重建，
>   约 17 秒，见第 4 节。
>
> 不再随包提供 dump：它是同一份数据的第二个副本，必然漂移（旧的那份停在 7 月 30 日），
> 且新图 352,245 条关系导出后有 134 MiB，超过 GitHub 单文件 100 MiB 上限。
> 落地细节与偏离项见 [`docs/图谱变更说明_0812_落地记录.md`](图谱变更说明_0812_落地记录.md)。
>
> 配套文档：
> - 返回值契约（tool-chain/v2）：[`docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md`](mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md)

---

## 0. 架构一图流

```
┌────────────┐   MCP (JSON-RPC 2.0 / stdio)   ┌─────────────────────┐   Bolt    ┌───────────────────────┐
│  你的 Agent │ ─────────────────────────────▶ │  server.py (本仓库)  │ ────────▶ │ Neo4j 2026.06.0        │
│  (客户端)   │ ◀───────────────────────────── │  MCP 编排/数据匹配   │ ◀──────── │ database: neo4j        │
└────────────┘        7 个 tools               └─────────────────────┘           │ (由 data/0812 导入)     │
                                                                                   └───────────────────────┘
```

- **MCP 只做流程编排 + 数据匹配，不执行生信任务。**
- 数据后端 = Neo4j 里的 0812 图谱，80,295 节点，与数据提供方的实例逐项一致。
- 工具目录不在图里：图只有她的 51 个 `tool` 节点，槽位模型由运行时从 `data/csv/catalog/` 合并。

---

## 1. 前置条件

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | 3.9+ | 跑 `server.py` |
| Neo4j Community | **2026.06.0** | 只有本机自建才需要；连共享服务器可跳过 |
| Java | 21 | 同上，Neo4j 2026.06.0 运行时依赖 |
| git | 任意 | clone 仓库（含 62MB CSV，clone 会稍慢） |

Neo4j 下载：https://neo4j.com/deployment-center/ （选 Community 2026.06.0）。

---

## 2. 获取代码

```bash
git clone <本仓库的 GitHub 地址>
cd bio-pipeline-kg-matcher
```

后端数据在仓库里：`data/0812/`（0812 交付的 entities / reference / relations CSV）
和 `data/csv/catalog/`（我方工具目录 slot 模型）。

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

## 4. 导入 Neo4j 后端（主路径）

> 目标：在一个 Neo4j 2026.06.0 实例的 `neo4j` 库里建出 0812 图。工具目录不进图。
> 这一步会**清空目标库**，只对确认过的本地实例执行。

### 4.1 准备 conf

```properties
server.default_listen_address=127.0.0.1
server.bolt.listen_address=127.0.0.1:7687
server.http.listen_address=127.0.0.1:7474
server.directories.import=import
dbms.security.auth_enabled=true
```

### 4.2 设初始密码并启动

```bash
NEO4J_HOME=/path/to/neo4j NEO4J_CONF=/path/to/neo4j/conf \
  /path/to/neo4j/bin/neo4j-admin dbms set-initial-password 'replace-me'
NEO4J_HOME=/path/to/neo4j NEO4J_CONF=/path/to/neo4j/conf \
  /path/to/neo4j/bin/neo4j console
```

### 4.3 取目标库的 database id

导入器要求显式确认库 ID，防止误清生产库：

```bash
# 在 Neo4j Browser 或 cypher-shell 执行
CALL db.info() YIELD id RETURN id;
```

### 4.4 导入

```bash
export NEO4J_PW='replace-me'
python3 scripts/python/import_0812.py --project-root . \
  --neo4j-import-dir /path/to/neo4j/import \
  --uri bolt://127.0.0.1:7687 --user neo4j --password-env NEO4J_PW \
  --database neo4j --expected-database-id <4.3 拿到的 id> --confirm-clear
```

导入器会自己把 CSV 同步进 `import/` 目录、批量清库、建约束和索引、跑 0812 的
`01`–`04`，最后打印节点与关系计数。期望值：

```
80,293 节点 / 352,252 关系   （与 config/senior_0812_reference_counts.json 逐项一致）
```

> 0811 时代这里还有一步「生成样本级 specimen 旁路表」：那版 sample 表没有
> tumor/normal，只能从更早的备份里捞出来在内存里补。0812 的 sample 表自带
> `tissue_type`（9,700 个样本有值），旁路表和它的生成脚本已经删掉。

图里就只有这些，没有目录同步步骤：我方的 slot 模型不进图，运行时由
`tool_catalog_source.py` 从 `data/csv/catalog/` 合并。

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
NEO4J_DATABASE=neo4j               # 4.5 导入的目标库

# —— 运行模式 ——
DATA_MATCHER_MODE=neo4j            # 走 Neo4j，不用 CSV
DATAGRAPH_SCHEMA_MODE=auto         # 自动识别 managed / legacy 两种 schema
DATAGRAPH_SNAPSHOT_ID=             # 0812 后端没有 managed 快照，留空

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
  "database": "neo4j",
  "snapshot_id": null,
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
  --uri bolt://127.0.0.1:7687 --database neo4j \
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
        "NEO4J_DATABASE": "neo4j",
        "DATAGRAPH_SNAPSHOT_ID": ""
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

## 9. 备选：连接远程服务器（生产路径）

不想本机装 Neo4j 就直接连组内共享的那台，它在 2026-08-12 已刷成 0812 图：

```ini
# .env.local
NEO4J_URI=bolt://192.168.130.24:7690
NEO4J_USER=neo4j
NEO4J_PASSWORD=<找组内要>
NEO4J_DATABASE=neo4j
DATA_MATCHER_MODE=neo4j
DATAGRAPH_SCHEMA_MODE=auto         # ★ 自动识别大小写标签(Project/project…)，两种导入都能读
```

浏览器 `http://192.168.130.24:7480`。注意端口是 7690/7480，不是默认的 7687/7474；
要先接进能路由到 `192.168.130.0/24` 的网络（不在同一网段时 ping 都不通）。

这台服务器与本机自建**逐项一致**，都是 0812 交付本身，没有任何我方新增的标签、
节点或属性。0811 时期服务器上曾额外写过 `sample_role`，因为那版交付没有肿瘤/正常
标注；0812 自带 `tissue_type`，那处偏离已经撤掉。

### 9.1 重刷这台服务器

`import_0812.py` 要求 CSV 躺在服务器的 `import/` 目录里，远程没有文件系统权限，
所以另有一份 `scripts/python/import_0812_remote.py`：它把交付 Cypher 里的
`LOAD CSV FROM 'file:///…'` 改写成 `UNWIND $rows`，从本地 CSV 分批推过去，
MERGE/SET 主体、约束和索引都还是交付原文，因此产出与本机导入同源。

```bash
export NEO4J_REMOTE_PW='<口令>'
python3 scripts/python/import_0812_remote.py \
  --uri bolt://192.168.130.24:7690 --user neo4j --password-env NEO4J_REMOTE_PW \
  --confirm-clear
```

约 1 分钟（43.3 万行）。**会先清空整库**，跑完自动比对
`config/senior_0812_reference_counts.json`，逐项一致才返回 0。

> `DATAGRAPH_SCHEMA_MODE=auto` 已做过大小写标签自适配和计数容差：无论她的库是大写标签
> (`Project/Study/…`) 还是小写标签 (`project/study/…`)、节点数是否与契约完全一致，MCP 都能
> 读入并给出告警而不崩溃。先跑一次 `health_check` 确认 `connected: true` 再接 agent。

---

## 10. 常见问题排查

| 现象 | 原因 / 处理 |
|---|---|
| `health_check: connected=false, error=connection_timeout` | Neo4j 没起 / URI 端口错 / 防火墙。先 `nc -z 127.0.0.1 7687`。 |
| `database id mismatch` | `--expected-database-id` 与 `CALL db.info()` 返回的不一致，导入器拒绝写入。按 4.3 重新取 id。 |
| `database is in use` | dump/load 要在目标实例**停止**时执行。 |
| `authentication_failed` | 初始密码要在新实例**第一次启动前** `set-initial-password`；`.env.local` 密码要一致。 |
| `Neo4j data matcher is not configured` | `.env.local` 缺 `NEO4J_URI` / `NEO4J_DATABASE` / `NEO4J_PASSWORD` 其一。 |
| `ready=false` 但 connected=true | 计数不符合合同：对比 `health_check` 的 `legacy_label_counts` 与 `config/unified_graph_expectations.json`，通常是 4.5 只跑了一半。 |
| `unsupported_reason` 非空 / `selection_status=unsupported` | 需求依赖尚未原子化的能力（差异表达、GO/KEGG、WGCNA、生存分析等），属正常返回，不是报错。 |
| clone 很慢 | 仓库含 62MB CSV，属正常。 |
| 连 `192.168.130.24` 超时 | 不在能路由到 `192.168.130.0/24` 的网络上。先 `ping 192.168.130.24`，不通就连 VPN 或换网，光看端口没用。 |

---

## 11. 参考文档

- [`docs/mcp_delivery/datagraph_restore_guide.md`](mcp_delivery/datagraph_restore_guide.md) — 恢复细节与九项验证
- [`docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md`](mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md) — tool-chain/v2 返回契约
- [`docs/mcp_delivery/PACKAGE_MANIFEST.md`](mcp_delivery/PACKAGE_MANIFEST.md) — 交付物清单与哈希
- [`config/unified_graph_expectations.json`](../config/unified_graph_expectations.json) — 快照/计数期望值
