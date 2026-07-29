# Bio Pipeline KG Matcher（生信流程与知识图谱匹配器）

面向自然语言的生信工作流规划器。运行时工具唯一真源是真实 Neo4j 实例：当前登记 24 个 tool，包括 12 个 atomic tool、11 个完整 pipeline tool 和 1 个 task pipeline。公共推荐只使用 12 个 atomic tool；pipeline-level 节点仅供目录查询。

## Top-3 编排

- **分析请求**：一次 LLM 同时生成业务 pipeline 推荐和 1-5 条按匹配度排序的原子链；返回最多 3 条 Neo4j 工具/数据推荐，并逐条校验原子链。
- **能力问答**：`能做什么`、`有哪些流程处理 MAF`、`有哪些原子工具`等目录问题直接查询 Neo4j，不生成候选链，返回 `selection_status=information`。
- **未原子化需求**：差异表达、富集、WGCNA、生存分析等若当前 atomic 目录无法完整表达，返回 `unsupported`，不调用 pipeline-level 节点补齐。

`recommendations[]` 返回业务 pipeline 的 Neo4j 工具详情和逐文件图谱证据；`candidates[]` 只返回通过闭集校验的 atomic 工具链。表格参考文件只有经 Neo4j 精确确认后才标为 `available`，否则标为 `missing_from_graph`。每个原子候选都独立拥有 `assets`、`tool_chain`、`study_accession` 和 `match_id`。配对 WES 保留 tumor/normal 四 FASTQ 专用匹配和 GATK 四槽绑定，候选之间不共享资产选择状态。运行参数以及 GTF、参考基因组、索引等执行端资源不参与可用性判定。

## 数据与 KG 后端

`data/csv/` 同时保留两层数据：

- `entities/`、`reference/`、`relations/`：2026-07-17 规范化 KG schema，供离线 matcher 和 Neo4j 共用；
- 旧版平铺 CSV：作为物理文件路径兼容镜像。matcher 以规范化实体为准，只从旧 T1 表补齐 `file_path` 等新实体未携带的字段。

Neo4j 是 pipeline/tool/slot/format/`NEXT`/`HAS_STEP` 的唯一运行时真源，同时提供 Demo 证据展示。Neo4j 不可用时不会退回到 WDL 工具。本地 WDL 只保留用于历史审查，公共 API 和 MCP 不从中解析工具。

同步前先验证 CSV，再将审核后的 NEXT 写入真实实例。默认 `--apply`
只修改 `source='curated-next-csv'` 的 NEXT，不修改工具定义、slot 或其他关系：

```bash
python3 scripts/python/validate_csv.py --project-root .
```

需要 Neo4j 时安装驱动并配置环境变量：

```bash
python3 -m pip install -r requirements-neo4j.txt
python3 scripts/python/sync_neo4j_tool_catalog.py --apply
```

## 运行模式

默认调用 OpenAI 兼容 LLM。分析请求必须由一次 LLM 调用生成候选；模型不可用时返回 `no_candidate`，不会回退到标准流程或编造方法链。目录浏览仍是确定性只读请求。

关闭 LLM、仅使用确定性规则（仍需连接 Neo4j 工具目录）：

```bash
FORCE_RULE=1 python3 server.py
```

启用 LLM 与真实 Neo4j Demo：

```bash
python3 -m pip install -r requirements-llm.txt
python3 -m pip install -r requirements-neo4j.txt
cp .env.local.example .env.local
# 在 .env.local 中填入轮换后的 LLM_API_KEY 和本机 NEO4J_PASSWORD
python3 app.py
```

默认 LLM 端点为 `api.deepseek.com`，模型为 `deepseek-v4-flash`，启用 thinking 与 high reasoning effort，超时 180 秒，最大输出 16000 token。显式进程环境变量优先于 `.env.local`。

## Web Demo

```bash
python3 app.py                 # http://127.0.0.1:8000
PORT=9000 python3 app.py
FORCE_RULE=1 python3 app.py    # 完全离线
```

`POST /api/ask` 返回 `tool-chain/v2` 契约：`recommendations[]` 是业务流程与数据证据，`candidates[]` 是独立的 Knowledge Card 原子工具链和数据资产。`GET /api/health` 返回脱敏的 LLM 配置状态与 Neo4j 版本、延迟、节点/关系统计。

## MCP 工具

| 工具 | 功能 |
|------|------|
| `route_pipeline_request` | 一次 LLM 生成业务 pipeline 推荐与原子候选，返回 Neo4j 工具/数据证据及严格校验后的 atomic Top-3 |
| `list_pipeline_capabilities` | 列出 Neo4j 中 12 个 pipeline/task-pipeline tool、slot 及锁定步骤 |
| `list_workflow_methods` | 列出 12 个 Neo4j atomic tool、24 个完整目录实体及拆解状态 |
| `validate_tool_chain` | 校验调用方提供的原子链 |
| `query_data_availability` | 查询 pipeline 或原子链的数据可用性 |
| `health_check` | 验证统一图和只读连接状态 |
| `render_pipeline_answer` | 渲染已有 pipeline 路由结果的中文摘要 |

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py app.py intent.py pipeline_router.py workflow_composer.py runtime_config.py neo4j_observability.py
RUN_REAL_INTEGRATION=1 python3 -m unittest discover -s tests -p 'test_runtime_integrations.py' -v  # 需要 .env.local 凭证
```

## 安全边界

- 密钥只通过环境变量注入，不写入源码、`.mcp.json` 或分发包。
- `.env.local` 已忽略，日志和 API 只显示端点主机、模型及配置状态。
- LLM 模式会发送用户问题、标准 pipeline 摘要和方法输入输出元数据，不发送原始生物数据文件内容。
- `feasibility` 只判断用户样本数据角色是否齐全；运行参数和执行端托管参考资源不进入该状态。路径、格式、样本 ID、配对和统计样本量由执行端校验。

## 相关文档

- `项目说明.md`：原系统设计与 benchmark 说明；
- `MCP连接文档.md`：MCP 接入说明；
- `docs/bio_pipelines_bug_report.md`：14 个 pipeline 静态审查与质量门禁依据；
- `docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md`：agent 端 `tool-chain/v2` 字段与迁移说明；
- `docs/mcp_delivery/schemas/tool_chain_output.schema.json`：正式 v2 JSON Schema；
- `cypher/`、`scripts/`：Neo4j schema、导入、查询模板及 CSV 校验器。
