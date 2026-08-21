#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""load_graph_http.py — 把 data/0812 的 31 个 CSV 灌进 Neo4j，走 HTTP tx/commit。

为什么不用 cypher/import0812/ 那套 LOAD CSV：
  1. LOAD CSV 读的是 **Neo4j 服务器本地** 的 import 目录。0821 实测目标机 192.168.130.24
     的 22 端口不可达（ssh 超时），文件推不上去，那套脚本就跑不了。HTTP 7480 是通的。
  2. 那套脚本的列名是**上一代 CSV** 的（T1_id/Title/type/输入格式/individual 用 age 这种
     无前缀名）。现网图谱实测用的是 t1_id/title/tumor_subtype/input_format/01_age——
     跟新 CSV 表头一致、跟老脚本不一致。也就是说现网不是这套脚本灌的，它已经落后一代。
     本脚本以「CSV 列名 = 图属性名」为契约，与现网实测属性名逐一对齐过。

用法:
    python3 scripts/load_graph_http.py --backup-only          # 只备份现网
    python3 scripts/load_graph_http.py --dry-run              # 只校验 CSV 与计数，不写库
    python3 scripts/load_graph_http.py --go                   # 备份 → 清库 → 全量重建 → 校验
环境:
    NEO4J_HTTP  (默认 http://192.168.130.24:7480/db/neo4j/tx/commit)
    NEO4J_USER / NEO4J_PASSWORD
"""
import argparse
import base64
import csv
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "0812")
URL = os.environ.get("NEO4J_HTTP", "http://192.168.130.24:7480/db/neo4j/tx/commit")
USER = os.environ.get("NEO4J_USER", "neo4j")
PWD = os.environ.get("NEO4J_PASSWORD", "")
AUTH = "Basic " + base64.b64encode(f"{USER}:{PWD}".encode()).decode()

csv.field_size_limit(10 ** 7)


def run(statement, params=None, retries=3):
    body = json.dumps({"statements": [{"statement": statement,
                                       "parameters": params or {}}]}).encode()
    for a in range(retries):
        try:
            req = urllib.request.Request(URL, data=body, headers={
                "Content-Type": "application/json", "Authorization": AUTH})
            d = json.load(urllib.request.urlopen(req, timeout=300))
            if d.get("errors"):
                raise RuntimeError(d["errors"][0].get("message", "")[:400])
            res = d["results"][0]
            return [r["row"] for r in res["data"]]
        except RuntimeError:
            raise                      # Cypher 语义错，重试没意义,直接冒泡
        except Exception:
            if a == retries - 1:
                raise
            time.sleep(4 * (a + 1))


def rows(rel):
    """读 CSV。空串一律丢掉——Neo4j 不存 null，写 '' 会让 IS NOT NULL 判断失真
    （现网实测就是空值直接不建属性，这里保持一致）。"""
    path = os.path.join(DATA, rel)
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            yield {(k or "").strip(): v for k, v in r.items()
                   if k and v not in (None, "")}


# ── 实体：(文件, 标签, 主键列) ───────────────────────────────────────────
# individual 的主键是 00_individual_accession，但图上另有一个无前缀的
# individual_accession（唯一约束建在它上面）+ individual_accession_aliases，
# 两者现网实测 7215/7215 完全相同。这是给查询用的稳定句柄，必须一起写。
ENTITIES = [
    ("entities/project.csv",    "project",    "project_accession"),
    ("entities/study.csv",      "study",      "study_accession"),
    ("entities/individual.csv", "individual", "00_individual_accession"),
    ("entities/sample.csv",     "sample",     "sample_accession"),
    ("entities/tool.csv",       "tool",       "tool_id"),
    ("entities/T1.csv",         "T1",         "t1_id"),
    ("entities/T2.csv",         "T2",         "t2_id"),
]

# ── 关系：(文件, 起标签, 起键列, 起键属性, 关系型, 终标签, 终键列, 终键属性) ──
RELATIONS = [
    ("relations/study_in_project.csv",      "study", "study_accession", "study_accession",
     "in_project", "project", "project_accession", "project_accession"),
    ("relations/individual_in_study.csv",   "individual", "individual_accession", "individual_accession",
     "in_study", "study", "study_accession", "study_accession"),
    ("relations/sample_in_individual.csv",  "sample", "sample_accession", "sample_accession",
     "in_individual", "individual", "individual_accession", "individual_accession"),
    ("relations/T1_in_study.csv",  "T1", "t1_id", "t1_id", "in_study",  "study", "study_accession", "study_accession"),
    ("relations/T1_in_sample.csv", "T1", "t1_id", "t1_id", "in_sample", "sample", "sample_accession", "sample_accession"),
    ("relations/T1_in_format.csv", "T1", "t1_id", "t1_id", "in_format", "format", "semantic_format", "format"),
    ("relations/T1_in_level.csv",  "T1", "t1_id", "t1_id", "in_level",  "datalevel", "data_level", "level"),
    ("relations/T1_in_modal.csv",  "T1", "t1_id", "t1_id", "in_modal",  "modal", "modal", "modal"),
    ("relations/T2_in_study.csv",  "T2", "t2_id", "t2_id", "in_study",  "study", "study_accession", "study_accession"),
    ("relations/T2_in_format.csv", "T2", "t2_id", "t2_id", "in_format", "format", "semantic_format", "format"),
    ("relations/T2_in_level.csv",  "T2", "t2_id", "t2_id", "in_level",  "datalevel", "data_level", "level"),
    ("relations/T2_in_modal.csv",  "T2", "t2_id", "t2_id", "in_modal",  "modal", "modal", "modal"),
    ("relations/T2_generated_from_T1.csv", "T2", "t2_id", "t2_id", "generated_from", "T1", "t1_id", "t1_id"),
    ("relations/tool_has_function.csv",       "tool", "tool_id", "tool_id", "has_function", "function", "function", "function"),
    ("relations/tool_has_semantic_input.csv", "tool", "tool_id", "tool_id", "input",  "format", "format", "format"),
    ("relations/tool_has_semantic_output.csv","tool", "tool_id", "tool_id", "output", "format", "format", "format"),
    ("relations/tool_suitable_for_modal.csv", "tool", "tool_id", "tool_id", "suitable_for", "modal", "modal", "modal"),
    ("relations/tool_relationship.csv",       "tool", "tool_id", "tool_id", "next_tool", "tool", "next_tool_id", "tool_id"),
    ("reference/format_subclass.csv",         "format", "child", "format", "subclass_of", "format", "parent", "format"),
]

CONSTRAINTS = [
    ("project_accession_unique",    "project",    "project_accession"),
    ("study_accession_unique",      "study",      "study_accession"),
    ("individual_accession_unique", "individual", "individual_accession"),
    ("sample_accession_unique",     "sample",     "sample_accession"),
    ("tool_id_unique",              "tool",       "tool_id"),
    ("T1_id_unique",                "T1",         "t1_id"),
    ("T2_id_unique",                "T2",         "t2_id"),
    ("format_name_unique",          "format",     "format"),
    ("function_name_unique",        "function",   "function"),
    ("level_value_unique",          "datalevel",  "level"),
    ("modal_name_unique",           "modal",      "modal"),
]
INDEXES = [
    ("project_name_index",            "project",    "project_name"),
    ("tool_name_index",               "tool",       "tool_name"),
    ("individual_tumor_type_index",   "individual", "09_tumor_type"),
    ("individual_primary_site_index", "individual", "09_primary_tumor_site"),
    ("study_tumor_type_index",        "study",      "tumor_type"),
    ("T1_strategy_index",             "T1",         "strategy"),
    ("T1_platform_index",             "T1",         "platform"),
    ("sample_specimen_type_index",    "sample",     "specimen_type"),
    ("T2_strategy_index",             "T2",         "strategy"),
    ("T2_file_path_index",            "T2",         "file_path"),
]


def batched(it, n):
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def backup(path):
    """全量导出到 JSONL。清库不可逆，这是唯一的回滚凭据——git 里的老 CSV 不算，
    现网 T1 有 27,196 个而 repo 老 CSV 只有 26,783 行，本来就对不上。"""
    t0 = time.time()
    with open(path, "w", encoding="utf-8") as f:
        for lab in ["project", "study", "individual", "sample", "tool",
                    "T1", "T2", "format", "function", "modal", "datalevel"]:
            n, skip = 0, 0
            while True:
                got = run(f"MATCH (n:{lab}) RETURN properties(n) SKIP {skip} LIMIT 5000")
                if not got:
                    break
                for r in got:
                    f.write(json.dumps({"_t": "node", "_label": lab, **r[0]},
                                       ensure_ascii=False) + "\n")
                n += len(got)
                skip += 5000
            print(f"    备份 {lab:<12} {n}")
        skip = 0
        while True:
            got = run("MATCH (a)-[r]->(b) RETURN labels(a)[0], elementId(a), type(r), "
                      f"labels(b)[0], elementId(b) SKIP {skip} LIMIT 20000")
            if not got:
                break
            for r in got:
                f.write(json.dumps({"_t": "rel", "from_label": r[0], "from": r[1],
                                    "type": r[2], "to_label": r[3], "to": r[4]}) + "\n")
            skip += 20000
        print(f"    备份关系 {skip} 量级，用时 {time.time()-t0:.0f}s → {path}")


def clear():
    for name, _, _ in CONSTRAINTS:
        run(f"DROP CONSTRAINT {name} IF EXISTS")
    for name, _, _ in INDEXES:
        run(f"DROP INDEX {name} IF EXISTS")
    while True:
        # 分批删。一条 DETACH DELETE 干掉 36 万条关系会把单事务撑得很大。
        got = run("MATCH (n) WITH n LIMIT 20000 DETACH DELETE n RETURN count(*)")
        left = run("MATCH (n) RETURN count(n)")[0][0]
        print(f"    删 {got[0][0]}，剩 {left}")
        if left == 0:
            break


def schema():
    for name, lab, prop in CONSTRAINTS:
        run(f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:`{lab}`) "
            f"REQUIRE n.`{prop}` IS UNIQUE")
    for name, lab, prop in INDEXES:
        run(f"CREATE INDEX {name} IF NOT EXISTS FOR (n:`{lab}`) ON (n.`{prop}`)")
    print(f"    约束 {len(CONSTRAINTS)} 条 + 索引 {len(INDEXES)} 条")


def load_reference():
    specs = [("reference/data_level.csv", "datalevel", "level"),
             ("reference/function.csv", "function", "function"),
             ("reference/multimodal.csv", "modal", "modal")]
    for rel, lab, key in specs:
        data = list(rows(rel))
        run(f"UNWIND $rows AS r MERGE (n:`{lab}` {{`{key}`: r.`{key}`}}) SET n += r",
            {"rows": data})
        print(f"    {lab:<12} {len(data)}")
    # formats.csv 表头是中文「语义格式」，图上属性名是 format
    fmts = [{"format": r["语义格式"], "description": r.get("description")}
            for r in rows("reference/formats.csv") if r.get("语义格式")]
    for r in fmts:
        if r["description"] is None:
            del r["description"]
    run("UNWIND $rows AS r MERGE (n:format {format: r.format}) SET n += r", {"rows": fmts})
    print(f"    format       {len(fmts)}")


def load_entities():
    for rel, lab, key in ENTITIES:
        total, bs = 0, 300 if lab == "individual" else 2000
        for chunk in batched(rows(rel), bs):
            if lab == "individual":
                # 图上的稳定句柄：无前缀 individual_accession（唯一约束建在它上面）
                # + aliases 副本。现网实测两者一致，照抄。
                for r in chunk:
                    acc = r.get("00_individual_accession")
                    r["individual_accession"] = acc
                    r["individual_accession_aliases"] = acc
                mkey = "individual_accession"
            else:
                mkey = key
            run(f"UNWIND $rows AS r MERGE (n:`{lab}` {{`{mkey}`: r.`{mkey}`}}) SET n += r",
                {"rows": chunk})
            total += len(chunk)
        print(f"    {lab:<12} {total}")


def load_relations():
    for rel, la, ca, pa, rt, lb, cb, pb in RELATIONS:
        total = 0
        for chunk in batched(rows(rel), 5000):
            chunk = [{"a": r[ca], "b": r[cb]} for r in chunk if r.get(ca) and r.get(cb)]
            if not chunk:
                continue
            run(f"UNWIND $rows AS r MATCH (a:`{la}` {{`{pa}`: r.a}}) "
                f"MATCH (b:`{lb}` {{`{pb}`: r.b}}) MERGE (a)-[:`{rt}`]->(b)", {"rows": chunk})
            total += len(chunk)
        print(f"    {os.path.basename(rel):<34} -{rt}-> {total}")


# ── 归一化：修 CSV 带进来的三类数据质量问题 ──────────────────────────────
# 全部幂等（只动还没修过的），既在 --go 末尾自动跑，也能 --normalize-only 单独对
# 已经灌好的库补跑。

# 【1】内容是数字、却被当字符串存的属性。CSV 每个格子都是字符串，MERGE...SET n += r
# 原样写进去就全成了 STRING，而 Cypher 的字符串比较是字典序——'9' > '60'、'995' > '7061'。
# 这不会报错，只会静默给错答案，0821 实测：
#   生存 > 365 天：字符串比 2110 人，实际 2465 人（漏 355）
#   TMB > 10    ：字符串比  885 人，实际  102 人（多报 783，8.7 倍）
#   生存天数最大值：字符串说 995，实际 7061
#   data_level = 1 ：0 行（存的是 '1'），data_level = '1' 才有 28228 行
#   study 按 sample_count 排序：字符串把 '81' 排在 '698'/'2030' 前面，最大的两个队列
#                              （HRA000873 2030、HRA000021 1016）被挤出 top5
# 而 13_*（生存）、11_tmb/11_msi_score 正是 SKILL 里指名做生存/TMB 分析要用的字段，
# study.sample_count 是选队列要用的字段，data_level 是 SKILL 正文里直接写了 `data_level=1`
# 的字段——错的全在主路径上。
# 列表是扫出来的（≥95% 取值匹配 ^-?\d+(\.\d+)?$ 且类型为 STRING），不是猜的；
# 用 --scan 可以重扫一遍确认没有新增漏网的。整数/浮点由运行时按有没有小数点自动判。
NUMERIC_PROPS = [
    ("individual", "01_age"),
    ("individual", "04_hemoglobin_concentration_g_l"),
    ("individual", "04_platelet_count_109_l"),
    ("individual", "04_white_blood_cell_count_109_l"),
    ("individual", "10_tumor_average_diameter_cm"),
    ("individual", "11_msi_score"),
    ("individual", "11_proportion_of_bone_marrow_blast_cells"),
    ("individual", "11_tmb"),
    ("individual", "12_hsct"),
    ("individual", "12_number_of_adjuvant_treatments"),
    ("individual", "13_dfs_time"),
    ("individual", "13_efs_time"),
    ("individual", "13_pfs_time"),
    ("individual", "13_survival_days"),
    ("study",      "sample_count"),
    ("study",      "individual_count"),
    ("project",    "individual_count"),
    ("datalevel",  "level"),
    ("T1",         "data_level"),
    ("T1",         "size"),
    ("T2",         "data_level"),
    ("T2",         "size"),
]
NUM_RE = r"^-?[0-9]+(\\.[0-9]+)?$"


def normalize_numeric():
    for lab, prop in NUMERIC_PROPS:
        # 先看还剩多少个 STRING 的（幂等：修过的已经是 INTEGER/FLOAT，不会再被选中）
        left = run(f"MATCH (n:`{lab}`) WHERE n.`{prop}` IS NOT NULL AND "
                   f"valueType(n.`{prop}`) STARTS WITH 'STRING' RETURN count(n)")[0][0]
        if not left:
            print(f"    {lab}.{prop:<42} 已是数值型，跳过")
            continue
        # 有小数点就转 FLOAT，否则 INTEGER。别一律 toFloat：data_level/size/天数
        # 变成 1.0 这种在输出里很难看，也会让 = 1 之外的等值比较变别扭。
        frac = run(f"MATCH (n:`{lab}`) WHERE n.`{prop}` IS NOT NULL AND "
                   f"toString(n.`{prop}`) CONTAINS '.' RETURN count(n)")[0][0]
        fn = "toFloat" if frac else "toInteger"
        # 非数字的值原样留着（比如 'unknown'）——宁可留一个字符串，也不要 toInteger
        # 静默变成 null 把数据抹掉。
        skipped = run(f"MATCH (n:`{lab}`) WHERE n.`{prop}` IS NOT NULL AND "
                      f"valueType(n.`{prop}`) STARTS WITH 'STRING' AND "
                      f"NOT n.`{prop}` =~ '{NUM_RE}' RETURN count(n)")[0][0]
        done = 0
        while True:
            got = run(f"MATCH (n:`{lab}`) WHERE n.`{prop}` IS NOT NULL AND "
                      f"valueType(n.`{prop}`) STARTS WITH 'STRING' AND n.`{prop}` =~ '{NUM_RE}' "
                      f"WITH n LIMIT 20000 SET n.`{prop}` = {fn}(n.`{prop}`) RETURN count(n)")
            c = got[0][0] if got else 0
            done += c
            if c == 0:
                break
        note = f"，{skipped} 个非数字值原样保留" if skipped else ""
        print(f"    {lab}.{prop:<42} {done} 个 → {fn[2:].upper()}{note}")


# 【2】format 大小写撞车。0821 的 formats.csv 新增了 Clinical/T1_meta/... 这批小写变体，
# 而数据侧引用的一直是 CLINICAL/T1_META 那批大写的。Neo4j 的 MERGE 大小写敏感，于是
# 每对撞车都建成两个节点，小写那个零引用。留着的害处是：模型按小写去查会查到 0 个文件，
# 从而误判"这个队列没有临床数据"。只删「存在大写同名 且 自己零引用」的，
# DIRECTORY_UNCLASSIFIED / UNMAPPEDBAM 不是撞车（只是暂时没数据引用），保留。
def normalize_format_case():
    dead = run("MATCH (f:format) WHERE NOT (f)--() "
               "AND EXISTS { MATCH (g:format) WHERE g.format = toUpper(f.format) AND g <> f } "
               "RETURN f.format ORDER BY f.format")
    names = [r[0] for r in dead]
    if not names:
        print("    无大小写撞车孤儿，跳过")
        return
    run("UNWIND $n AS x MATCH (f:format {format: x}) DELETE f", {"n": names})
    print(f"    删除大小写撞车孤儿 {len(names)} 个: {names}")


# 【3】individual 上那三个记账列。它们是 CSV 里跟着个体走的冗余快照，真正的归属靠
# in_study / in_individual 边，所以现在没有任何查询读它们——但值是错的：
#   a) 159 个个体在 individual.csv 里有两行（同一病人跨两个 study，如 HRA001748 sc-RNA
#      + HRA001749 WES）。按 accession MERGE 之后只剩一个节点，这三列被后写的那行覆盖，
#      另一半信息丢了。
#   b) 更糟的是 HRA016026 那 349 行整体错位一行：individual.csv 说 HRI1703186 的样本是
#      HRS2218012/13，而 sample.csv 和 T1.csv 都说这两个样本属于 HRI1703187。两个独立
#      来源 700/700 互相印证，说明错的是 individual.csv 这一列。
# 图上的边跟的是 sample.csv（对的那一边），所以拓扑没问题。这里把这三个属性按边重建，
# 免得以后有人图省事直接读属性去做配对——那正好会在 HRA016026 这个配对队列上全错。
def _join(var):
    """把列表拼成 'a;b;c'；空列表给 null（图里"空"就是不建属性，跟 rows() 的口径一致）。"""
    return (f"CASE WHEN size({var}) = 0 THEN null ELSE "
            f"reduce(a = '', x IN {var} | CASE WHEN a = '' THEN x ELSE a + ';' + x END) END")


def normalize_individual_cols():
    n = run(f"""
        MATCH (i:individual)
        OPTIONAL MATCH (i)-[:in_study]->(s:study)
        WITH i, s.study_accession AS sa ORDER BY sa
        WITH i, collect(DISTINCT sa) AS sts
        OPTIONAL MATCH (sp:sample)-[:in_individual]->(i)
        WITH i, sts, sp.sample_accession AS pa ORDER BY pa
        WITH i, sts, collect(DISTINCT pa) AS sps
        SET i.`00_study_accession`  = {_join('sts')},
            i.`00_sample_accession` = {_join('sps')}
        RETURN count(i)""")
    print(f"    按 in_study / in_individual 边重建 00_study_accession / "
          f"00_sample_accession：{n[0][0]} 个个体")
    # 00_strategy 没有对应的边可以重建（strategy 记在 T1/T2 上），改成从文件侧汇总
    n2 = run(f"""
        MATCH (sp:sample)-[:in_individual]->(i:individual)
        MATCH (f:T1)-[:in_sample]->(sp) WHERE f.strategy IS NOT NULL
        WITH i, f.strategy AS st ORDER BY st
        WITH i, collect(DISTINCT st) AS ss
        SET i.`00_strategy` = {_join('ss')}
        RETURN count(i)""")
    print(f"    按 T1.strategy 汇总重建 00_strategy：{n2[0][0]} 个个体")


def normalize():
    print("  [1] 数值属性类型")
    normalize_numeric()
    print("  [2] format 大小写撞车")
    normalize_format_case()
    print("  [3] individual 冗余记账列")
    normalize_individual_cols()


def scan_numeric():
    """重扫一遍：哪些属性内容是数字却存成了 STRING。用来确认 NUMERIC_PROPS 没漏。"""
    for lab in ["individual", "sample", "study", "project", "T1", "T2", "tool",
                "format", "function", "modal", "datalevel"]:
        props = [p[0] for p in run(f"MATCH (n:`{lab}`) UNWIND keys(n) AS k "
                                   f"RETURN DISTINCT k ORDER BY k")]
        hit = []
        for p in props:
            r = run(f"MATCH (n:`{lab}`) WHERE n.`{p}` IS NOT NULL "
                    f"RETURN count(*), sum(CASE WHEN toString(n.`{p}`) =~ '{NUM_RE}' THEN 1 ELSE 0 END), "
                    f"head(collect(valueType(n.`{p}`)))")[0]
            if r[0] and r[1] / r[0] >= 0.95 and "STRING" in str(r[2]):
                hit.append(p)
        print(f"    {lab:<12} 仍是 STRING 的数值属性: {hit or '无'}")


def validate():
    print("\n  节点:", run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) ORDER BY l"))
    print("  关系:", run("MATCH ()-[r]->() RETURN type(r), count(*) ORDER BY type(r)"))
    print("  总计:", run("MATCH (n) RETURN count(n)")[0][0], "节点 /",
          run("MATCH ()-[r]->() RETURN count(r)")[0][0], "关系")
    gap = run("MATCH (t:T1) WHERE t.run_accession IS NOT NULL AND "
              "NOT (t)-[:in_sample]->() RETURN count(t)")[0][0]
    print(f"  带 run 但无 in_sample 的 T1（0819 那个 29% 缺口）: {gap}")
    print("  师兄 case:", run(
        "MATCH (t:T1)-[:in_sample]->(s:sample) WHERE t.file_name STARTS WITH 'HRR027243' "
        "RETURN t.file_name, s.sample_accession, s.tissue_type"))


def preflight():
    bad = []
    for rel, lab, key in ENTITIES:
        hdr = next(csv.reader(open(os.path.join(DATA, rel), encoding="utf-8-sig")))
        hdr = [h.strip().lstrip("﻿") for h in hdr]
        if key not in hdr:
            bad.append(f"{rel} 缺主键列 {key}")
    for rel, la, ca, pa, rt, lb, cb, pb in RELATIONS:
        hdr = next(csv.reader(open(os.path.join(DATA, rel), encoding="utf-8-sig")))
        hdr = [h.strip().lstrip("﻿") for h in hdr]
        for c in (ca, cb):
            if c not in hdr:
                bad.append(f"{rel} 缺列 {c}")
    n = {rel: sum(1 for _ in rows(rel)) for rel, *_ in ENTITIES}
    print("  CSV 预检:", "❌ " + "; ".join(bad) if bad else "✅ 列名全对得上")
    print("  实体行数:", n)
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backup-only", action="store_true")
    ap.add_argument("--normalize-only", action="store_true",
                    help="不重灌，只对现有库跑归一化（幂等，可重复执行）")
    ap.add_argument("--scan", action="store_true",
                    help="只扫描：哪些属性内容是数字却存成了 STRING")
    ap.add_argument("--backup", default="/tmp/neo4j_backup_before_0821.jsonl")
    a = ap.parse_args()
    if not PWD:
        sys.exit("需要 NEO4J_PASSWORD")
    print(f"目标: {URL}\n数据: {DATA}\n")
    if a.scan:
        scan_numeric()
        return
    if a.normalize_only:
        print("归一化（不动拓扑，只改属性类型/删撞车孤儿/重建冗余列）")
        normalize()
        return
    ok = preflight()
    if a.dry_run:
        return
    if not ok:
        sys.exit("预检未过，拒绝写库")
    print("\n[1/6] 备份现网")
    backup(a.backup)
    if a.backup_only:
        return
    if not a.go:
        sys.exit("\n未加 --go，到此为止（已备份，未改动任何数据）")
    t0 = time.time()
    print("\n[2/6] 清库"); clear()
    print("\n[3/6] 建约束/索引"); schema()
    print("\n[4/6] 灌数据"); load_reference(); load_entities(); load_relations()
    # 归一化必须在灌完之后：CSV 每个格子都是字符串，不修的话生存/TMB/data_level/
    # sample_count 这些字段一律按字典序比较，静默给错答案。别把它当可选步骤。
    print("\n[5/6] 归一化"); normalize()
    print(f"\n[6/6] 校验（重建用时 {time.time()-t0:.0f}s）"); validate()


if __name__ == "__main__":
    main()
