"""D9: Generate a single-page fact sheet for demo day."""
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline_router import assess_feasibility, CsvKGDataMatcher, PIPELINE_DATA_PROFILE_KEYS, _role_of_file
from workflow_composer import WorkflowComposer, RegisteredMethodCatalog

CSV_DIR = REPO / "data" / "csv"
LATENCY_PATH = REPO / "docs" / "a2_latency_probe.json"
OUT_PATH = REPO / "docs" / "demo_facts.md"


def load_csv(name):
    # T11 lives at data/csv/T11.csv; most entity tables live under data/csv/entities/
    if name == "T11.csv":
        path = CSV_DIR / "T11.csv"
    else:
        path = CSV_DIR / "entities" / name
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def count_rows(name):
    return len(load_csv(name))


def neo4j_catalog_stats():
    cat = RegisteredMethodCatalog()
    data = sum(1 for _ in cat.data_edges)
    order = sum(1 for e in cat.next_edges if e not in {(s, t) for s, _, t, _ in cat.data_edges})
    return {
        "atomic_tools": len(cat.methods),
        "pipeline_tools": len(cat.pipeline_methods),
        "total_tools": len(cat.all_methods),
        "data_next_edges": data,
        "order_next_edges": order,
        "connected": cat.connected,
        "error": cat.error,
    }


def data_stats():
    studies = load_csv("study.csv")
    individuals = load_csv("individual.csv")
    samples = load_csv("sample.csv")
    t1 = load_csv("T1.csv")
    t11 = load_csv("T11.csv")
    t2 = load_csv("T2.csv")

    strategies = Counter(r.get("strategy", "") for r in t1)
    # T1 has no format column; formats come from T11. Aggregate T11 formats weighted by T1 rows would require join.
    t11_formats = Counter(r.get("format", "") for r in t11)

    # T1 uses camelCase columns; T11 uses snake_case. Match by study+run+filename.
    t1_keys = set()
    for r in t1:
        key = (r.get("studyAccession"), r.get("runAccession"), r.get("dataName"))
        t1_keys.add(key)
    t11_invisible = []
    for r in t11:
        key = (r.get("study_accession"), r.get("run_accession"), r.get("files"))
        if key not in t1_keys:
            t11_invisible.append(r)

    invisible_by_study = Counter(r.get("study_accession", "") for r in t11_invisible)
    invisible_by_format = Counter(r.get("format", "") for r in t11_invisible)

    return {
        "studies": len(studies),
        "individuals": len(individuals),
        "samples": len(samples),
        "t1_files": len(t1),
        "t11_files": len(t11),
        "t2_files": len(t2),
        "t1_strategies": dict(strategies),
        "t11_formats": dict(t11_formats),
        "t11_invisible": len(t11_invisible),
        "t11_invisible_by_study": dict(invisible_by_study),
        "t11_invisible_by_format": dict(invisible_by_format),
    }


def format_mislabel_scan():
    t11 = load_csv("T11.csv")
    t2 = load_csv("T2.csv")
    contradictions = []

    def check(rows, source, study_field="study_accession"):
        for r in rows:
            # Skip directory entries in T2
            if r.get("file_type", "").upper() == "DIR" or r.get("files", "").endswith("-files"):
                continue
            fmt = (r.get("format") or "").lower()
            fname = (r.get("files") or "").lower()
            if fmt == "maf" and not fname.endswith((".maf", ".maf.gz")):
                contradictions.append({"source": source, "file": r.get("files"), "format": fmt, "study": r.get(study_field)})
            if fmt == "bam" and not fname.endswith((".bam", ".bai")):
                contradictions.append({"source": source, "file": r.get("files"), "format": fmt, "study": r.get(study_field)})
            if fmt in ("vcf", "gvcf") and not fname.endswith((".vcf", ".vcf.gz", ".gvcf", ".gvcf.gz")):
                contradictions.append({"source": source, "file": r.get("files"), "format": fmt, "study": r.get(study_field)})

    check(t11, "T11")
    check(t2, "T2")
    return contradictions


def pipeline_coverage():
    # 使用 CsvKGDataMatcher 合并后的记录（T1 标准化记录 + T2 处理后数据）。
    # 这样 assess_feasibility 才能拿到 individual_accession、specimen_types 等
    # 由 _load_normalized_t1 补全的字段，否则 wes_somatic_pair 等配对流程会被误报为 0。
    matcher = CsvKGDataMatcher(CSV_DIR)
    records = list(matcher.t1) + list(matcher.t2)
    by_study = defaultdict(list)
    for r in records:
        r["input_role"] = _role_of_file(r)
        by_study[r.get("study_accession", "")].append(r)

    studies = sorted(s for s in by_study if s)
    pipelines = sorted(PIPELINE_DATA_PROFILE_KEYS.keys())
    rows = []
    for study in studies:
        for pid in pipelines:
            result = assess_feasibility(pid, by_study[study])
            rows.append({
                "study": study,
                "pipeline": pid,
                "feasible": result.get("ok", False),
                "reason": result.get("message", ""),
            })
    return rows


def token_costs():
    if not LATENCY_PATH.exists():
        return {}
    data = json.loads(LATENCY_PATH.read_text(encoding="utf-8"))
    result = {}
    for label, item in data.items():
        toks = [r.get("llm_tokens") for r in item.get("runs", []) if r.get("llm_tokens")]
        if toks:
            avg = sum(toks) / len(toks)
            # deepseek-v4-pro pricing placeholder: input ~0.07 USD/M, output ~0.30 USD/M
            # tokens reported are total; rough cost = avg * 0.0001 USD
            result[label] = {
                "avg_tokens": round(avg, 0),
                "estimated_cost_usd": round(avg * 0.0001, 4),
            }
    return result


def main():
    print("gathering catalog stats...")
    catalog = neo4j_catalog_stats()
    print("gathering data stats...")
    data = data_stats()
    print("scanning format labels...")
    contradictions = format_mislabel_scan()
    print("computing pipeline coverage...")
    coverage = pipeline_coverage()
    print("loading latency/token data...")
    costs = token_costs()

    feasible_count = sum(1 for r in coverage if r["feasible"])
    total_cells = len(coverage)

    by_pipeline = defaultdict(list)
    by_study = defaultdict(list)
    for r in coverage:
        by_pipeline[r["pipeline"]].append(r)
        by_study[r["study"]].append(r)

    pipeline_summary = []
    for pid in sorted(by_pipeline):
        rows = by_pipeline[pid]
        feasible = sum(1 for r in rows if r["feasible"])
        pipeline_summary.append({"pipeline": pid, "studies": len(rows), "feasible_studies": feasible})

    zero_coverage = [p["pipeline"] for p in pipeline_summary if p["feasible_studies"] == 0]

    lines = []
    lines.append("# Demo 事实清单（现跑）\n")
    lines.append(f"生成时间：{os.popen('date -u +%Y-%m-%dT%H:%M:%SZ').read().strip()}\n")

    lines.append("## 1. Neo4j 工具目录\n")
    lines.append(f"- atomic 工具数：{catalog['atomic_tools']}")
    lines.append(f"- pipeline/task_pipeline 数：{catalog['pipeline_tools']}")
    lines.append(f"- 工具节点总数：{catalog['total_tools']}")
    lines.append(f"- NEXT data 边：{catalog['data_next_edges']}")
    lines.append(f"- NEXT order 边：{catalog['order_next_edges']}")
    lines.append(f"- Neo4j 连接状态：{'connected' if catalog['connected'] else 'ERROR ' + str(catalog['error'])}")
    lines.append("")

    lines.append("## 2. CSV 数据规模\n")
    lines.append(f"- study 数：{data['studies']}")
    lines.append(f"- individual 数：{data['individuals']}")
    lines.append(f"- sample 数：{data['samples']}")
    lines.append(f"- T1 文件数：{data['t1_files']}")
    lines.append(f"- T11 文件数：{data['t11_files']}")
    lines.append(f"- T2 文件数：{data['t2_files']}")
    lines.append(f"- T1 strategy 分布：{json.dumps(data['t1_strategies'], ensure_ascii=False)}")
    lines.append(f"- T1 无 format 列；T11 format 分布：{json.dumps(data['t11_formats'], ensure_ascii=False)}")
    lines.append("")

    lines.append("## 3. T11 不可见记录\n")
    lines.append(f"- T11 中未被 T1 覆盖：{data['t11_invisible']} 条")
    lines.append(f"- 按 study：{json.dumps(data['t11_invisible_by_study'], ensure_ascii=False)}")
    lines.append(f"- 按 format：{json.dumps(data['t11_invisible_by_format'], ensure_ascii=False)}")
    lines.append("")

    lines.append("## 4. 格式/角色标注疑似矛盾\n")
    lines.append(f"- 扫描到矛盾项：{len(contradictions)}")
    for c in contradictions[:20]:
        lines.append(f"  - [{c['source']}] {c['study']} | format={c['format']} | {c['file']}")
    if len(contradictions) > 20:
        lines.append(f"  - ... 共 {len(contradictions)} 条，详见 docs/format_mislabels.json")
    lines.append("")

    lines.append("## 5. Study × Pipeline 真值表摘要\n")
    lines.append(f"- 总格数：{total_cells}")
    lines.append(f"- 系统判定可行：{feasible_count}")
    lines.append(f"- 系统判定不可行：{total_cells - feasible_count}")
    lines.append("")

    lines.append("## 6. Pipeline 覆盖率\n")
    lines.append("| pipeline | 涉及 study 数 | 可行 study 数 |")
    lines.append("|---|---|---|")
    for p in pipeline_summary:
        lines.append(f"| {p['pipeline']} | {p['studies']} | {p['feasible_studies']} |")
    lines.append("")

    lines.append("## 7. 零覆盖 Pipeline\n")
    if zero_coverage:
        lines.append("- " + "\n- ".join(zero_coverage))
    else:
        lines.append("- 无")
    lines.append("")

    lines.append("## 8. 演示查询 Token 与成本估算\n")
    lines.append("| 查询 | 平均 tokens | 估算成本 USD |")
    lines.append("|---|---|---|")
    for label, c in costs.items():
        lines.append(f"| {label} | {c['avg_tokens']} | {c['estimated_cost_usd']} |")
    lines.append("")

    lines.append("## 9. 原始覆盖明细（前 30 条）\n")
    lines.append("| study | pipeline | feasible | reason |")
    lines.append("|---|---|---|---|")
    for r in coverage[:30]:
        lines.append(f"| {r['study']} | {r['pipeline']} | {r['feasible']} | {r['reason'][:60]} |")
    lines.append("")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"saved {OUT_PATH}")

    # Save contradictions as JSON for reference
    (REPO / "docs" / "format_mislabels.json").write_text(
        json.dumps(contradictions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
