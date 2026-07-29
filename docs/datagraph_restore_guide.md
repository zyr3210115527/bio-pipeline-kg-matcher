# 数据图恢复手册

> **当前交付更新（2026-07-24）**：MCP 交付应使用
> `docs/mcp_delivery/neo4j/datagraph-staging.dump`，SHA-256
> `07572b120251d549062890c29e64a3f9ac2f5ea95dc5d0c517ec3a768c8017a9`。
> 它包含数据图 32,744 节点/73,001 关系和工具目录 233 节点/601 关系；统一图总计 32,977 节点/73,602 关系。
> 恢复后应运行 `scripts/python/verify_unified_graph.py`、191-case 双读和 MCP smoke；
> 完整命令见 `docs/mcp_delivery/datagraph_restore_guide.md`。下文的纯数据图 dump
> 仅保留为上一轮历史恢复记录，不应作为当前 MCP 交付物。

本手册对应 `datagraph/v1`。已演练环境为 Neo4j Community `2026.06.0` + JDK 21，不依赖 APOC 或其他插件。

## 交付物

| 文件 | 用途 | 验证值 |
|---|---|---|
| `docs/backups/datagraph_staging_dump_20260724T090000Z/datagraph-staging.dump` | Neo4j 原生离线 dump | SHA-256 `1c606e01489a8d472d1a95f9d86f3437e5e2818ea08da61c8a41e56922ac3641` |
| `docs/import_manifest_20260724T085734.559720Z.json` | CSV hash、scope、计数、悬空外键、schema inventory | snapshot `dg-b23135d49c950d0846a563bc` |
| `docs/datagraph_verification_report.json` | 源 staging 六层验证 | material differences `0` |
| `docs/datagraph_restore_verification.json` | dump 恢复库六层验证 | material differences `0` |

生产库在本轮写入前的逻辑备份为 `docs/backups/production_full_logical_backup_20260724T084051.799468Z.jsonl.gz`，SHA-256 为 `34025502eed5cc1acf59c8236423b830f5b6161cfc1038bb63a314980d55b2a7`。它包含 34,838 节点、81,227 关系、16 约束和 19 索引，与本数据图 dump 不是同一交付物。

## 前置检查

1. 使用与 dump 一致的 Neo4j `2026.06.0`；跨大版恢复需另行执行 Neo4j migration，本演练未覆盖。
2. 准备全新、独立的 `NEO4J_HOME`、data/logs/run/import/plugins 目录和未占用端口。
3. 校验 dump：

```bash
shasum -a 256 docs/backups/datagraph_staging_dump_20260724T090000Z/datagraph-staging.dump
```

4. 配置 `initial.dbms.default_database=datagraph-staging`、独立的 `server.directories.*`、Bolt/HTTP 端口。本演练使用 restore home `/Users/zhouyiran/.codex/runtime/neo4j_datagraph_restore`、Bolt `7689`、HTTP `7476`。

## 离线恢复

目标 Neo4j 必须处于停止状态。以下命令中的路径按部署环境替换：

```bash
export JAVA_HOME=/path/to/jdk-21
export NEO4J_HOME=/path/to/fresh-neo4j-home
export NEO4J_CONF=/path/to/fresh-neo4j-home/conf

/path/to/neo4j-2026.06.0/bin/neo4j-admin dbms set-initial-password '<new-local-password>'
/path/to/neo4j-2026.06.0/bin/neo4j-admin database load datagraph-staging \
  --from-path='/absolute/path/to/docs/backups/datagraph_staging_dump_20260724T090000Z'
/path/to/neo4j-2026.06.0/bin/neo4j console
```

`database load` 恢复约束、索引、节点、关系和 store ID，无需再手动重建 schema。本演练恢复后的 database ID 保持为 `AF76A4F...F1EF`；因此对克隆库而言，**database ID 不足以单独证明连接的是哪个实例**，还必须核对 URI/端口、进程 `--home-dir`、system database ID 和数据目录。

## 恢复后 gate

先只读核对身份和计数：

```cypher
CALL db.info() YIELD name, id, creationDate RETURN name, id, creationDate;
MATCH (n) RETURN count(n) AS nodes;
MATCH ()-[r]->() RETURN count(r) AS relationships;
MATCH (n)
WHERE any(x IN labels(n) WHERE x IN
  ['Tool','tool_id','IOSlot','io_slot','ArtifactType','artifact_type','Function','function','Format','format'])
RETURN count(n) AS forbidden_tool_nodes;
```

预期：`datagraph-staging`；数据图 32,744 节点/73,001 关系；工具目录 233 节点/601 关系；总计 32,977 节点/73,602 关系；跨域关系 0。然后运行全量 gate：

```bash
export RESTORE_NEO4J_PASSWORD='<new-local-password>'
.venv/bin/python scripts/python/verify_datagraph.py \
  --csv-dir data/csv --scope t1 \
  --manifest docs/import_manifest_20260724T085734.559720Z.json \
  --allowlist config/datagraph_representation_allowlist.json \
  --uri bolt://127.0.0.1:7689 --database datagraph-staging --user neo4j \
  --password-env RESTORE_NEO4J_PASSWORD \
  --expected-database-id AF76A4FDB2817F94BD15471B3956E277CD52659FC960C514A67345F59531F1EF \
  --forbid-database-id 3B6484DB41F1C2BDC776FB5F93C6DEAD92BA99CB55BB62B4DC4BAE9A5284C7B1 \
  --output-json docs/datagraph_restore_verification.json \
  --output-markdown docs/datagraph_restore_verification.md
```

退出码必须为 0，六层都必须 `PASS`，实质差异必须为 0。已演练结果满足该条件，图指纹为 `f14a565c755f8235ddd13b91223ea7be946d5539a255864c553594456b488afe`。

## Smoke queries

```cypher
// 按测序类型筛 FASTQ
MATCH (f:t1)
WHERE f.physical_format IN ['fq.gz','fastq.gz'] AND toUpper(f.strategy) CONTAINS 'WES'
RETURN count(f) AS files, count(DISTINCT f.run_accession) AS runs;

// 按 T2 语义格式映射输入角色
MATCH (f:t2)-[:IN_FORMAT]->(fmt:data_format)
WHERE fmt.format IN ['Raw Counts','TPM / FPKM','Public Somatic MAF','Sample Metadata']
RETURN fmt.format, count(f) AS files;

// 按个体查多样本，供配对逻辑继续分类 tumor/normal
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WITH i, collect(s.sample_accession) AS samples
WHERE size(samples) >= 2
RETURN i.individual_accession, samples, size(samples) AS sample_count
ORDER BY sample_count DESC LIMIT 5;
```

已演练结果：WES FASTQ 8,922 个、4,461 个 run；T2 角色类查询返回 `Raw Counts` 4、`TPM / FPKM` 8、`Public Somatic MAF` 11、`Sample Metadata` 11；个体多样本查询正常返回。

## 回滚与故障处理

- 不要对正在 mounted 的 database 执行 dump/load。
- load 失败时不在原目标上反复覆盖；换一个全新 home 重做，保留失败目录供诊断。
- verifier 任意一层失败均不得切换 matcher。根据 JSON 的 `material_differences` 定位后，从 canonical CSV 重新导入新隔离库，不在图上手工补数。
- 生产回滚使用上述生产逻辑备份只能在经审核的空隔离库中先演练；本轮未对生产执行停库、load 或任何写入。
