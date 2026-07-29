#!/usr/bin/env python3
"""用 DeepSeek API 实跑 96 例 benchmark。
数据评分口径：预测文件集合 == 标准文件集合（多一个少一个都算错）。
"""
import os, sys, json, warnings, re, time
warnings.filterwarnings("ignore")

os.environ["FORCE_RULE"] = "0"
os.environ["LLM_MODE"] = "api"
if not (os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")):
    raise RuntimeError("Set LLM_API_KEY or DEEPSEEK_API_KEY before running the benchmark")
os.environ.setdefault("LLM_BASE_URL", "https://api.deepseek.com/chat/completions")
os.environ.setdefault("LLM_MODEL", "deepseek-v4-pro")
os.environ.setdefault("LLM_TIMEOUT", "60")
os.environ["LLM_TIMEOUT"] = "60"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openpyxl
from pipeline_router import route_pipeline_request

BENCH = "/Users/zhouyiran/data/progress/0709/incoming/96例问题-数据-工具对应表.xlsx"

def norm_files(cell):
    if not cell:
        return set()
    parts = re.split(r"[\n;,]+", str(cell))
    return {p.strip() for p in parts if p.strip()}

def pred_file_set(result):
    data = result.get("matched_data") or {}
    files = data.get("file_candidates") or []
    return {str(f.get("files")).strip() for f in files if f.get("files")}

wb = openpyxl.load_workbook(BENCH, read_only=True, data_only=True)
ws = wb["Sheet1"]
rows = [r for r in list(ws.iter_rows(values_only=True))[1:] if r[1]]
wb.close()

n = len(rows)
top1_ok = top3_ok = data_exact = data_any = e2e = 0
llm_used = 0
records = []

for i, r in enumerate(rows, 1):
    q, gold_data, gold_tool = r[1], r[2], r[3]
    gold_tools = norm_files(gold_tool)      # 有的题多工具
    gold_primary = list(gold_tools)[0] if gold_tools else str(gold_tool).strip()
    gold_fset = norm_files(gold_data)

    try:
        res = route_pipeline_request(q, top_k=5)["result"]
    except Exception as e:
        res = {"matched_pipelines": [], "matched_data": {}, "llm_metadata": {}}
        print(f"[{i}] ERROR {type(e).__name__}: {e}", flush=True)

    mp = res.get("matched_pipelines") or []
    pred_ids = [p["pipeline_id"] for p in mp]
    pred_top1 = pred_ids[0] if pred_ids else None
    if (res.get("llm_metadata") or {}).get("used"):
        llm_used += 1

    t1 = pred_top1 in gold_tools if gold_tools else False
    t3 = bool(gold_tools & set(pred_ids[:3]))
    pf = pred_file_set(res)
    d_exact = (pf == gold_fset) and bool(gold_fset)
    d_any = bool(pf & gold_fset)

    top1_ok += t1; top3_ok += t3; data_exact += d_exact; data_any += d_any
    if t1 and d_exact: e2e += 1

    records.append({
        "idx": i, "q": q, "gold_tool": gold_primary, "pred_top1": pred_top1,
        "pred_top3": pred_ids[:3], "top1": t1, "top3": t3,
        "gold_files": sorted(gold_fset), "pred_files": sorted(pf),
        "data_exact": d_exact,
    })
    mark = "✓" if t1 else "✗"
    dmark = "✓" if d_exact else "✗"
    print(f"[{i:>2}/{n}] tool{mark} data{dmark}  gold={gold_primary:<32} pred={pred_top1}", flush=True)

print("\n" + "="*60)
print(f"样本数: {n}   LLM 实际生效: {llm_used}/{n}")
print(f"Pipeline Top1 Accuracy : {top1_ok}/{n} = {top1_ok/n*100:.2f}%")
print(f"Pipeline Top3 Recall   : {top3_ok}/{n} = {top3_ok/n*100:.2f}%")
print(f"Data 精确匹配(多一少一算错): {data_exact}/{n} = {data_exact/n*100:.2f}%")
print(f"Data Any-file 命中     : {data_any}/{n} = {data_any/n*100:.2f}%")
print(f"End-to-end(Top1且数据精确): {e2e}/{n} = {e2e/n*100:.2f}%")

with open("bench_deepseek_result.json", "w", encoding="utf-8") as f:
    json.dump({"n": n, "llm_used": llm_used, "top1": top1_ok, "top3": top3_ok,
               "data_exact": data_exact, "data_any": data_any, "e2e": e2e,
               "records": records}, f, ensure_ascii=False, indent=2)
print("明细已写入 bench_deepseek_result.json")
