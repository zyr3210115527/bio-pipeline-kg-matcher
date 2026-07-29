# update728 MCP 验证上线包清单

生成日期：2026-07-29

## 验证对象

- 真实 Neo4j 发行版：2026.06.0
- 验证端口：`bolt://127.0.0.1:7688`（独立临时实例）
- 数据源：`import.zip` 解压后的完整 CSV
- MCP 模式：`DATA_MATCHER_MODE=neo4j`
- 旧图模式：`DATAGRAPH_SCHEMA_MODE=legacy-update728`

## 已通过验证

`真实后端验证结果.json` 的 `ready=true`。检查覆盖：

- Bolt 连通性和 Neo4j 版本
- Project 17、Study 19、Individual 5,335、Sample 8,640、T1 24,518、T2 38,011
- 旧关系 `IN_STUDY`、`IN_SAMPLE`、`GENERATED_FROM`、`NEXT_TOOL`
- T1/T2 代表性查询和旧图 matcher 适配
- MCP `tools/list` 7 个运行时接口
- `health_check`、`list_workflow_methods`、`list_pipeline_capabilities`
- `query_data_availability`、`route_pipeline_request`、`render_pipeline_answer`
- 错误参数返回 JSON-RPC `-32602`

真实库中旧图关系核对：`NEXT_TOOL=22`（`kind=data/order`）；安装 MCP 后新增审核目录 `tool_id=24`、`NEXT=28`、`HAS_STEP=7`，旧 `Tool/Function/Format` 信息图未删除。

## 包内目录

- `app/`：MCP 服务端、Neo4j matcher、路由和运行时依赖代码
- `app/config/`：统一期望值、知识卡和执行合同
- `app/data/csv/catalog/`：24 工具执行目录及关系 CSV
- `app/scripts/python/`：目录 bootstrap 和真实后端只读验证脚本
- `后端数据提供方必须修改清单.md`：第一步必须修改项
- `中文接入方案.md`：部署、接入、回滚和责任边界
- `mcp输出JSON实例.json`：输出结构示例
- `真实后端验证结果.json`：本次真实后端验证证据

包不包含 Neo4j 二进制、原始业务 CSV 或任何凭据；业务库连接由部署环境变量提供。
