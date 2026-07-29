"""Run the six validation queries and emit key fields for manual review."""
import json
from workflow_composer import WorkflowComposer

QUERIES = [
    ("paired_wes", "我有肿瘤和正常配对的 WES FASTQ，想做体细胞变异检测并注释"),
    ("trim_to_fastp", "RNA-seq 上游流程里把 trim_galore 换成 fastp，其他不变"),
    ("rnaseq_upstream", "我有双端 FASTQ 想做 RNA-seq 上游分析"),
    ("tpm_cluster", "我有 TPM 矩阵想做无监督聚类"),
    ("go_kegg", "想同时做 GO 和 KEGG 富集"),
    ("single_wes", "我有一个样本的 WES FASTQ，想做变异检测和注释"),
]

composer = WorkflowComposer()
for key, query in QUERIES:
    result = composer.plan(query, top_k=5)
    plan = result.get("workflow_plan", {})
    agent_input = result.get("agent_input", {})
    feasibility = agent_input.get("feasibility", {})
    out = {
        "query": query,
        "workflow_mode": result.get("workflow_mode"),
        "selection_status": result.get("selection_status"),
        "orchestration_status": result.get("orchestration_status"),
        "orchestration_message": result.get("orchestration_message"),
        "pipeline_ids": plan.get("pipeline_ids") or [x.get("pipeline_id") for x in plan.get("reference_pipelines", [])],
        "execution_status": plan.get("execution_status"),
        "decomposition_gaps": plan.get("decomposition_gaps", []) if plan.get("mode") == "custom" else None,
        "validation_ok": plan.get("validation", {}).get("ok"),
        "validation_errors": plan.get("validation", {}).get("errors", [])[:5],
        "feasibility_status": feasibility.get("status"),
        "feasibility_message": feasibility.get("message"),
        "missing_assets": feasibility.get("missing_assets", [])[:10],
        "tool_chain_step_ids": [x.get("step_id") for x in agent_input.get("tool_chain", [])],
        "pipeline_assessments": plan.get("coverage_assessment", {}).get("pipeline_assessments", []),
    }
    print(f"\n=== {key} ===")
    print(json.dumps(out, ensure_ascii=False, indent=2))
