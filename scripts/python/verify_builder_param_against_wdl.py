"""第二轮补 builder_param：拿 .wdl 本体 + knowledge_card 三方交叉验证。

第一轮只看卡片 interface.params，靠角色对应 + 双射校验落了 31 条。第二轮把
归档.zip 里随卡片一起发布的 .wdl 本体也当证据——WDL 的 workflow input 块是权威
契约，它跟工具一起发布，不会漂移。

三条门槛同时成立才落，任一条不过整条退回人工：
  1. .wdl 顶层 workflow X { input {...} } 里有该参数，且类型是 File；
  2. knowledge_card.yaml 的 interface.params 里有同名参数（师兄这条规则做成硬校验）；
  3. 卡片该参数的 target 逐字等于 <WorkflowName>.<param>，并以它作为 wdl_target。

第 3 条卡掉了 paired_fastq_to_unmapped_bam 的 fastq_1/fastq_2：WDL 里就叫这个名字，
但卡片的 interface.params 里根本没有这两个参数，只有 sample_name / output_base 等
七个元数据参数。按师兄自己定的规则这两条填不了，要先补卡片。
"""

import re, csv, sys
from pathlib import Path
import yaml

ROOTS=[Path('/tmp/gd'), Path('/tmp/wf/workflow')]

CAND = [
 # tool_id, slot_name, builder_param
 ("bwa","clean_fastq_read_r1","read1"),
 ("bwa","clean_fastq_read_r2","read2"),
 ("fastp","raw_fastq_read_r1","read1"),
 ("fastp","raw_fastq_read_r2","read2"),
 ("rsem","transcriptome_bam","transcriptome_bam"),
 ("samtools","aligned_bam","alignment"),
 ("featurecounts","genome_annotation","gtf_file"),
 ("featurecounts","sorted_dedup_bam","bam"),
 ("gatk","tumor_bam","tumor_bam"),
 ("gatk","tumor_bai","tumor_bai"),
 ("gatk","normal_bam","normal_bam"),
 ("gatk","normal_bai","normal_bai"),
 ("gatk","interval_list","interval_list"),
 ("snpeff","filtered_vcf","input_vcf"),
 ("paired_fastq_to_unmapped_bam","fastq_1","fastq_1"),
 ("paired_fastq_to_unmapped_bam","fastq_2","fastq_2"),
 ("gsea_pathway_enrichment","tabular_bio_data","expression_matrix"),
 ("dataset_downstream","scrna_object_rds","input_rds"),
 ("dataset_downstream","genome_annotation","gene_order"),
 ("dataset_matrix_annotation","scrna_object_rds","input_rds"),
 ("breast_cellchat","scrna_object_rds","input_rds"),
 ("immunotherapy_cellchat","scrna_object_rds","input_rds"),
 ("celltype_case_control_de","scrna_object_rds","input_rds"),
 ("tcell_intervention","scrna_object_rds","input_rds"),
 ("ipf_trajectory_regulon","scrna_object_rds","input_rds"),
 ("lung_tme_annotation_cnv","scrna_object_rds","input_rds"),
 ("lung_tme_annotation_cnv","genome_annotation","gene_order"),
]

def find_dir(tool_id):
    for root in ROOTS:
        for d in root.rglob('knowledge_card.yaml'):
            if '__MACOSX' in str(d): continue
            if d.parent.name == tool_id: return d.parent
    # fall back: match meta.id
    for root in ROOTS:
        for d in root.rglob('knowledge_card.yaml'):
            if '__MACOSX' in str(d): continue
            try: c=yaml.safe_load(d.read_text())
            except Exception: continue
            if str((c.get('meta') or {}).get('id') or '')==tool_id: return d.parent
    return None

def wdl_inputs(wdl):
    t=wdl.read_text()
    m=re.search(r'^workflow\s+(\w+)\s*\{',t,re.M)
    if not m: return None,{}
    i=t.index('input {',m.start()); d=0; j=len(t)
    for k in range(i+6,len(t)):
        if t[k]=='{': d+=1
        elif t[k]=='}':
            d-=1
            if d==0: j=k; break
    out={}
    for line in t[i+7:j].splitlines():
        s=line.strip()
        mm=re.match(r'^([A-Za-z\[\]\?\+]+)\s+(\w+)\s*(=|$)', s)
        if mm: out[mm.group(2)]=(mm.group(1), mm.group(3)=='=')
    return m.group(1), out

ok=[]; bad=[]
for tool_id, slot, param in CAND:
    d=find_dir(tool_id)
    if not d: bad.append((tool_id,slot,param,"找不到工具目录")); continue
    wdls=[w for w in d.glob('*.wdl')]
    if len(wdls)!=1: bad.append((tool_id,slot,param,f"wdl 数={len(wdls)}")); continue
    wfname, inputs = wdl_inputs(wdls[0])
    if param not in inputs: bad.append((tool_id,slot,param,f"WDL input 块无此参数 (wf={wfname})")); continue
    ptype, has_def = inputs[param]
    card=yaml.safe_load((d/'knowledge_card.yaml').read_text())
    params={p.get('name'):p for p in ((card.get('interface') or {}).get('params') or [])}
    if param not in params:
        bad.append((tool_id,slot,param,"卡片 interface.params 里没有同名参数")); continue
    target=str(params[param].get('target') or '')
    expect=f"{wfname}.{param}"
    if target != expect:
        bad.append((tool_id,slot,param,f"卡片 target={target!r} != {expect!r}")); continue
    ok.append((tool_id,slot,param,expect,ptype,has_def))

print(f"通过 {len(ok)} / 候选 {len(CAND)}\n")
for r in ok: print(f"  OK  {r[0]:32s} {r[1]:22s} -> {r[2]:20s} {r[3]:52s} {r[4]}{' (有默认)' if r[5] else ''}")
print()
for r in bad: print(f"  拒  {r[0]:32s} {r[1]:22s} -> {r[2]:20s} {r[3]}")
import json; json.dump([{"tool_id":r[0],"slot_name":r[1],"builder_param":r[2],"wdl_target":r[3]} for r in ok], open(sys.argv[1] if len(sys.argv)>1 else '/tmp/apply.json','w'), ensure_ascii=False, indent=1)
