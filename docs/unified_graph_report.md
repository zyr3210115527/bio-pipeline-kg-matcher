# Unified Graph Report

## 结论

隔离数据库 `datagraph-staging` 已成为自包含的统一交付图。数据图和工具目录在同一 database 中，但节点标签、所有权标记和关系均保持域隔离。生产数据库只作为工具目录的只读来源，未发生写入。

## 可行性与实现

原 `sync_neo4j_tool_catalog.py` 支持 URI、database、user 和 password-env，但普通 `--apply` 只维护 CSV 管理的目录部分，不能精确复制生产目录中的 slot 固定属性、pipeline recipe 和全部关系。因此使用 `scripts/python/copy_tool_catalog.py` 对生产目录做只读导出，并在目标 ID 守卫、禁止生产 ID、数据图存在性和跨域关系检查通过后，精确替换 staging 目录域。

标签不存在冲突：工具目录使用 `tool_id/io_slot/artifact_type/function/format`，数据参考域使用 `data_format/data_format_row/data_level/data_modal`。工具目录的 `:format` 与数据图的 `:data_format` 可明确区分。数据图 `t1-[:IN_FORMAT]->data_format` 表示语义格式，物理格式在 `t1.physical_format`，不能复用旧生产 Cypher 的含义。

## 导入前后

| 项目 | C 基线 | 最终 D staging |
|---|---:|---:|
| 目录节点 | 218 | 233 |
| 目录关系 | 556 | 601 |
| 工具 | 24 | 24 |
| atomic / pipeline | 12 / 12 | 12 / 12 |
| input / output slot | 49 / 50 | 58 / 53 |
| NEXT | 22 | 28 |
| HAS_STEP | 7 | 7 |

初始 legacy bootstrap 缺少 301 条生产关系并多出 6 条错误映射。C 阶段已把完整目录转成 canonical CSV；D 阶段再原子加入槽、variant 和 NEXT 四元组，最终 staging fingerprint 为 `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`。

## 最终身份

| 域 | 节点 | 关系 | fingerprint/snapshot |
|---|---:|---:|---|
| 数据图 | 32,744 | 73,001 | `f14a565c...b488afe`; `dg-b23135d49c950d0846a563bc` |
| 工具目录 | 233 | 601 | `2ec21a69...5c903` |
| 合计 | 32,977 | 73,602 | 两域交叉关系 0 |

统一验证脚本 `scripts/python/verify_unified_graph.py` 同时检查数据计数、数据 fingerprint、snapshot、目录计数、目录 fingerprint、工具数、合同关系数、域隔离和总计数。九项全部通过，原始结果见 `docs/unified_graph_verification.json`。

## 保留的数据边界

交付 scope 仍为 `t1`。1,269 条悬空外键按 manifest 忠实记录，不通过拓扑遍历补造。HRA000122 的 696 条 T11-only WES FASTQ 和 HRA000021 的 T11-only BAM 不进入本次权威范围，等待数据负责人决定。两个 Fusion T2 的语义误标也没有篡改，matcher 继续复用文件名/format 推断。
