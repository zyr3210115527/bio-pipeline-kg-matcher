# update728 MCP 接入方案

## 目标

本方案让 MCP 直接读取实际交付的 Neo4j 业务图，同时保留旧图中的数据实体和 `NEXT_TOOL` 信息图。MCP 的执行合同仍由包内审核目录提供：24 个 `tool_id`（12 个原子工具、12 个流程工具）、精确输入输出 slot、artifact、`HAS_STEP` 和审核后的 `NEXT`。

## 一、后端数据提供方必须先完成

必须项见同包的 `后端数据提供方必须修改清单.md`。核心是：所有 CSV 实际 UTF-8；明确 Individual 重复 accession 的主键和冲突策略；补齐或诊断 6,785 条缺失端点关系；统一 5,346 条 Format 拼写；写入稳定的 `BackendSnapshot`；修正 `NEXT_TOOL/NEXT` 与 Run 验证错位；提供带约束、索引、日志且可重复执行的导入入口。

T1 的 1,152 条完全重复记录不要求单独处理；T1 内部 ID 与展示文件名、标签大小写、`T2_id/t2_id`、`kind` 边属性均由 MCP 兼容层处理。

## 二、部署 MCP

1. 解压本包，进入 `app/`。
2. 安装 `requirements.txt` 中的 Neo4j Python 驱动。
3. 设置连接变量：

```bash
export NEO4J_URI='bolt://<neo4j-host>:7687'
export NEO4J_USER='neo4j'
export NEO4J_PASSWORD='<password>'
export NEO4J_DATABASE='neo4j'
export DATA_MATCHER_MODE='neo4j'
export DATAGRAPH_SCHEMA_MODE='auto'
export MCP_DATA_MATCHER_MODE='neo4j'
```

4. 在真实业务库执行包内 `scripts/python/sync_neo4j_tool_catalog.py --apply --bootstrap-catalog`。该脚本只清理带小写 MCP owner label 的目录节点，不删除旧的 `Tool/Function/Format` 信息图。
5. 运行 `scripts/python/validate_real_backend.py --uri ... --output docs/real_backend_validation.json`。
6. 只有验证报告 `ready=true` 才接入 MCP 客户端：

```bash
python server.py
```

MCP 使用 JSON-RPC stdio。先发送 `initialize`，再调用 `tools/list`；执行请求使用 `tools/call`。

## 三、上线检查

- `health_check`：应返回旧核心标签精确计数，MCP `tool_count=24`，并报告 `backend_snapshot` 或明确 `backend_snapshot_missing` 警告。
- `list_workflow_methods`：原子工具数 12，流程工具数 12。
- `list_pipeline_capabilities`：流程工具均来自 Neo4j 的 `HAS_STEP` 锁定配方。
- `query_data_availability`：仅查询，不执行分析；数据后端为 `neo4j`。
- `route_pipeline_request`：只规划和校验，不执行外部工具。
- `validate_tool_chain`：校验 slot、artifact 和 NEXT，不接受未注册工具。
- `render_pipeline_answer`：只负责渲染已有结果。

## 四、回滚

MCP 目录节点带有小写 owner label。回滚时停止 MCP 进程，恢复 Neo4j 备份，再重新运行验证；不要执行旧的 `00_clear.cypher` 作为回滚操作。旧 39 个 Tool 信息图不由 MCP 目录同步脚本删除。

## 五、边界

MCP 不把旧 39 个 Tool 直接当作可执行合同。若未来要转换为执行真源，后端还需为每个工具提供稳定 runtime ID、`tool_kind`、必选输入输出 slot、artifact 和 data 边的 input/output slot 名。
