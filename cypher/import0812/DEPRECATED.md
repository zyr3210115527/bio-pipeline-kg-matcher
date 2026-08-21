# 这套 LOAD CSV 脚本已过期，不要直接跑

0821 数据换代后，本目录的 `02_import_entities.cypher` / `03_import_ontology_relations.cypher`
引用的列名在 `data/0812/` 的 CSV 里**已经不存在**了。逐列比对结果：

| 脚本里写的 | 现在 CSV 里的 |
|---|---|
| `row.T1_id` / `row.T2_id` | `t1_id` / `t2_id` |
| `row.Title`（study） | `title` |
| `row.type`（project） | `tumor_subtype` |
| `row.输入格式` / `输出格式` / `下游工具` / `适用组学`（tool） | `input_format` / `output_format` / `downstream_tools` / `applicable_omics` |
| `row.age` / `row.gender` …（individual 无前缀名） | `01_age` / `01_gender`（全列加编号前缀） |

Cypher 读不到的列返回 null，**不会报错**——直接跑的结果是灌出一张属性名残缺的图，
MCP 那边所有按 `t1_id`/`title`/`01_age` 写的查询会静默查空。

更要紧的一点：现网（192.168.130.24）图谱实测的属性名是 `t1_id`/`title`/`tumor_subtype`/
`01_age`，跟新 CSV 一致、跟本目录脚本不一致。也就是说**现网这张图本来就不是这套脚本灌的**，
它至少落后一代。

## 用什么代替

`scripts/load_graph_http.py`。它走 HTTP `tx/commit` 批量 UNWIND，不依赖 LOAD CSV。
之所以必须换掉 LOAD CSV：`LOAD CSV FROM 'file:///'` 读的是 **Neo4j 服务器本地**的 import
目录，而目标机 22 端口不可达（ssh 超时），CSV 推不上去；HTTP 7480 是通的。

```bash
python3 scripts/load_graph_http.py --dry-run      # 只校验列名与行数
python3 scripts/load_graph_http.py --backup-only  # 只导出现网到 JSONL
python3 scripts/load_graph_http.py --go           # 备份 → 清库 → 重建 → 校验
```

新脚本以「CSV 列名 = 图属性名」为契约，11 条唯一约束 + 10 条索引均与现网 `SHOW INDEXES`
逐条核对过。0821 用它重建的结果：81,628 节点 / 364,184 关系，与交付截图一致。

## 本目录还有什么用

`constraints.cypher` / `indexes.cypher` / `05_validation.cypher` 仍可作为约束定义与校验语句
的参考读物（新脚本里的 `CONSTRAINTS`/`INDEXES` 就是照它们 + 现网实测对齐的）。
`00_clear.cypher` 也照旧可用。要恢复 LOAD CSV 路径的话，需要先把 `02_`/`03_` 的列名按上表
改到位，并解决 CSV 上传到服务器 import 目录的问题。
