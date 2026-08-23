"""把 io_slot.csv 的输入槽与 WDL / knowledge card 对齐（0823 第三轮）。

前两轮只做"抄参数名"：槽表说有这个槽，就去 WDL 里找同角色的参数填上。剩下的 39 个
填不上，不是因为参数名难找，是因为**槽本身是错的**——槽表是按模板批量生成的，不是按
WDL 生成的。硬证据：`dataset_downstream` 与 `dataset_matrix_annotation` 的槽集合逐字
相同（连 description 文案都一样），但两个 WDL 的 File 输入数量不同。

所以这一轮改的是槽，不是参数名。四类动作，每一类都以 knowledge card 的
`interface.params` 为准（师兄规则："参数名需要与 knowledge card 相同"）：

1. 删幽灵槽——card 里根本没有对应的 `type: file` 参数。留着它们的代价不是报错，是
   `required=true` 的槽永远匹配不上，把整条链判成数据不全；补 builder_param 更糟，
   等于给一个不存在的参数盖章。
2. 拆该拆未拆的槽——一个槽对着 WDL 的两个参数（read1/read2、fastq_file1/fastq_file2、
   rrna_star_index/genome_star_index）。风险不对称：read2 是 `File?`，漏填不报错，
   STAR / trim_galore 静默按单端跑完，结果错但一路绿灯。
3. 改命名/方向错的槽——bcftools 的输入 card 里叫 `filtered_vcf`，槽表叫 `unfiltered_vcf`，
   于是图按同名串联把 Mutect2 的**原始 VCF** 喂给 `bcftools view -f PASS`；FILTER 注记
   要 FilterMutectCalls 之后才存在，这条线不报错，只安静地给出空的 PASS 集合。
4. 加数组基数——fastqc/multiqc/cnvkit/rmats 的输入在 WDL 里是 `Array[File]+`，单文件槽
   装不下，补 builder_param 也没用。新增 `cardinality` 列。

删槽必须连带删 relationships.csv 里的 HAS_INPUT_SLOT / REQUIRES / ALLOW_FORMAT，
否则图里留下指向不存在节点的悬空边。
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "csv" / "catalog"
SLOTS = CATALOG / "io_slot.csv"
RELS = CATALOG / "relationships.csv"
TOOLS = CATALOG / "tool_id.csv"
NEXT = ROOT / "data" / "csv" / "relations" / "tool_relationship.csv"

SOURCE = "wdl-slot-reconciliation-2026-08-23"

# ---------------------------------------------------------------- 1. 删幽灵槽
# 依据：这些工具的 knowledge_card.yaml `interface.params` 里没有任何 `type: file`
# 参数与之对应。逐个核对过（见 docs/待确认_builder_param.md）。
DROP = [
    # genome_annotation：参考资源在这些 WDL 里全是 String + 容器内默认路径
    # （bwa/gatk/snpeff 的 reference_fasta、rmats 的 annotation_gtf），或者干脆是
    # `String species` / `String genome` 标签（6 个单细胞工具）。没有 File 参数。
    ("bwa", "genome_annotation"),
    ("gatk", "genome_annotation"),
    ("snpeff", "genome_annotation"),
    ("rmats_alternative_splicing", "genome_annotation"),
    ("breast_cellchat", "genome_annotation"),
    ("immunotherapy_cellchat", "genome_annotation"),
    ("celltype_case_control_de", "genome_annotation"),
    ("ipf_trajectory_regulon", "genome_annotation"),
    ("tcell_intervention", "genome_annotation"),
    ("dataset_matrix_annotation", "genome_annotation"),
    # tabular_bio_data / sample_metainfo：这 6 个单细胞工具的 File 参数只有
    # input_rds（dataset_downstream / lung_tme_annotation_cnv 多一个 gene_order，
    # 已在第二轮填过）。
    ("celltype_case_control_de", "tabular_bio_data"),
    ("dataset_downstream", "tabular_bio_data"),
    ("dataset_matrix_annotation", "tabular_bio_data"),
    ("lung_tme_annotation_cnv", "tabular_bio_data"),
    ("tcell_intervention", "tabular_bio_data"),
    ("tcell_intervention", "sample_metainfo"),
    ("ipf_trajectory_regulon", "sample_metainfo"),
    # cnvkit 的 File 参数只有 targets_bed? 和 clinical_metadata?，没有第三个表格输入。
    ("cnvkit_cnv_clinical", "tabular_bio_data"),
    # gatk 的 `single` 变体不可实现：GatkWesSomaticWorkflow 是严格 tumor-normal
    # Mutect2，四个 BAM/BAI 都是必需，没有单样本入口。card 里也没有这个参数。
    ("gatk", "sorted_dedup_bam"),
    # cellranger 的 aligned_bam 在槽表里同时是必需 input 和 output（自环）。
    # CellRangerFullPipeline 的输入里没有任何 BAM。
    ("cellranger_workflow", "aligned_bam"),
    # 下面这些是被拆掉/改名的槽，新槽在 ADD 里。
    ("star", "genome_annotation"),          # -> rrna_star_index + genome_star_index
    ("cnvkit_cnv_clinical", "aligned_bam"), # -> tumor_bams/bais + normal_bams/bais
    ("rmats_alternative_splicing", "transcriptome_bam"),  # -> group1_bams + group2_bams
]

# ------------------------------------------------- 2. 原地改（同一行改字段）
# (tool, slot) -> 要覆盖的列
PATCH = {
    # bcftools：card 的输入就叫 filtered_vcf，槽表叫 unfiltered_vcf。改名同时改绑定。
    ("bcftools", "unfiltered_vcf"): {
        "slot_name": "filtered_vcf",
        "builder_param": "filtered_vcf",
        "wdl_target": "BcftoolsSomaticPostprocessWorkflow.filtered_vcf",
        "artifact": "filtered_vcf",
        "required": "true",
        "description": "Filtered somatic VCF (FilterMutectCalls 之后)",
    },
    # rsem 的参考输入是 rsem_index（task 里按目录用 `~{rsem_index}/rsem_ref`），
    # 不是 GTF。改名 + 绑定。
    ("rsem", "genome_annotation"): {
        "slot_name": "rsem_index",
        "builder_param": "rsem_index",
        "wdl_target": "RsemQuantificationWorkflow.rsem_index",
        "description": "RSEM 索引目录",
    },
    # fastqc / multiqc：WDL 是 Array[File]+，scatter / 扇入。
    ("fastqc", "clean_fastq_read"): {
        "builder_param": "fastqs", "wdl_target": "FastQcWorkflow.fastqs",
        "wdl_type": "Array[File]+", "cardinality": "array", "required": "false",
    },
    ("fastqc", "raw_fastq_read"): {
        "builder_param": "fastqs", "wdl_target": "FastQcWorkflow.fastqs",
        "wdl_type": "Array[File]+", "cardinality": "array", "required": "false",
    },
    ("multiqc", "quality_control_report"): {
        "builder_param": "qc_files", "wdl_target": "MultiQcWorkflow.qc_files",
        "wdl_type": "Array[File]+", "cardinality": "array", "required": "true",
    },
    # cnvkit 的临床表 = clinical_metadata（File?，run_clinical_association 才用）。
    ("cnvkit_cnv_clinical", "clinical_table"): {
        "builder_param": "clinical_metadata",
        "wdl_target": "CnvkitCnvClinical.clinical_metadata",
        "required": "false",
    },
    # scrna_cell_communication：7 个 File 参数全是 File?，槽表却全标 required=true。
    # 按角色一一对应：rds 对象 -> seurat_rds；表达矩阵 -> combined_counts（h5ad，
    # card 明写"与 seurat_rds 二选一"）；元数据表 -> cell_metadata。
    # receiver_de_genes / background_expressed_genes 是基因列表，可由
    # auto_generate_receiver_inputs 生成，不建槽。
    ("scrna_cell_communication", "scrna_object_rds"): {
        "builder_param": "seurat_rds",
        "wdl_target": "ScrnaCellCommunication.seurat_rds",
        "required": "false", "wdl_type": "File?", "one_of_group": "expression_source",
    },
    ("scrna_cell_communication", "tabular_bio_data"): {
        "builder_param": "combined_counts",
        "wdl_target": "ScrnaCellCommunication.combined_counts",
        "required": "false", "wdl_type": "File?", "one_of_group": "expression_source",
    },
    ("scrna_cell_communication", "sample_metainfo"): {
        "builder_param": "cell_metadata",
        "wdl_target": "ScrnaCellCommunication.cell_metadata",
        "required": "false", "wdl_type": "File?",
    },
    # 拆分后的旧槽降级成别名行（照 bwa/fastp 的既有做法：别名行 builder_param 留空，
    # 真实槽自己上报）。
    ("star", "clean_fastq_read"): {
        "required": "false", "artifact": "clean_fastq_read",
        "dimension": "mate", "dimension_value": "r1",
        "variant_alias_for": "clean_fastq_read_r1",
    },
    ("trim_galore", "raw_fastq_read"): {
        "required": "false", "artifact": "raw_fastq_read",
        "dimension": "mate", "dimension_value": "r1",
        "variant_alias_for": "raw_fastq_read_r1",
    },
    ("cellranger_workflow", "raw_fastq_read"): {
        "required": "false",
        "dimension": "mate", "dimension_value": "r1",
        "variant_alias_for": "raw_fastq_read_r1",
    },
}

# --------------------------------------------------------------- 3. 新增槽
# (tool, direction, slot_name, required, artifact, wdl_type, dim, dim_value,
#  builder_param, wdl_target, cardinality, formats, description)
ADD = [
    # star：read1 必需 / read2 是 File?（漏填静默按单端跑）
    ("star", "input", "clean_fastq_read_r1", "true", "clean_fastq_read", "File",
     "mate", "r1", "read1", "StarRnaSeqWorkflow.read1", "", ["fq.gz"], "Clean FASTQ R1"),
    ("star", "input", "clean_fastq_read_r2", "false", "clean_fastq_read", "File?",
     "mate", "r2", "read2", "StarRnaSeqWorkflow.read2", "", ["fq.gz"], "Clean FASTQ R2"),
    # star 的两个 STAR 索引：一个 genome_annotation 槽对着两个必需 File 参数。
    # 二者都带 card 默认值，canonical role 是 reference_file，不进 execution_params
    # （师兄规则 4），建槽只为让目录表如实反映 WDL 接口。
    ("star", "input", "rrna_star_index", "true", "genome_annotation", "File",
     "", "", "rrna_star_index", "StarRnaSeqWorkflow.rrna_star_index", "",
     ["index"], "rRNA STAR 索引"),
    ("star", "input", "genome_star_index", "true", "genome_annotation", "File",
     "", "", "genome_star_index", "StarRnaSeqWorkflow.genome_star_index", "",
     ["index"], "基因组 STAR 索引"),
    # trim_galore
    ("trim_galore", "input", "raw_fastq_read_r1", "true", "raw_fastq_read", "File",
     "mate", "r1", "read1", "TrimGaloreWorkflow.read1", "", ["fq.gz"], "Raw FASTQ R1"),
    ("trim_galore", "input", "raw_fastq_read_r2", "false", "raw_fastq_read", "File?",
     "mate", "r2", "read2", "TrimGaloreWorkflow.read2", "", ["fq.gz"], "Raw FASTQ R2"),
    # trim_galore 的输出也得拆，否则 star 新拆出来的 r1/r2 在图里没有上游可连，
    # 拆了等于白拆（fastp 已经是这个形状）。
    ("trim_galore", "output", "clean_fastq_read_r1", "false", "clean_fastq_read",
     "File", "mate", "r1", "", "", "", ["fq.gz"], "Trimmed FASTQ R1"),
    ("trim_galore", "output", "clean_fastq_read_r2", "false", "clean_fastq_read",
     "File", "mate", "r2", "", "", "", ["fq.gz"], "Trimmed FASTQ R2"),
    # cellranger：fastq_file1 / fastq_file2 都是必需 File
    ("cellranger_workflow", "input", "raw_fastq_read_r1", "true", "raw_fastq_read",
     "File", "mate", "r1", "fastq_file1", "CellRangerFullPipeline.fastq_file1", "",
     ["fq.gz"], "Raw FASTQ R1"),
    ("cellranger_workflow", "input", "raw_fastq_read_r2", "true", "raw_fastq_read",
     "File", "mate", "r2", "fastq_file2", "CellRangerFullPipeline.fastq_file2", "",
     ["fq.gz"], "Raw FASTQ R2"),
    # bcftools：card 里 filtered_vcf_index 是必需 File，槽表整个漏了。
    # 缺了执行直接失败（task 里 `ln -sf` 成 .tbi 才能读）。
    ("bcftools", "input", "filtered_vcf_index", "true", "vcf_index", "File",
     "", "", "filtered_vcf_index",
     "BcftoolsSomaticPostprocessWorkflow.filtered_vcf_index", "", ["tbi"],
     "Filtered VCF 索引"),
    # gatk 的 workflow 同时输出 unfiltered_vcf 和 filtered_vcf（内部跑了
    # FilterMutectCalls），槽表只建了前者，于是图只能按 unfiltered 串联。补上后者，
    # bcftools 才有正确的上游。
    ("gatk", "output", "filtered_vcf", "false", "filtered_vcf", "File",
     "", "", "", "", "", ["vcf"], "过滤后体细胞 VCF"),
    ("gatk", "output", "filtered_vcf_index", "false", "vcf_index", "File",
     "", "", "", "", "", ["tbi"], "过滤后 VCF 索引"),
    # cnvkit：5 个等长并行数组，按同下标绑定（ValidateCnvInputs +
    # scatter(range(length(sample_ids))) 强制）。照 gatk 用 dimension=sample_role。
    ("cnvkit_cnv_clinical", "input", "tumor_bams", "true", "aligned_bam",
     "Array[File]+", "sample_role", "tumor", "tumor_bams",
     "CnvkitCnvClinical.tumor_bams", "array", ["bam"], "肿瘤 BAM 数组"),
    ("cnvkit_cnv_clinical", "input", "tumor_bais", "true", "bai",
     "Array[File]+", "sample_role", "tumor", "tumor_bais",
     "CnvkitCnvClinical.tumor_bais", "array", ["bai"], "肿瘤 BAI 数组"),
    ("cnvkit_cnv_clinical", "input", "normal_bams", "true", "aligned_bam",
     "Array[File]+", "sample_role", "normal", "normal_bams",
     "CnvkitCnvClinical.normal_bams", "array", ["bam"], "正常 BAM 数组"),
    ("cnvkit_cnv_clinical", "input", "normal_bais", "true", "bai",
     "Array[File]+", "sample_role", "normal", "normal_bais",
     "CnvkitCnvClinical.normal_bais", "array", ["bai"], "正常 BAI 数组"),
    # rmats：两组 Array[File]+，分组语义在 group1_label / group2_label 两个 String 里，
    # 槽表只表达形状，不表达"哪组是 case"——那是业务标注决定的。
    ("rmats_alternative_splicing", "input", "group1_bams", "true",
     "transcriptome_bam", "Array[File]+", "comparison_group", "group1",
     "group1_bams", "RmatsAlternativeSplicing.group1_bams", "array", ["bam"],
     "对照组 BAM 数组"),
    ("rmats_alternative_splicing", "input", "group2_bams", "true",
     "transcriptome_bam", "Array[File]+", "comparison_group", "group2",
     "group2_bams", "RmatsAlternativeSplicing.group2_bams", "array", ["bam"],
     "实验组 BAM 数组"),
    ("rmats_alternative_splicing", "input", "group1_bais", "false", "bai",
     "Array[File]", "comparison_group", "group1", "group1_bais",
     "RmatsAlternativeSplicing.group1_bais", "array", ["bai"], "对照组 BAI 数组"),
    ("rmats_alternative_splicing", "input", "group2_bais", "false", "bai",
     "Array[File]", "comparison_group", "group2", "group2_bais",
     "RmatsAlternativeSplicing.group2_bais", "array", ["bai"], "实验组 BAI 数组"),
]


def main() -> int:
    with SLOTS.open(newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if "cardinality" not in header:
        header.append("cardinality")
    for row in rows:
        row.setdefault("cardinality", "")

    dropped_ids, dropped_names = [], set()
    kept = []
    for row in rows:
        key = (row["tool_id"], row["slot_name"])
        if row["direction"] == "input" and key in DROP:
            dropped_ids.append(row["identity"])
            dropped_names.add(key)
            continue
        kept.append(row)
    missing_drop = set(DROP) - dropped_names
    if missing_drop:
        print(f"[FAIL] DROP 里有槽在表中不存在: {sorted(missing_drop)}")
        return 1

    renamed = {}
    patched = 0
    for row in kept:
        key = (row["tool_id"], row["slot_name"])
        patch = PATCH.get(key)
        if not patch or row["direction"] != "input":
            continue
        old_identity = row["identity"]
        row.update(patch)
        row["catalog_source"] = SOURCE
        row["slot_id"] = f"{row['tool_id']}::input::{row['slot_name']}"
        row["identity"] = f"io_slot:{row['slot_id']}"
        if row["identity"] != old_identity:
            renamed[old_identity] = row["identity"]
        patched += 1
    if patched != len(PATCH):
        print(f"[FAIL] PATCH 命中 {patched} 条，期望 {len(PATCH)} 条")
        return 1

    existing = {r["identity"] for r in kept}
    added_edges = []
    for (tool, direction, name, required, artifact, wdl_type, dim, dim_value,
         bp, target, cardinality, formats, desc) in ADD:
        slot_id = f"{tool}::{direction}::{name}"
        identity = f"io_slot:{slot_id}"
        if identity in existing:
            print(f"[FAIL] 新增槽已存在: {identity}")
            return 1
        kept.append({
            "identity": identity, "labels": "IOSlot|io_slot",
            "catalog_source": SOURCE, "description": desc, "direction": direction,
            "one_of_group": "", "required": required, "slot_id": slot_id,
            "slot_name": name, "tool_id": tool, "artifact": artifact,
            "wdl_type": wdl_type, "dimension": dim, "dimension_value": dim_value,
            "variant": "", "variant_alias_for": "", "builder_param": bp,
            "wdl_target": target, "cardinality": cardinality,
        })
        edge = "HAS_INPUT_SLOT" if direction == "input" else "HAS_OUTPUT_SLOT"
        added_edges.append((edge, f"tool_id:{tool}", identity))
        if artifact:
            rel = "REQUIRES" if direction == "input" else "PRODUCES"
            added_edges.append((rel, identity, f"artifact_type:{artifact}"))
        for fmt in formats:
            added_edges.append(("ALLOW_FORMAT", identity, f"catalog_format:{fmt}"))

    kept.sort(key=lambda r: (r["tool_id"], r["direction"], r["slot_name"]))
    with SLOTS.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept)

    # --- relationships.csv：删悬空边、改名、加新边
    with RELS.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rel_header = list(reader.fieldnames or [])
        rel_rows = list(reader)
    dead = set(dropped_ids)
    rel_kept = []
    removed_edges = 0
    for row in rel_rows:
        if row["start"] in dead or row["end"] in dead:
            removed_edges += 1
            continue
        row["start"] = renamed.get(row["start"], row["start"])
        row["end"] = renamed.get(row["end"], row["end"])
        rel_kept.append(row)
    have = {(r["type"], r["start"], r["end"]) for r in rel_kept}
    new_edges = 0
    for etype, start, end in added_edges:
        if (etype, start, end) in have:
            continue
        rel_kept.append({"type": etype, "start": start, "end": end,
                         "properties_json": "{}"})
        have.add((etype, start, end))
        new_edges += 1
    with RELS.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rel_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rel_kept)

    # --- tool_id.csv：gatk 的 single 变体随槽一起消失
    with TOOLS.open(newline="") as handle:
        reader = csv.DictReader(handle)
        tool_header = list(reader.fieldnames or [])
        tool_rows = list(reader)
    for row in tool_rows:
        if row["tool_id"] != "gatk":
            continue
        variants = json.loads(row["input_variants_json"] or "{}")
        variants.pop("single", None)
        row["input_variants_json"] = json.dumps(variants, separators=(",", ":"))
    with TOOLS.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tool_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(tool_rows)

    # --- tool_relationship.csv：gatk->bcftools 改接 filtered_vcf，
    #     samtools->gatk 的 sorted_dedup_bam 边随槽删除（tumor/normal 两条边已覆盖）
    with NEXT.open(newline="") as handle:
        reader = csv.DictReader(handle)
        next_header = list(reader.fieldnames or [])
        next_rows = list(reader)
    out_rows = []
    for row in next_rows:
        if (row["tool_id"], row["next_tool_id"], row["input"]) == \
                ("T007", "T008", "sorted_dedup_bam"):
            continue  # gatk 已无 sorted_dedup_bam 输入槽
        if (row["tool_id"], row["next_tool_id"], row["input"]) == \
                ("T008", "T009", "unfiltered_vcf"):
            row["output"] = "filtered_vcf"
            row["input"] = "filtered_vcf"
        out_rows.append(row)
    if not any(r["tool_id"] == "T008" and r["next_tool_id"] == "T009"
               and r["input"] == "filtered_vcf_index" for r in out_rows):
        out_rows.append({"tool_id": "T008", "next_tool_id": "T009", "kind": "data",
                         "output": "filtered_vcf_index",
                         "input": "filtered_vcf_index"})
    with NEXT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=next_header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"删槽 {len(dropped_ids)} / 改槽 {patched} / 新增槽 {len(ADD)}")
    print(f"relationships: 删边 {removed_edges} / 改名 {len(renamed)} / 新边 {new_edges}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
