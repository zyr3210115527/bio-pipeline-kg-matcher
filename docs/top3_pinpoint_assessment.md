# Top-3 原子链改造定位报告（Phase 1，只读）

日期：2026-07-28  
范围：只盘点，不实现；未写 Neo4j，未修改目录、CSV、fingerprint、接口或校验规则。

## 结论先行

锁定方案可以实现，且编排器只需一次规划 LLM 调用。正确的改造边界不是“让现有 standard 返回三个结果”，而是：

```text
capability 查询继续走确定性只读分支
工作流请求 -> 一次 LLM 返回 1~5 条按 rank 排序的 atomic candidates
           -> 每条独立执行原有 _validate_custom_steps
           -> 每条独立匹配数据并校验完整组合
           -> 丢弃校验失败或数据不完整者
           -> 取前 3
```

三个关键结论：

1. **现有第一阶段 standard/pipeline 选择应整体删除。** 新 prompt 可以直接包含 atomic menu 和现有第二阶段的全部生物学、slot、配对及诚实阻断约束，一次返回 `candidates[]`。
2. **必须升级为 `tool-chain/v2`。** `tool-chain/v1` 的核心判别结构是一份顶层 `agent_input`，其中只有一份 `study_accession`、`assets`、`tool_chain`、`feasibility` 和 `match_id`。改成多份候选是破坏性结构变更，不应继续冒充 v1。
3. **工具目录基线不应变化。** 正式交付基线仍应是目录 `233` 节点 / `601` 关系、fingerprint `2ec21a69ff703115ed20a4946b62bf4bf22b3c8bdb6f1562fce0719f2655c903`。当前本机 7687 不是该交付基线，不能用它为 Phase 2 的最终门禁背书。

此外有一个必须在实现前钉死的细节：当前通用 `match_custom_roles()` 会把角色去重，并且 FASTQ 只取一对 R1/R2；配对肿瘤/正常 WES 现在靠 `_custom_plan()` 的专门分支取得四条 FASTQ。Top-3 逐候选匹配不能简单地对所有链只调用 `match_custom_roles()`，否则会丢失 tumor/normal 维度。Phase 2 必须保留现有配对 profile、`sample_role`、mate 和 GATK 四槽行为，并保证候选间没有共享的可变绑定状态。

## 1. standard 路径全貌

### 1.1 MCP 到返回的调用链

当前主调用链如下（行号为当前工作区代码）：

```text
server.py:415 route_pipeline_request
  -> server.py:424 _composer(mode).plan(...)
  -> workflow_composer.py:365 WorkflowComposer.plan()
       -> workflow_composer.py:373 capability shortcut（若命中则提前返回）
       -> workflow_composer.py:386 _llm_decision()
            -> workflow_composer.py:427 stage-one prompt：standard/custom + pipeline IDs
            -> workflow_composer.py:567 第一次 LLM 调用
            -> workflow_composer.py:573 显式内部修改校正
            -> workflow_composer.py:585 已知 standard 组合校正
            -> workflow_composer.py:601 coverage gap 降级 custom
            -> workflow_composer.py:608 standard 直接返回 decision
            -> workflow_composer.py:612 custom 才构造 stage-two atomic prompt
            -> workflow_composer.py:798 第二次 LLM 调用（含重试修复路径）
       -> workflow_composer.py:414 _standard_plan()
            -> pipeline_router.py:1365 PipelineRouter.route()
            -> pipeline_router.py:1392 matcher.match(intent, matched[:1])
            -> pipeline_router.py:1924 build_agent_input()（只认 matched[0]）
            -> workflow_composer.py:1892 _attach_plan()
            -> workflow_composer.py:1975 _apply_agent_contract()
            -> workflow_composer.py:2303 _standard_tool_chain()
            -> workflow_composer.py:2401 _expanded_pipeline_methods()（仅有 HAS_STEP 时）
            -> Knowledge Card externalize + contract validation
  -> server.py:432 _compact_route()
  -> MCP structuredContent/text
```

standard 在 `_standard_plan()` 中先将 LLM pipeline IDs 约束到 Neo4j pipeline 目录，再调用 router。若 ID 为空，只有规则回退路径可取 router 第一名；LLM 已运行但未返回 ID 时不允许无条件补一条。最后 `_standard_tool_chain()` 返回 pipeline-level 节点，或把唯一已登记 HAS_STEP 的 `rnaseq_singletask` 展开为锁定 atomic recipe。

### 1.2 数据只跟第一条流程

即使 standard 可选多个 pipeline，当前数据层仍只跟第一条：

- `pipeline_router.py:1390-1392` 明确使用 `matched[:1]`。
- `pipeline_router.py:1957` 使用 `primary = matched[0]["pipeline_id"]`。
- 一份 `agent_input` 只装一个 primary study 和一组文件。

因此现有“多个 standard pipeline”也不是三份独立候选，更不能直接复用为 Top-3。

## 2. standard 专属代码判定

| 代码/字段 | 位置 | Phase 2 判定 | 原因 |
|---|---:|---|---|
| `_pipeline_menu_lines()` | `workflow_composer.py:964` | 从路由 prompt 删除；目录查询能力另保留 | 新规划器只允许 atomic tool，不再让 LLM 选 pipeline-level 节点 |
| `_known_standard_pipeline_ids()` | `workflow_composer.py:1220` | dead code，删除 | 四组硬编码组合只为把请求拉回 standard |
| `_standard_has_coverage_gap()` | `workflow_composer.py:1027` | dead code，删除 | 不再存在 standard -> custom 降级；候选链直接原子化或明确 unsupported |
| `_standard_plan()` | `workflow_composer.py:1448` | dead code，删除 | Top-3 每项都是 custom atomic chain |
| `_standard_tool_chain()` | `workflow_composer.py:2303` | dead code，删除 | 不再返回 pipeline-level 节点，也不从 standard recipe 装链 |
| `_expanded_pipeline_methods()` | `workflow_composer.py:2401` | 路由侧 dead code，删除 | 只被 standard 展开和 standard 测试引用；Top-3 不从 pipeline recipe 生成候选 |
| `expand_standard_steps` | `plan()`、MCP schema、文档 | 删除 | 兼容开关与新产品定义冲突 |
| `pipeline_assessments` | stage-one prompt、`_standard_plan()` | 删除 | 其职责由 candidate `rank`/`match_note` 和逐链 validation 取代 |
| `uncovered_requirements` | 同上 | 改为顶层 `unsupported_reason` | 不再做 standard 覆盖评估；无法原子化必须明确拒绝 |
| standard quality-gate 装配 | `_quality_gate_for_request()`、`_apply_agent_contract()` | 从推荐链删除 | gate 挂在 pipeline-level 引用上；新候选没有 pipeline 节点。若未来要保留风险提示，应重新定义为 atomic/Knowledge Card 风险，不能把旧 pipeline gate 偷渡到 candidate |
| `_method_menu_lines()` | `workflow_composer.py:1042` | 保留 | 是一次 LLM multi-candidate prompt 的闭集菜单来源 |
| `_validate_custom_steps()` | `workflow_composer.py:1619` | 原样保留 | 是每条候选的强校验边界，禁止放宽 |
| `_custom_tool_chain()`、资产绑定、Knowledge Card externalize/validate | `workflow_composer.py:2443` 等 | 保留并改为逐候选调用 | 这是现有 atomic chain 到 agent 契约的正确路径 |
| capability/catalog 分支 | `workflow_composer.py:373-385`、`server.py:433-472` | 保留 | 能力浏览不是 standard 推荐，不生成执行链 |

`_attach_plan()`、`_apply_agent_contract()` 不是整体 dead code，但当前实现以单个 plan/单份 contract 为中心，必须拆成“构造一个 candidate contract”的可复用函数，再由顶层 Top-3 汇总器调用。不能在循环中反复改写同一个 `result["agent_input"]`。

## 3. LLM 当前协议与一次调用可行性

### 3.1 当前两阶段协议

第一阶段位于 `workflow_composer.py:427-550`，输入 12 个 pipeline/task-pipeline 菜单，输出：

```json
{
  "analysis": {},
  "mode": "standard | custom",
  "reason": "...",
  "requirements": [],
  "pipeline_ids": [],
  "reference_pipeline_ids": [],
  "pipeline_assessments": [],
  "uncovered_requirements": []
}
```

第一阶段后还有三层程序校正：显式修改优先、四种已知 standard 组合、coverage gap 降级。

第二阶段位于 `workflow_composer.py:612-778`，只在 custom 时出现，输入完整 atomic menu，输出一条链：

```json
{
  "analysis": {},
  "steps": [],
  "decomposition_gaps": []
}
```

第二阶段 prompt 已包含必须迁移的关键约束：

- tumor/normal 分支必须分开处理后在注册的多槽工具汇合；
- mate 与 `sample_role` 必须对应；不能按资产位置猜配对；
- 只允许精确 input/output 名、artifact 和 NEXT/data edge；
- raw count 与 TPM/FPKM 不互换；
- STAR `transcriptome_bam` 与 genomic `aligned_bam` 不互换；
- MultiQC 是 QC 汇总及 order-only 依赖，不解析表达/富集结果；
- 目录不能表达时必须给出诚实 decomposition gap，不能编步骤。

### 3.2 一次调用结论

**可以且应该改为一次调用。** 新 prompt 直接提供 atomic menu，并要求：

```json
{
  "analysis": {},
  "candidates": [
    {"rank": 1, "match_note": "...", "steps": []},
    {"rank": 2, "match_note": "...", "steps": []}
  ],
  "unsupported_reason": null
}
```

程序应限制候选数为 1~5，校验 rank 唯一且可排序，并对每个 `steps` 独立调用原有 `_validate_custom_steps()`。第一阶段的 pipeline 菜单、mode 判定、pipeline assessment、known-standard 校正都不再需要。

这里的“一次 LLM”是一次**规划调用**。后续 intent/data matching 必须走确定性代码；不得为每条候选再调用 LLM，也不得让 `selection_summary` 触发额外模型调用。当前 `_custom_plan()` 调 router 时使用 `allow_llm=False`，这一点可沿用。

## 4. 一对多数据匹配与性能

### 4.1 现状

现有 route 数据匹配是单 primary pipeline 模型，不支持一次调用返回 N 份相互独立的数据合同。

已经存在的 atomic-chain 数据入口是：

- `CsvKGDataMatcher.match_custom_roles()`：`pipeline_router.py:890-995`；
- MCP `query_data_availability(steps=...)`：`server.py:504-537`；
- `_custom_required_asset_roles()`：`server.py:254-269`。

但是 composer 的普通 `_custom_plan()` 并没有普遍使用 `match_custom_roles()`。它先按 reference pipeline 路由数据；只有检测到配对需求时，才在 `workflow_composer.py:1561-1579` 显式用 `wes_somatic_pair` profile 重新取四条配对 FASTQ。这是 Phase 2 不能忽略的现状。

### 4.2 Top-3 的正确匹配边界

每条通过 validation 的候选都需要独立完成：

1. 从 normalized steps 和正式 slot 维度推导数据要求；
2. 若含 tumor/normal 维度，沿用现有 paired profile 和同个体四 FASTQ 逻辑；
3. 否则使用 custom-role matcher；
4. 只接受完整 `data_combinations` 且 `assess_custom_role_feasibility(...).ok == true` 的结果；
5. 为该候选新建 assets、bindings、contract，不复用上一候选的 `asset_usage` 或绑定字典。

不能把 fallback `file_candidates` 非空当作“有数据”。`file_candidates` 可以只是部分候选；`match_custom_roles()` 只有在 feasibility 成功后才会于 `pipeline_router.py:968-975` 添加 `data_combinations`。

### 4.3 性能

交付报告 `docs/dual_read_report.md:39-40` 的 Neo4j matcher 基线：

- p50：`170.887 ms`；
- p95：`244.366 ms`。

顺序执行 5 次的粗略 matcher 成本为：

- p50 约 `0.85 s`；
- p95 约 `1.22 s`。

matcher 初始化由 server 进程缓存，因此不应每个 candidate 重建 driver/catalog。`_match_files()` 当前每次会重扫 T1/T2 候选（`pipeline_router.py:1089-1179`）。安全优化方向是按一次 intent/assay 预取并打分候选文件池，再对每条链独立做 role/slot/配对过滤；不能缓存或共享最终 assets/bindings。历史 LLM 延迟远大于 matcher，因此先保证隔离正确，再做这一级缓存。

## 5. 数据不足的判定

当前相关返回语义：

- `match_custom_roles()`：无完整组合时 `data_combinations=[]`；仍可能存在部分 `file_candidates`。
- `assess_custom_role_feasibility()`：返回 `ok`、`missing_roles`、`actual_file_count` 和 message。
- 现有单链 contract：缺数据时 `selection_status=missing_assets`，`feasibility.status=missing_assets`。

Top-3 的锁定规则应落实为：

- `validation.ok == false`：丢弃；内部日志记录 validation errors。
- `data_combinations` 为空或 candidate-specific feasibility 不通过：丢弃；内部日志记录 missing roles。
- 至少剩 1 条：返回 1~3 条，不补齐。
- 全部因未原子化失败：`candidates=[]`，填写具体 `unsupported_reason`。
- 能原子化但本地无完整数据：`candidates=[]`，返回明确的“没有有数据的可用候选”状态；不要伪装成 unsupported，也不要把 missing candidate 混进榜单。

## 6. 现有 custom 输出的真实结构

以下是 2026-07-28 直接调用当前 `WorkflowComposer.plan()`，注入一条已校验 FastQC decision 后再按 MCP compact 字段整理出的真实形状。当前本机数据匹配到 HRA000074；路径只表示图中登记资产，`path_verified=false`。

```json
{
  "schema_version": "tool-chain/v1",
  "selection_status": "draft",
  "orchestration_status": "draft",
  "orchestration_ready": false,
  "orchestration_message": "自定义方法链草案已形成，仍需执行端物化。",
  "workflow_mode": "custom",
  "intent": {
    "query_text": "对 RNA-seq FASTQ 只做 FastQC",
    "analysis_goal": null,
    "disease": null,
    "omics_type": "bulk RNA-seq",
    "input_hint": "fq.gz",
    "quant_hint": null,
    "requested_outputs": ["qc"],
    "source": "rule",
    "ambiguous": true
  },
  "workflow_plan": {
    "mode": "custom",
    "execution_status": "draft_requires_pipeline_materialization",
    "validation": {
      "ok": true,
      "errors": [],
      "warnings": [],
      "required_external_inputs": []
    },
    "decomposition_gaps": []
  },
  "agent_input": {
    "execution_kind": "tool_chain",
    "workflow_mode": "custom",
    "match_id": "match-a9efc9b67c1fca8c",
    "study_accession": "HRA000074",
    "assets": [
      {
        "asset_id": "HRA000074-fastq_r1-1",
        "role": "fastq_r1",
        "path": "/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000074/HRR025859_f1.fq.gz",
        "format": "Raw FASTQ",
        "path_verified": false,
        "source": "T1",
        "sample_accession": "HRS024297",
        "run_accession": "HRR025859",
        "individual_accession": "HRI024297",
        "sample_role": null,
        "mate": "r1"
      },
      {
        "asset_id": "HRA000074-fastq_r2-2",
        "role": "fastq_r2",
        "path": "/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000074/HRR025859_r2.fq.gz",
        "format": "Raw FASTQ",
        "path_verified": false,
        "source": "T1",
        "sample_accession": "HRS024297",
        "run_accession": "HRR025859",
        "individual_accession": "HRI024297",
        "sample_role": null,
        "mate": "r2"
      }
    ],
    "tool_chain": [
      {
        "step_id": "fastqc",
        "tool_id": "fastqc",
        "inputs": {
          "fastqs": {
            "sources": [
              {"asset_id": "HRA000074-fastq_r1-1"},
              {"asset_id": "HRA000074-fastq_r2-2"}
            ],
            "flatten": true
          }
        },
        "depends_on": []
      }
    ],
    "feasibility": {
      "status": "ready",
      "missing_assets": [],
      "data_ready": true,
      "message": "流程所需的用户样本数据已匹配。"
    },
    "selection_reason": "只做 FastQC",
    "orchestration_status": "draft",
    "orchestration_ready": false,
    "orchestration_message": "自定义方法链草案已形成，仍需执行端物化。",
    "extensions": {
      "quality_gates": {},
      "plan_validation": {"ok": true, "errors": [], "warnings": [], "required_external_inputs": []},
      "execution_contract": {"schema_version": "knowledge-card-execution-contract/v1"},
      "contract_validation": {
        "ok": true,
        "errors": [],
        "internal_catalog": {"ok": true, "errors": []},
        "knowledge_card": {"ok": true, "errors": []}
      }
    },
    "pipeline_id": null,
    "files": [
      "/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000074/HRR025859_f1.fq.gz",
      "/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000074/HRR025859_r2.fq.gz"
    ],
    "files_text": "/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000074/HRR025859_f1.fq.gz\n/mnt/CNCBOBdata/cbbgroup/tcoa/HRA000074/HRR025859_r2.fq.gz"
  }
}
```

单条专属字段包括：顶层 `workflow_plan`、`agent_input`，以及其中的 `match_id`、`study_accession`、`assets`、`tool_chain`、`feasibility`、`selection_reason`、`pipeline_id/files/files_text` 和 candidate-specific contract validation。它们不能共享于三条候选。

还需注意一个状态语义：当前所有通过校验的 custom chain 都在 `workflow_composer.py:2013-2016` 被标成 `draft`，即使数据齐全。Top-3 的“榜上候选”究竟表示“可编排且数据齐”还是“执行端已经可执行”，必须在 v2 文档中明确。按本项目只负责编排的既定边界，建议顶层 `selection_status=ready` 表示“至少有一条可选编排”，candidate 内保留 `validation` 和 `feasibility` 两个事实，不声称生信任务已经执行。

## 7. Top-3 输出格式与版本

推荐升级为 `tool-chain/v2`，而不是扩展 v1：

```json
{
  "schema_version": "tool-chain/v2",
  "selection_status": "ready | no_candidate | unsupported | information",
  "candidate_count": 2,
  "candidates": [
    {
      "rank": 1,
      "match_note": "最精确覆盖用户目标",
      "workflow_mode": "custom",
      "match_id": "match-...",
      "validation": {"ok": true, "errors": []},
      "feasibility": {"status": "ready", "missing_assets": [], "data_ready": true},
      "study_accession": "...",
      "assets": [],
      "tool_chain": [],
      "extensions": {"contract_validation": {"ok": true, "errors": []}}
    }
  ],
  "unsupported_reason": null,
  "intent": {},
  "planner_metadata": {}
}
```

理由：

- `server.py:33-107` 和 `docs/mcp_delivery/schemas/tool_chain_output.schema.json` 都要求一份顶层 `agent_input`。
- v1 以 `workflow_mode=standard|custom|capability` 和一份 `agent_input` 为判别结构。
- 三份 `study_accession/assets/tool_chain` 改变了基数和访问路径。
- 对接方需要从 `agent_input.tool_chain` 改读 `candidates[i].tool_chain`，这正是破坏性迁移。

不建议保留一份“Top1 复制到旧 `agent_input`”的兼容层。锁定需求已明确允许 breaking change；双写会制造两个真源，并让调用方继续忽略 Top2/Top3。

capability 信息查询可以作为 v2 schema 的 `information` 分支保留，但不能伪造成空候选的工作流结果。`unsupported`（能力未原子化）与 `no_candidate`（原子链可构造但无完整数据/全部校验失败）也应分开。

## 8. 基线与交付影响（逐项会/不会）

| 项目 | 会不会变 | 精确结论 |
|---|---|---|
| 双读 191 数据 matcher 基线 | **实质口径不会因删除 standard 自动改变** | 191 是 CSV/Neo4j 数据层等价性 corpus，不是 standard route 数量。若 Phase 2 只在编排层逐候选调用现有 matcher，应继续要求 191/191、0 material differences。若实现共享文件池优化，仍必须重跑全部 191。route/demo 的 standard 期望则必须另行改写 |
| 目录节点/关系/fingerprint | **不会变** | 不改目录、CSV、slot、NEXT、HAS_STEP。批准基线应继续是 233/601 和 `2ec21a69...5c903`；发生变化即越界 |
| `tool-chain/v1` 契约 | **会破坏** | 顶层单 `agent_input` 改为 `candidates[]`，必须升 `tool-chain/v2` |
| `docs/mcp_delivery/` | **会，需要全套重出** | schema、字段说明、迁移说明、示例、transcripts、cassette、consumer acceptance 和 smoke 期望均受影响 |
| MCP 主工具 | **会** | `route_pipeline_request` 输入删除 `force_custom`/`expand_standard_steps`，输出升 v2；`top_k` 的语义应明确是返回上限还是内部候选数，锁定需求建议固定返回上限 3、内部最多生成 5 |
| 其他 6 个 MCP 工具 | **大体不会** | catalog、health、`validate_tool_chain`、custom-steps `query_data_availability` 正交；render 需适配 v2。pipeline-ID data query 可保留为目录/数据工具，但不得参与推荐 |
| pairing/mate/sample_role/GATK 四槽 | **不允许改变** | 要求零回归；逐候选数据匹配必须保留现有专用 paired profile |
| custom validation 严格性 | **不允许改变** | `_validate_custom_steps()` 原样逐候选调用 |
| 未拆解 pipeline | **不会被偷偷展开** | 富集、差异表达、WGCNA、生存等当前 atomic menu 无法表达时返回 unsupported，不从 11 个 pipeline-level 节点编造内部步骤 |

### 8.1 当前环境与交付基线必须分开

已验证交付报告 `docs/self_verification_report.md` 记录：

- 84 tests discovered，81 passed，3 opt-in skipped；
- unified graph 9/9；
- dual-read 191/191，0 material differences；
- MCP online/offline 12/12；
- 目录 233/601，fingerprint `2ec21a69...5c903`。

本次 Phase 1 在当前工作区实跑单元测试结果是：`84` discovered，`74` passed，`7` failed，`3` skipped。失败集中在当前 7687 目录与批准 slot/Knowledge Card 基线不一致，以及 2 条 standard expansion 断言；这不是 Top-3 代码造成的，因为 Phase 2 尚未开始。

当前 live 7687 呈现旧目录形状（218/548、fingerprint `439dff...57de1f`），没有交付 staging 的统一 snapshot。此前只读门禁结果也仅为 unified 2/9、MCP 4/12，dual-read 会在前置合同检查处中止。因此 Phase 2 最终验证必须恢复批准 dump 到**隔离实例**后执行；生产 7687 继续只读，不能为跑门禁而覆盖。

## 9. custom、配对、validate、data availability 的正交性

| 能力 | 是否正交 | 处理原则 |
|---|---|---|
| `_validate_custom_steps()` | 是 | 完全保留，逐 candidate 调用，不改规则 |
| Knowledge Card externalize/validate | 是 | 每个 candidate 都必须独立再校验一次 |
| `_select_asset()` 的 mate/sample_role 精确绑定 | 是，但对多候选状态隔离敏感 | 每个 candidate 新建 `asset_usage` 和 bindings；不可跨 candidate 复用 |
| GATK four-slot/input variants | 是 | 保留完整唯一 variant 校验；不能为提高 Top-3 通过率放宽 |
| `query_data_availability(steps)` | 是 | 已按 custom chain 校验并查数据，可保留接口 |
| `query_data_availability(pipeline_ids)` | 技术上正交，产品上不再推荐 | 可作为目录/数据检查工具存在，但 route 不得调用它生成推荐 |
| capability/list tools | 是 | 保留只读信息查询 |
| `render_pipeline_answer` | 否 | 当前按单份 result/agent_input 渲染，必须改为逐 candidate 展示 |
| app/demo | 否 | `app.py:55` 构建 standard plan map；`demo.html` 有 standard 组合、coverage assessment、参考标准流程及单链面板，均需改成 Top-3 列表 |

最大风险不是 `_validate_custom_steps()`，而是**数据选择和绑定的状态隔离**。当前配对逻辑是在单链上下文验证的；Top-3 循环必须把 normalized steps、matched combination、assets、asset usage、contract validation 都局部化。

## 10. 测试影响

### 10.1 数量纠正

任务描述中的“81 用例”是旧口径。当前仓库实际发现 **84 个测试方法**；批准交付结果是 81 passed + 3 skipped。当前 live 环境实跑为 74 passed + 7 failed + 3 skipped。

按测试方法逐项扫描，**28 个用例需要审查：其中 27 个需要删除或改写行为，1 个 MultiQC menu 测试只需随 prompt 重命名**。另有 2 个 runtime transport 测试仅把 `{"mode":"standard"}` 当作普通 LLM JSON，用于验证 model metadata 和重试；它们不验证 standard 产品行为，应保留并把 fixture 改成 v2 candidate JSON即可。`test_registered_pipeline_path_remains_compatible` 测的是独立 `query_data_availability(pipeline_ids)`，是否保留取决于该工具的产品策略，不应随 route standard 一起误删。

### 10.2 删除：只验证已取消的 standard 兼容行为

- `tests/test_standard_expansion.py::test_legacy_switch_preserves_pipeline_node_and_asset_bindings`
- `tests/test_standard_expansion.py::test_pipeline_without_recipe_is_explicitly_unexpanded`
- `tests/test_workflow_composer.py::test_standard_mode_can_compose_multiple_locked_pipelines`
- `tests/test_workflow_composer.py::test_known_standard_combination_overrides_llm_atomic_decomposition_error`
- `tests/test_workflow_composer.py::test_execution_quality_risk_does_not_block_orchestration_status`
- `tests/test_workflow_composer.py::test_standard_llm_stage_does_not_include_method_catalog`
- `tests/test_workflow_composer.py::test_force_custom_skips_standard_selection_call`
- `tests/test_workflow_composer.py::test_standard_coverage_gap_is_promoted_to_custom_assessment`
- `tests/test_workflow_composer.py::test_llm_uncovered_requirements_survive_known_combination_rule`
- `tests/test_workflow_composer.py::test_llm_standard_without_pipeline_ids_not_filled_by_router_fallback`

这些断言验证的是将被删除的 mode、兼容开关、pipeline assessment 或 standard fallback，不应为了“保持测试数”保留无意义兼容代码。

### 10.3 改写为 Top-3 契约/一次调用行为

- `tests/test_standard_expansion.py::test_rnaseq_expands_to_valid_locked_recipe` -> Top1 为合法 RNA atomic chain，所有候选无 pipeline-level 节点。
- `tests/test_workflow_composer.py::test_internal_change_still_precedes_known_standard_combination` -> 所有工作流请求都走一次 multi-candidate prompt，不再测 mode 优先级。
- `tests/test_workflow_composer.py::test_singular_recommendation_is_routed_not_listed` -> 返回 1~3 candidates，而非 capability。
- `tests/test_workflow_composer.py::test_execution_parameter_wording_does_not_force_custom_mode` -> 参数措辞不改变 candidate 生成/数据判定。
- `tests/test_workflow_composer.py::test_explicit_change_overrides_llm_standard_misclassification` -> 一次调用返回候选或 unsupported，不再有 stage-one/stage-two。
- `tests/test_workflow_composer.py::test_standard_rnaseq_recipe_uses_only_neo4j_tools` -> 每个候选只含 Neo4j atomic tool，且无 WDL/pipeline ID。
- `tests/test_workflow_composer.py::test_standard_agent_contract_matches_tool_chain_v1` -> 改成 `tool-chain/v2` candidates schema；未原子化聚类请求应 unsupported。
- `tests/test_workflow_composer.py::test_ubam_runtime_parameters_do_not_affect_success` -> uBAM 尚无 atomic tool 时明确 unsupported；运行参数仍不进入 missing assets。
- `tests/test_workflow_composer.py::test_rnaseq_reference_assets_are_execution_managed` -> 对每个 candidate 保持 reference managed、只匹配用户 FASTQ。
- `tests/test_workflow_composer.py::test_missing_user_sample_data_still_sets_missing_assets` -> 缺数据 candidate 被过滤；全空返回 no-candidate 原因。
- `tests/test_workflow_composer.py::test_custom_llm_stage_loads_method_catalog_only_after_classification` -> 断言唯一调用直接获得 atomic menu 并返回 1~5 candidates。
- `tests/test_workflow_composer.py::test_mcp_stdout_contains_json_only_when_llm_is_unavailable` -> 仍锁 stdout JSON-only，但不再期待 standard 规则结果。
- `tests/test_runtime_integrations.py::test_fastq_prompt_regression_is_four_for_four` -> 连跑 Top-3/unsupported 预期，不再比 pipeline IDs。
- `tests/test_runtime_integrations.py::test_mixed_standard_custom_and_capability_routing` -> atomic Top-3 + unsupported + capability 三分支。

### 10.4 保留约束，但脱离旧 standard helper

- `tests/test_standard_expansion.py::test_multiqc_is_in_stage_two_menu` -> 保留，重命名为 multi-candidate atomic menu/prompt 测试。
- `tests/test_workflow_composer.py::test_quality_gate_scope_does_not_block_paired_rnaseq`
- `tests/test_workflow_composer.py::test_quality_gate_scope_blocks_explicit_single_end_rnaseq`
- `tests/test_workflow_composer.py::test_ubam_example_input_risk_is_validation_not_blocker`

后三条目前验证 pipeline quality-gate helper。若该 helper 随 standard 删除，应删除原断言，并把仍然有效的生物学约束迁移到 atomic validation/候选过滤测试，不能让单端、配对或输入风险约束随 helper 一起消失。

### 10.5 必须零回归并新增的测试

现有 custom validation、slot model、配对打乱、Knowledge Card、data matcher、`validate_tool_chain`、custom-steps data availability 测试必须保留。新增至少覆盖：

- 单次 LLM 返回 1、3、5 条及乱序/重复 rank 的归一化；
- 候选逐条校验，失败者只进内部诊断、不进入榜单；
- 候选逐条数据匹配，无完整 `data_combinations` 者被过滤；
- 有 1/2/3 条时正常返回，不硬凑；
- 全部未原子化与全部无数据是两个不同状态；
- 三个 candidate 的 `assets`、`match_id`、bindings 相互独立；
- 肿瘤/正常四 FASTQ 资产顺序多次打乱，Top-3 循环后 `sample_role`/mate/GATK 四槽仍精确；
- candidate 经 internal validation、Knowledge Card externalization 和 external contract validation 三层校验；
- LLM 只调用一次，matcher 调用次数等于通过 validation 的候选数（或等价的共享预取 + 独立过滤）；
- v2 schema、MCP compact output、renderer 和 consumer migration。

## Phase 2 建议实施顺序

1. 先定义并测试 `tool-chain/v2` schema 与单个 candidate builder，明确 status 语义。
2. 将第二阶段全部约束迁入一次 multi-candidate prompt，先用 mock 固定输出验证解析与一次调用。
3. 逐候选调用不变的 `_validate_custom_steps()`。
4. 提取 candidate-specific matcher；先处理 paired profile，再处理通用 custom roles，保证状态隔离。
5. 逐候选构建 assets/tool chain/Knowledge Card contract，排序取前 3。
6. 删除 standard dead code、输入参数和 UI/文档分支。
7. 在隔离的批准 staging dump 上跑单元、配对打乱、191 双读、9/9、12/12、LLM 稳定性和 p50/p95。

## Phase 1 停止点

本报告完成了附件要求的 10 项只读定位。尚未执行 Phase 2；未删除 standard 代码，未改 `route_pipeline_request`，未改 `_validate_custom_steps`，未改 pairing/slot 行为，未写 Neo4j，未触碰目录/CSV/fingerprint。
