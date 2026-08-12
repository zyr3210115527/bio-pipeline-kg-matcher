# Unified Graph Restore Guide

> **已作废（2026-08-12）。** 交付不再提供 Neo4j dump，本文引用的
> `mcp_delivery/neo4j/` 目录已删除。现在从 `data/0811/` 的 CSV 直接导入建图，
> 见仓库根目录的 `docs/MCP连接与运行指南.md` 第 4 节。本文保留作历史参考。


## 前置条件

- Neo4j Community 2026.06.0（交付 dump 的创建版本）
- Java 21
- 一个全新的 Neo4j home；不要覆盖已有生产 home
- dump: `neo4j/datagraph-staging.dump`
- SHA-256: `32349f2e3cf7087180e72a84f422cc24108186b12eb624abfd9e8e96c45e1a26`
  （2026-07-30 刷新：完整活图 82,659 节点 / 103,084 关系，新增 t1.file_path 回填）

## 1. 校验文件

```bash
shasum -a 256 neo4j/datagraph-staging.dump
```

结果必须与上面的 hash 完全一致。

## 2. 准备新 home

在新 home 的 `conf/neo4j.conf` 至少设置：

```properties
initial.dbms.default_database=datagraph-staging
server.default_listen_address=127.0.0.1
server.bolt.listen_address=127.0.0.1:7687
server.http.listen_address=127.0.0.1:7474
dbms.security.auth_enabled=true
```

先为新实例设置密码，再启动第一次：

```bash
NEO4J_HOME=/path/to/new-home NEO4J_CONF=/path/to/new-home/conf \
  /path/to/neo4j/bin/neo4j-admin dbms set-initial-password 'replace-me'
```

## 3. 恢复

数据库名必须与 dump 文件名一致：

```bash
NEO4J_HOME=/path/to/new-home NEO4J_CONF=/path/to/new-home/conf \
  /path/to/neo4j/bin/neo4j-admin database load datagraph-staging \
  --from-path=/absolute/path/to/mcp_delivery/neo4j \
  --overwrite-destination=true
```

只对事先确认的全新 home 使用 `--overwrite-destination`。然后启动 Neo4j：

```bash
NEO4J_HOME=/path/to/new-home NEO4J_CONF=/path/to/new-home/conf \
  /path/to/neo4j/bin/neo4j console
```

## 4. 统一图验证

```bash
export RESTORE_NEO4J_PASSWORD='replace-me'
python scripts/python/verify_unified_graph.py \
  --expectations app/config/unified_graph_expectations.json \
  --uri bolt://127.0.0.1:7687 \
  --database datagraph-staging --user neo4j \
  --password-env RESTORE_NEO4J_PASSWORD \
  --expected-database-id AF76A4FDB2817F94BD15471B3956E277CD52659FC960C514A67345F59531F1EF \
  --forbid-database-id 3B6484DB41F1C2BDC776FB5F93C6DEAD92BA99CB55BB62B4DC4BAE9A5284C7B1 \
  --output restore_unified_graph_verification.json
```

九项必须全部 PASS。预期数据图为 32,744 节点 / 73,001 关系，工具目录为 233 节点 / 601 关系，总计 32,977 节点 / 73,602 关系，跨域关系为 0。目录 fingerprint 必须是 `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`。

随后运行 `python scripts/python/mcp_smoke_test.py`。本次交付已在一个全新 home 的 `7689` 上实际恢复，统一图 9/9、双读 191/191、MCP 在线/离线各 12/12 均通过；证据为 `restore_*.json`。

## 5. 常见错误

- `No matching archives`: load 的数据库名必须是 `datagraph-staging`。
- `database is in use`: dump/load 要在目标实例停止时执行。
- `authentication_failed`: initial password 必须在新实例第一次启动前设置。
- `unified_graph_contract_mismatch`: dump、database 或 snapshot 配错，禁止启动 MCP 生产调用。
