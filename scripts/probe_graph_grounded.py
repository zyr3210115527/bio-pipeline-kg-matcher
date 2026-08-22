#!/usr/bin/env python3
"""接上图谱之后才跑得了的一组题：期望值全部从图里查出来，不靠猜。

前面三个探针（probe_30_prompts / probe_robustness / probe_privacy_and_kind）都是在
图谱断线时写的，凡是"这个队列有没有这类数据"的断言当时都无从核实。0822 图谱接上
（80,679 节点 / 352,468 关系 / 51 个工具，与生产库逐项对上）之后，这批题才有意义。

每条题的期望不是"我觉得应该"，而是先查图：

    MATCH (t:T2) WHERE toLower(t.file_name) =~ '.*(fpkm|tpm|count|matrix).*'
    RETURN t.study_accession, count(*)

查出来 14 个队列有表达矩阵（HRA000073/74/87/122、HRA001272、HRA002693、HRA003107、
HRA006117、HRA007167、HRA007413），HRA000001 和 HRA000021 只有 WGS 的 BQSR.bam，
一张矩阵都没有。scRNA 的 h5 只在 HRA001748 和 HRA005191。MAF 只在
HRA000873/001272/001749/006499/007169/016026。

因此正反两面都能真判：

* G 有数据。点名的队列确实有这个模态，必须绑到数据，且资产要带得出样本归属。
* N 没这个模态。队列在、但这类文件图里没有，必须说没有——**不许拿同队列里别的
  模态顶上**。这是最容易"错得像对"的一类：回包结构完整、路径真实存在、只是文件
  根本不是用户要的东西。
* X 跨队列污染。点名 A 队列，返回的资产里不许混进 B 队列的文件。
* L 样本归属。师兄 0821 那条 null 的直接回归：可用资产必须给得出 sample/run 编号。

用法：
    python3 scripts/probe_graph_grounded.py
    python3 scripts/probe_graph_grounded.py --only N
    python3 scripts/probe_graph_grounded.py --output docs/graph0822/graph_grounded.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REFUSAL = {"unsupported", "no_candidate"}
STUDY_TOKEN = re.compile(r"HRA\d{6}")
SAMPLE_TOKEN = re.compile(r"HR[SRI]\d+")

# 声明了 rds 输入槽的 9 条流程。查法（不是猜的）：
#   catalog/relationships.csv 里 ALLOW_FORMAT -> catalog_format:rds 的 io_slot，
#   再沿 HAS_INPUT_SLOT 反查 tool_id。
# 图里 18 种 format 一个 rds/Seurat 对象都没有（单细胞只有 SCRNA_MATRIX_H5 403 个
# 和 SCRNA_MATRIX_H5_ZIP 2 个），所以这 9 条在当前图谱上永远填不满输入槽。
# 这本身是给师兄的数据质量问题，不是代码 bug；这里只负责钉住"不许假装填得上"。
RDS_ONLY_PIPELINES = [
    "breast_cellchat",
    "celltype_case_control_de",
    "dataset_downstream",
    "dataset_matrix_annotation",
    "immunotherapy_cellchat",
    "ipf_trajectory_regulon",
    "lung_tme_annotation_cnv",
    "scrna_cell_communication",
    "tcell_intervention",
]


def case(cid: str, group: str, prompt: str, **expect: Any) -> Dict[str, Any]:
    return {"case_id": cid, "group": group, "prompt": prompt, "expect": expect}


# expect 支持的键：
#   study            题面点名的队列；用于跨队列污染检查
#   data_available   True 表示必须有推荐绑到 available 数据
#   modality_absent  True 表示图里没有这个模态，不许报 available
#   slot_unsatisfied 图里有"看着像"的文件，但流程声明的输入槽位它填不上；
#                    必须说填不上，不许松绑成 available（详见 G04-G07 注释）。
#                    True = 整题都不许报 available；给一串 pipeline_id = 只锁这几条。
#   attribution      True 表示可用资产必须带 sample/run 编号（师兄那条 null 的回归）
#   refuse           True 表示必须落在 REFUSAL
#   no_cross_study   True 表示资产不得混入别的队列
CASES: List[Dict[str, Any]] = [
    # ---- G. 图里确实有这个模态：必须绑到数据 ----
    case("G01", "G", "用 HRA001272 的基因表达矩阵做差异表达分析",
         study="HRA001272", data_available=True, attribution=True, no_cross_study=True),
    case("G02", "G", "HRA003107 的表达矩阵做无监督聚类分型",
         study="HRA003107", data_available=True, no_cross_study=True),
    case("G03", "G", "拿 HRA000873 的 MAF 文件做突变景观分析",
         study="HRA000873", data_available=True, attribution=True, no_cross_study=True),

    # ---- G04-G07：初版把这四条写成了 data_available=True，跑出来"失败"，
    # 查下去发现**是期望错了，不是产品错了**。改成锁真正的不变量：槽位填不上时
    # 必须说填不上。这四条的共同形状是"图里有看着像的文件，但不是流程要的东西"——
    # 恰恰是最容易被松绑掉的一类，所以留着比删掉有用。
    #
    # G04/G05：图里单细胞只有 SCRNA_MATRIX_H5（403 个）和 SCRNA_MATRIX_H5_ZIP（2 个），
    # 一个 rds/Seurat 对象都没有；而下列 9 条流程声明的输入槽是 scrna_object_rds
    # （catalog/relationships.csv 里 ALLOW_FORMAT -> catalog_format:rds 查得）。
    # h5 矩阵和 Seurat 对象不是一回事（后者带聚类、降维、注释结果），拿 h5 顶上去，
    # 回包会显示"数据已就绪"，执行端才会炸。
    # 只锁这 9 条：同一道题推 cellranger_workflow 绑 FASTQ 是对的，它声明的输入
    # 本来就是 FASTQ，两个队列也确实有 scRNA FASTQ。
    case("G04", "G", "HRA001748 的单细胞表达矩阵做细胞类型注释",
         study="HRA001748", slot_unsatisfied=RDS_ONLY_PIPELINES, no_cross_study=True),
    case("G05", "G", "用 HRA005191 的单细胞数据做降维聚类",
         study="HRA005191", slot_unsatisfied=RDS_ONLY_PIPELINES, no_cross_study=True),
    # G06：HRA000021 的 T2 只有 DNA_ALIGNMENT_BQSR_BAM(1016) 和 _INDEX_BAI(1016)，
    # 没有 TABULAR_BIO_DATA；cnvkit_cnv_clinical 同时要 clinical_table 和
    # tabular_bio_data。BAM 在，另外两个槽填不上，就不能报 available。
    case("G06", "G", "HRA000021 的 BAM 文件做拷贝数变异检测",
         study="HRA000021", slot_unsatisfied=True, no_cross_study=True),
    # G07：VCF 注释要走 GATK -> BCFtools -> SnpEff，而这条路径在"当前目录/执行合同的
    # 已知边界"里被显式禁掉了（Knowledge Card 传不了 VCF+index 槽位）。拒答是对的。
    case("G07", "G", "用 HRA006499 的 VCF 做变异注释",
         study="HRA006499", slot_unsatisfied=True, no_cross_study=True),

    case("G08", "G", "HRA002693 的表达矩阵做免疫浸润分析",
         study="HRA002693", data_available=True, no_cross_study=True),

    # ---- N. 队列在，但图里没有这个模态：必须说没有，不许拿别的模态顶上 ----
    # HRA000021 / HRA000001 的 T2 只有 WGS 的 BQSR.bam + bai，一张表达矩阵都没有。
    case("N01", "N", "HRA000021 的基因表达矩阵做差异表达分析",
         study="HRA000021", modality_absent=True, no_cross_study=True),
    case("N02", "N", "用 HRA000001 的表达矩阵做 WGCNA 共表达网络",
         study="HRA000001", modality_absent=True, no_cross_study=True),
    # HRA000073 只有 bulk_RNA，没有 WES/WGS，也没有 MAF。
    case("N03", "N", "用 HRA000073 的 MAF 文件做 TMB 计算",
         study="HRA000073", modality_absent=True, no_cross_study=True),
    case("N04", "N", "HRA002693 的全外显子数据做体细胞突变检测",
         study="HRA002693", modality_absent=True, no_cross_study=True),
    # 单细胞 h5 只在 HRA001748 / HRA005191。
    case("N05", "N", "用 HRA000874 的单细胞数据做细胞通讯分析",
         modality_absent=True),
    case("N06", "N", "HRA006117 的单细胞矩阵做细胞类型注释",
         study="HRA006117", modality_absent=True, no_cross_study=True),
    # 队列本身不存在。
    case("N07", "N", "用 HRA888888 的 RNA-seq 数据做差异表达分析",
         refuse=True, modality_absent=True),
    case("N08", "N", "HRA000021 的单细胞数据做拟时序分析",
         study="HRA000021", modality_absent=True, no_cross_study=True),

    # ---- X. 跨队列污染：点名一个队列，别把别人的文件端出来 ----
    case("X01", "X", "只用 HRA001749 这个队列的 BAM 做变异检测，不要别的队列的数据",
         study="HRA001749", no_cross_study=True),
    case("X02", "X", "HRA007169 的 VCF 做过滤和注释",
         study="HRA007169", no_cross_study=True),
    case("X03", "X", "用 HRA016026 的 MAF 做驱动基因分析",
         study="HRA016026", no_cross_study=True),
    case("X04", "X", "HRA000071 的 BAM 做结构变异检测",
         study="HRA000071", no_cross_study=True),

    # ---- L. 样本归属：师兄 0821「数据有的是 null」的直接回归 ----
    case("L01", "L", "使用 HRA001272 的 RNA-seq 数据做差异表达和 GO 富集分析",
         study="HRA001272", data_available=True, attribution=True, no_cross_study=True),
    case("L02", "L", "HRA000873 的比对结果做体细胞突变 calling",
         study="HRA000873", attribution=True, no_cross_study=True),
    case("L03", "L", "用 HRA006499 的 BAM 做拷贝数分析，我要知道每个文件对应哪个样本",
         study="HRA006499", attribution=True, no_cross_study=True),
]


def _assets(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in result.get("recommendations") or []:
        out.extend((rec.get("data") or {}).get("assets") or [])
    return out


def judge(result: Dict[str, Any], expect: Dict[str, Any]) -> List[str]:
    problems: List[str] = []
    status = result.get("selection_status")
    recs = result.get("recommendations") or []
    assets = _assets(result)

    if expect.get("refuse") and status not in REFUSAL:
        problems.append(f"应当拒答，实际 selection_status={status}")

    if expect.get("data_available"):
        statuses = [(rec.get("data") or {}).get("status") for rec in recs]
        if not any(s == "available" for s in statuses):
            problems.append(
                f"图里确实有这个模态，却没绑到数据。各推荐 data.status={statuses}"
            )

    if expect.get("modality_absent"):
        # 关键：不是"必须拒答"，而是"不许声称有数据"。给出信息性推荐是可以的。
        for rec in recs:
            data = rec.get("data") or {}
            if data.get("status") == "available":
                names = [
                    a.get("asset_id") or a.get("name") or a.get("path")
                    for a in data.get("assets") or []
                ]
                problems.append(
                    f"图里没有这个模态，却报了 available：{rec.get('pipeline_id')} -> {names[:4]}"
                )

    if expect.get("slot_unsatisfied"):
        # 锁的不是"必须拒答"，而是"不许假装填得上"。可接受的表现有两种：
        # 报 missing_from_graph / 非 available，或者干脆拒答并说清缺哪个槽。
        # 不可接受的只有一种：报 available——那等于把 h5 当成 rds、把缺失的
        # clinical_table 当成有，回包显示"数据已就绪"，执行端才会炸。
        #
        # 值可以是 True（该题图里没有任何流程填得上，整题都不许报 available），
        # 也可以是一串 pipeline_id（只有这几条填不上，别的流程照常可用）。
        # G04/G05 走后者：0822 实测问「HRA005191 的单细胞数据做降维聚类」，
        # 系统推的是 cellranger_workflow 绑 fq.gz——这是**对的**，cellranger 的
        # 声明输入就是 FASTQ，该队列也确实有 scRNA FASTQ。初版把这两条写成
        # 全题 True，是我照着 dataset_downstream 一条流程的槽位反推期望，
        # 而没去看图里还有别的流程接得住，判错的是期望不是产品。真正要锁死的
        # 只有那 9 条声明 rds 输入槽的流程：图里 18 种格式一个 rds 都没有，
        # 它们永远填不上，谁报 available 谁就是把 h5 松绑成了 Seurat 对象。
        scope = expect["slot_unsatisfied"]
        scoped = None if scope is True else {str(p) for p in scope}
        for rec in recs:
            data = rec.get("data") or {}
            pipeline_id = rec.get("pipeline_id")
            if scoped is not None and pipeline_id not in scoped:
                continue
            if data.get("status") == "available":
                names = [
                    a.get("asset_id") or a.get("name") or a.get("path")
                    for a in data.get("assets") or []
                ]
                problems.append(
                    f"流程声明的输入槽在图里填不上，却报了 available："
                    f"{pipeline_id} -> {names[:4]}。"
                    "这是把'看着像的文件'松绑成了'流程要的文件'。"
                )
        # 说不了为什么也是问题：用户得知道是缺哪一类数据，而不是只看到一个空结果。
        reason = (
            result.get("unsupported_reason")
            or (result.get("extensions") or {}).get("atomic_candidate_unavailable_reason")
        )
        if not recs and status in REFUSAL and not str(reason or "").strip():
            problems.append("拒答了但没给任何理由，用户无从判断该补什么数据")

    if expect.get("no_cross_study") and expect.get("study"):
        want = expect["study"]
        for asset in assets:
            blob = " ".join(
                str(asset.get(key) or "")
                for key in ("asset_id", "path", "file_path", "name")
            )
            found = set(STUDY_TOKEN.findall(blob))
            if found and want not in found:
                problems.append(
                    f"资产来自别的队列：题面点名 {want}，实际 {sorted(found)} "
                    f"({asset.get('asset_id') or asset.get('name')})"
                )

    if expect.get("attribution"):
        available = [
            a for rec in recs
            if (rec.get("data") or {}).get("status") == "available"
            for a in ((rec.get("data") or {}).get("assets") or [])
        ]
        if available:
            blind = [
                a.get("asset_id") or a.get("name")
                for a in available
                if not SAMPLE_TOKEN.search(json.dumps(a, ensure_ascii=False))
            ]
            if blind:
                problems.append(
                    f"{len(blind)}/{len(available)} 个可用资产给不出样本/run 编号"
                    f"（师兄 0821 那条 null 的形状）：{blind[:4]}"
                )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="", help="只跑这些组，逗号分隔，如 G,N")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output", default="", help="逐条结果写到这个文件")
    args = parser.parse_args()

    groups = {g.strip().upper() for g in args.only.split(",") if g.strip()}
    cases = [c for c in CASES if not groups or c["group"] in groups]

    from workflow_composer import WorkflowComposer

    composer = WorkflowComposer()
    catalog = composer.registered_methods
    print(
        f"工具目录：{len(catalog.all_methods)} 个（atomic {len(catalog.methods)}），"
        f"connected={catalog.connected} error={catalog.error}"
    )
    if not catalog.all_methods:
        print(
            "!! 目录为空。这套探针的期望值全部是从图里查出来的，图谱不可达时"
            "一条都判不了——直接退出，不产出一份看着全绿的假报告。"
        )
        return 3

    records: List[Dict[str, Any]] = []
    failed = 0
    for run in range(1, args.repeat + 1):
        for item in cases:
            try:
                result = composer.plan(item["prompt"])
            except Exception as exc:  # noqa: BLE001 - 崩了本身就是结论
                print(f"[{run}] EXC  {item['case_id']} {type(exc).__name__}: {exc}")
                records.append({
                    "run": run,
                    **{k: v for k, v in item.items() if k != "expect"},
                    "problems": [f"抛出异常 {type(exc).__name__}: {exc}"],
                })
                failed += 1
                continue
            problems = judge(result, item["expect"])
            if problems:
                failed += 1
            print(
                f"[{run}] {'ok  ' if not problems else 'FAIL'} {item['case_id']} "
                f"{item['prompt'][:40]}"
            )
            print(
                f"        status={result.get('selection_status')} "
                f"rec={result.get('recommendation_count')} "
                f"cand={result.get('candidate_count')} "
                f"data={[(r.get('data') or {}).get('status') for r in result.get('recommendations') or []]}"
            )
            for problem in problems:
                print(f"        !! {problem}")
            records.append({
                "run": run,
                **{k: v for k, v in item.items() if k != "expect"},
                "expect": item["expect"],
                "status": result.get("selection_status"),
                "recommendation_count": result.get("recommendation_count"),
                "candidate_count": result.get("candidate_count"),
                "recommendations": [
                    {
                        "pipeline_id": r.get("pipeline_id"),
                        "data_status": (r.get("data") or {}).get("status"),
                        "assets": [
                            a.get("asset_id") or a.get("name")
                            for a in ((r.get("data") or {}).get("assets") or [])[:6]
                        ],
                    }
                    for r in result.get("recommendations") or []
                ],
                "unsupported_reason": result.get("unsupported_reason"),
                "problems": problems,
            })

    total = len(cases) * args.repeat
    print(f"\n共 {total} 条，失败 {failed} 条。")
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"逐条结果已写入 {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
