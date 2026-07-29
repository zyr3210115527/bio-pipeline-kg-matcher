# Top-3 Implementation

## Outcome

Standard routing has been removed. Every analysis request now follows one pipeline:

```text
one LLM call -> 1-5 ranked atomic chains -> strict validation per chain
-> independent data match per chain -> independent asset/contract build
-> keep data-complete valid chains -> rank -> return at most 3
```

Capability browsing remains a deterministic information-only branch. It never creates an executable candidate.

## Code changes

| Area | Change | Reason |
|---|---|---|
| `workflow_composer.py` | Added `_top3_llm_decision`, `_top3_plan`, `_normalize_ranked_candidates`, `_build_top3_candidate` | Generate and process all candidates through one LLM response |
| `workflow_composer.py` | Removed standard selectors, coverage promotion, standard expansion, `force_custom`, `expand_standard_steps`, and v1 `agent_input` assembly | Prevent pipeline-level nodes and two competing result contracts |
| `workflow_composer.py` | Keeps `_validate_custom_steps` unchanged and calls it once per candidate | Preserve the approved closed-catalog, slot and NEXT gates |
| `workflow_composer.py` | Detects paired WES from tumor/normal step IDs plus GATK's four BAM/BAI slots | Preserve the dedicated four-FASTQ matcher |
| `workflow_composer.py` | Creates matching, assets, binding and Knowledge Card validation state inside each candidate loop | Prevent cross-candidate contamination |
| `server.py` | `route_pipeline_request` accepts `query`, `top_k=1..3`, `data_matcher_mode`, `include_internal`; output is `tool-chain/v2` | The old single-chain shape cannot represent Top-3 |
| `app.py` | Demo adapter and renderer consume `candidates[]` | Remove assumptions about top-level `agent_input` |
| `intent.py` | Rejects nested fragments from truncated JSON and preserves LLM metadata | A truncated response must not be mistaken for a complete candidate payload |
| `runtime_config.py` | Default LLM timeout 180 seconds and max tokens 16000 | DeepSeek reasoning responses can exceed the previous 60s/8000-token envelope |
| `pipeline_router.py` | Parses explicit `HRA...` study accessions and applies them as hard cohort/file constraints; removes the legacy Python-only standard router and v1 agent-input builder | Prevent an absent requested study from silently receiving another study's data and eliminate the last standard dead path |
| `scripts/top3_live_probe.py` | Records repeatable live quality and latency probes without credentials | Make Top-3 acceptance reproducible |

The catalog, canonical CSV, Neo4j data, slot definitions, NEXT edges and `_validate_custom_steps` rules were not changed.

## Candidate pipeline

For every normalized candidate:

1. `_validate_custom_steps` validates atomic tool IDs, exact input/output names, variants, artifacts, forward references, NEXT edges and connectivity.
2. `_candidate_required_asset_roles` derives only user sample roles; execution-managed references are excluded.
3. `_is_paired_wes_candidate` selects the dedicated `wes_somatic_pair` matcher only when both sample branches and all four GATK merge slots exist. Other chains use `match_custom_roles`.
4. Only a complete `data_combinations` entry is accepted. Partial `file_candidates` do not count.
5. Assets and internal bindings are built for that candidate only.
6. The internal contract is validated, translated to Knowledge Card IDs/names, and validated again.
7. A failure is retained only in `extensions.rejected_candidates` when `include_internal=true`; it never enters `candidates[]`.

Candidates are de-duplicated by full step JSON, sorted by model rank, assigned unique positive ranks when necessary, and capped at five before processing and three after acceptance.

## Paired WES invariant

The generic custom-role matcher selects one FASTQ pair and cannot replace paired tumor/normal matching. The Top-3 loop therefore preserves the special path:

```text
has tumor step suffix
and has normal step suffix
and one GATK step binds tumor_bam/tumor_bai/normal_bam/normal_bai
    -> matcher.match(... wes_somatic_pair ...)
else
    -> matcher.match_custom_roles(...)
```

`assets`, the candidate's combination, internal chain, usage tracking and validation results are local variables. No matching state is shared between candidates.

The current Knowledge Card maps GATK's paired tumor/normal inputs but not the internal single-sample `sorted_dedup_bam` input. It also lacks the VCF index required by BCFtools. Those chains fail closed until the backend contract is extended; this implementation does not synthesize a mapping or artifact.

## Output contract

`tool-chain/v2` has no top-level `agent_input`. It contains `candidates[]`; every candidate owns its `rank`, `match_note`, `match_id`, `study_accession`, `assets`, `tool_chain`, and contract diagnostics.

The statuses are:

- `ready`: one or more validated and data-complete candidates;
- `unsupported`: the requested analysis requires an unregistered atomic capability;
- `no_candidate`: no proposed chain survived strict validation plus data matching;
- `information`: capability browsing, with no executable candidate.

This is intentionally breaking. No Top1-to-v1 compatibility copy is produced.

## LLM prompt template

The runtime appends the current Neo4j atomic menu after the following exact template:

```text
你是生信工作流候选链规划器。你只负责流程编排，不执行任务，也不讨论线程、内存等运行参数。

一次性生成 1 到 5 条按匹配程度排序的候选链，通常只需 1 到 3 条真正不同的完整链。所有候选都必须只由下方 Neo4j 目录中的 atomic tool 组成；禁止输出 pipeline/task_pipeline 节点。为保证 JSON 完整，analysis 每个字段只写一句短句，match_note 和 reason 各不超过一句，不重复抄写规则或目录。

只输出一个 JSON 对象，不要 Markdown：
{
  "analysis": {
    "sample_layout": "单样本或配对样本及角色",
    "data_path": "输入到目标产物的数据形态变化",
    "coverage": "每条候选覆盖目标的方式",
    "checks": "闭集、槽位、NEXT、样本维度和最终产物自检"
  },
  "candidates": [
    {"rank": 1, "match_note": "推荐理由和侧重", "steps": [
      {
        "step_id": "唯一且稳定的标识",
        "tool_id": "目录中的 atomic tool id",
        "inputs": {
          "精确注册输入名": {"asset_role": "数据角色"}
          或 "精确注册输入名": {"from": {"step_id": "前序步骤", "output": "精确注册输出名"}}
        },
        "depends_on": ["仅用于顺序依赖的前序步骤"],
        "reason": "步骤作用"
      }
    ]}
  ],
  "unsupported_reason": null
}

候选规则：
1. rank 必须唯一，1 最贴合；第一条必须是覆盖完整目标的首选链，其余才是不同工具组合或侧重的替代链。不要为了凑数复制、截短或给出明显不完整的链。
2. 每个 input 名、from.output 名、tool_id 必须逐字匹配目录。tool_id 只能取每行开头 `-` 后、第一根 `|` 前的小写名称（如 fastp、star、samtools）；T01/T02 之类编号不是 tool_id，绝对不能输出。from 只能引用前序 step；每条 from 和 depends_on 都必须存在对应 NEXT 边，数据连接还必须匹配目录中的 output->input 数据边。
3. 除首个根步骤外，每步必须通过 from 或 depends_on 与前序相连。MultiQC 只汇总 QC 日志，步骤必须写 `inputs: {}` 并只用 depends_on 连接需要汇总的前序步骤，执行合同会自动聚合 QC 来源；禁止为 MultiQC 编造或直接绑定任何 input。它不解析表达矩阵、变异表或富集结果。
4. raw count 与 TPM/FPKM 不可互换；uBAM 不等于 aligned BAM；STAR transcriptome_bam 只给 RSEM，aligned_bam 才能给 SAMtools。STAR 的 clean_fastq_read 是可承载双端 R1/R2 的成对 reads bundle；不要因为目录只有一个语义槽就把双端 RNA-seq 判为不支持。
5. reference/index/annotation 等执行端管理资产使用 reference_file。用户样本数据必须明确 asset_role；不要把运行参数当资产。

配对 tumor/normal 的硬约束：
- GATK 输入有两个互斥变体。单样本分析必须且只能绑定 sorted_dedup_bam，禁止使用 tumor_bam/tumor_bai/normal_bam/normal_bai；只有明确的 tumor-normal 配对分析才使用下面的四槽变体。
- step 是“工具 x 样本”实例。fastqc/fastp/trim_galore/bwa/star/samtools 等单样本步骤必须分别生成 _tumor 和 _normal 两条链，不能提前合并，也不能交叉引用。
- 两侧都完成独立比对和 BAM 处理后才能汇合。汇合 GATK 只出现一次，并且必须同时精确绑定 tumor_bam、tumor_bai、normal_bam、normal_bai 四个注册槽；后续 bcftools/snpeff 等汇合步骤也只出现一次。
- 每个样本的 R1/R2 必须保持 mate 和 sample_role 一致，不能按文件列表位置猜测。

不支持规则：
- 若完整需求需要当前 atomic 目录尚未拆出的能力，例如差异表达、GO/KEGG/Reactome 富集、WGCNA 共表达网络、生存分析或其他未登记方法，candidates 必须为空，并在 unsupported_reason 明确说明“这类分析尚未原子化，暂不支持”。
- 若目录槽位或 NEXT 边无法忠实表达目标，也返回空 candidates 和具体 unsupported_reason；禁止编造工具、槽位、边或内部步骤。
- candidates 非空时 unsupported_reason 必须为 null。

Neo4j atomic 方法目录：
<由 _method_menu_lines() 动态附加的 12 个 atomic tool 合同>
```

The user message is exactly `用户需求：<query>`.
