#!/usr/bin/env python3
"""从知识卡片补 io_slot.csv 的 builder_param / wdl_target。

槽名是语义制品名（sample_metainfo / clinical_table / tabular_bio_data），卡片参数名
是 WDL 本地名（metainfo_xlsx / clinical_xls / expr），两套词表不重叠——所以不能按
字面 join。已填好的 12 个工具走的是**角色对应**：

    sample_metainfo -> metainfo_xlsx | metainfo_file | meta_xlsx
    clinical_table  -> clinical_xls  | clinical_file
    count_matrix    -> counts_tsv    | count_tsv
    somatic_maf     -> maf | maf_file

本脚本把这条既成约定机械化，并且**只在双射成立时才落**：工具的每个必需输入槽都能
唯一对上一个必需文件参数，且没有必需文件参数落空。任何一边多出来就整个工具退回人工
——多出来的那一边本身就是线索（槽表少建了槽，或者槽表建了 WDL 根本不收的输入）。

不做部分填充：半填的工具比全空的工具更难发现问题。
"""
import csv, json, re, sys
from pathlib import Path

import yaml

IO_SLOT = Path(__file__).resolve().parents[2] / "data/csv/catalog/io_slot.csv"
CARD_ROOTS = [Path("/tmp/gd"), Path("/tmp/wf/workflow")]   # 归档(08-20) 优先于 workflow(07-26)
APPLY = "--apply" in sys.argv

FIELDS = ("identity,labels,catalog_source,description,direction,one_of_group,required,"
          "slot_id,slot_name,tool_id,artifact,wdl_type,dimension,dimension_value,"
          "variant,variant_alias_for,builder_param,wdl_target").split(",")

# 角色词表。顺序即优先级：clinical 要排在 expr 前面（clinical_matrix 是临床表不是表达谱），
# meta 要排在 expr 前面（sample_metadata 不是表达矩阵）。
ROLES = [
    ("maf",      r"maf"),
    ("clinical", r"clinical"),
    ("meta",     r"meta(info|data)?|sample_?info"),
    ("rds",      r"\brds\b|seurat|_object\b|^input_rds$"),
    ("fastq",    r"fastq|read[12]\b|_r[12]\b"),
    ("bam",      r"\bbam\b|\bbai\b|\bcram\b"),
    ("vcf",      r"\bvcf\b"),
    ("interval", r"interval|\bbed\b"),
    ("ref",      r"\bgtf\b|genome|fasta|annotation|index|reference|\bref\b"),
    ("expr",     r"expr|count|tpm|fpkm|matrix|abundance|quant"),
]
SLOT_ROLES = [
    ("maf",      r"maf"),
    ("clinical", r"clinical"),
    ("meta",     r"meta(info|data)?|sample_?info"),
    ("rds",      r"\brds\b|seurat|_object"),
    ("fastq",    r"fastq|_r[12]$|^fastq_[12]$|tumor_r[12]|normal_r[12]"),
    ("bam",      r"\bbam\b|\bbai\b"),
    ("vcf",      r"\bvcf\b"),
    ("interval", r"interval|\bbed\b"),
    ("ref",      r"genome_annotation|\bgtf\b|genome|fasta|index|reference"),
    ("expr",     r"tabular_bio_data|count|tpm|expression|matrix"),
]


def role_of(name, table):
    n = str(name or "").lower()
    for role, pat in table:
        if re.search(pat, n):
            return role
    return None


def load_cards():
    """按 meta.id **和**目录名两个键索引——原子工具的 tool_id 是 `bwa`，
    卡片里的 meta.id 却是 `bwa_mem_paired`，只认一个键会漏掉 9 个工具。"""
    cards = {}
    for root in reversed(CARD_ROOTS):
        for p in sorted(root.rglob("knowledge_card.yaml")):
            if "__MACOSX" in str(p):
                continue
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                continue
            for key in {str((doc.get("meta") or {}).get("id") or ""), p.parent.name}:
                if key:
                    cards[key] = doc
    return cards


def card_file_params(doc):
    """卡片里代表"一个文件输入"的参数。数组型单列——它对应几个槽是人说了算。"""
    single, arrays = [], []
    for p in ((doc.get("interface") or {}).get("params") or []):
        if not isinstance(p, dict) or not p.get("target"):
            continue
        t = str(p.get("type") or "").lower().strip()
        if t == "file":
            single.append(p)
        elif t.startswith("array"):
            desc = str(p.get("description") or "") + str(p.get("name") or "")
            if re.search(r"文件|路径|file|path|bam|fastq|tsv|csv|vcf", desc, re.I):
                arrays.append(p)
    return single, arrays


def main():
    rows = list(csv.DictReader(IO_SLOT.open(encoding="utf-8-sig")))
    cards = load_cards()

    by_tool = {}
    for r in rows:
        by_tool.setdefault(r["tool_id"], []).append(r)

    filled, manual = [], []

    for tool, trows in sorted(by_tool.items()):
        empty_ins = [r for r in trows if r["direction"] == "input"
                     and not (r["builder_param"] or "").strip()]
        if not empty_ins:
            continue
        doc = cards.get(tool)
        if not doc:
            manual.append({"tool_id": tool, "原因": "找不到知识卡片",
                           "槽": [r["slot_name"] for r in empty_ins]})
            continue
        single, arrays = card_file_params(doc)
        req_params = [p for p in single if p.get("required") is True]
        req_slots = [r for r in empty_ins if str(r["required"]).lower() == "true"]

        if arrays:
            manual.append({"tool_id": tool, "原因": "卡片有数组型文件参数，一个参数对几个槽要人定",
                           "槽": [r["slot_name"] for r in empty_ins],
                           "数组参数": [f"{p['name']}:{p.get('type')}" for p in arrays],
                           "单文件参数": [str(p["name"]) for p in single]})
            continue

        # 按角色配对，只认唯一命中
        pairs, why = {}, None
        used = set()
        for r in req_slots:
            srole = role_of(r["slot_name"], SLOT_ROLES) or role_of(r["description"], SLOT_ROLES)
            cands = [p for p in req_params
                     if str(p["name"]) not in used and role_of(p["name"], ROLES) == srole]
            if srole is None:
                why = f"槽 {r['slot_name']} 归不出角色"; break
            if len(cands) != 1:
                why = (f"槽 {r['slot_name']}(角色={srole}) 对上 {len(cands)} 个必需参数"
                       f"{[str(c['name']) for c in cands]}"); break
            pairs[r["slot_id"]] = cands[0]
            used.add(str(cands[0]["name"]))

        leftover = [str(p["name"]) for p in req_params if str(p["name"]) not in used]
        if why is None and leftover:
            why = f"卡片必需参数 {leftover} 在槽表里没有对应的槽（槽表缺槽）"

        # 同角色还有可选文件参数没处安放 —— 说明这一个槽其实代表多个文件。
        # trim_galore 就是这样：一个 raw_fastq_read 槽，卡片 read1 必需、read2 可选，
        # 只落 read1 会让双端的 R2 静默消失，回包字段却是满的。
        if why is None:
            spare = [str(p["name"]) for p in single
                     if p.get("required") is not True
                     and role_of(p["name"], ROLES) in {role_of(k["name"], ROLES)
                                                       for k in pairs.values()}]
            if spare:
                why = (f"同角色还剩可选文件参数 {spare} 无槽可放，"
                       f"一个槽实际代表多个文件（如双端 R1/R2）")

        if why is not None:
            manual.append({
                "tool_id": tool, "原因": why,
                "槽": [{"slot_name": r["slot_name"], "required": r["required"],
                        "artifact": r["artifact"],
                        "角色": role_of(r["slot_name"], SLOT_ROLES)
                                or role_of(r["description"], SLOT_ROLES)}
                       for r in empty_ins],
                "卡片必需文件参数": [{"name": str(p["name"]), "target": str(p["target"]),
                                    "角色": role_of(p["name"], ROLES),
                                    "说明": str(p.get("description") or "")[:60]}
                                   for p in req_params],
                "卡片可选文件参数": [str(p["name"]) for p in single
                                   if p.get("required") is not True],
            })
            continue

        for r in empty_ins:
            p = pairs.get(r["slot_id"])
            if p:
                r["builder_param"] = str(p["name"])
                r["wdl_target"] = str(p["target"])
                filled.append((tool, r["slot_name"], str(p["name"]), str(p["target"])))

    print(f"{'【已应用】' if APPLY else '【干跑，未写盘】'}  可填 {len(filled)} 条 / "
          f"待人工 {len(manual)} 个工具")
    cur = None
    for t, s, b, w in filled:
        if t != cur:
            cur = t; print(f"\n  {t}")
        print(f"     {s:<24} -> {b:<22} {w}")
    print("\n" + "=" * 74)
    for m in manual:
        print(f"  {m['tool_id']:<30} {m['原因']}")

    if APPLY:
        with IO_SLOT.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader(); w.writerows(rows)
    Path("/tmp/manual_review.json").write_text(
        json.dumps(manual, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
