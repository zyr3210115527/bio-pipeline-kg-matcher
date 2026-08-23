# execution_params 规格（师兄需求原文 + 落地说明）

> 来源：师兄的接口卡片（`route_pipeline_request` 输出增强需求）。本文件为需求存档 +
> 本仓库的落地实现说明。实现见 `workflow_composer.py:_execution_params`；契约见
> `docs/mcp_delivery/schemas/tool_chain_output.schema.json` 与
> `docs/mcp_delivery/MCP_AGENT_INTEGRATION_ZH.md` §3.1。

## 一、需求原文

请保持现有 `tool-chain/v2` 结构不变，在每条 `recommendations[]` 中新增 `execution_params`。

格式要求：

```json
{
  "pipeline_id": "wes_somatic_maf_landscape",
  "tool": { "catalog_status": "registered" },
  "data": { "status": "available", "assets": [] },
  "execution_params": {
    "maf_file": "/hpcdisk1/.../HRA001272-SomaticSNV-1.0.maf"
  }
}
```

规则：

1. `execution_params` 的键必须与对应 `knowledge_card.yaml` 中 `interface.params[].name` 完全一致，不要使用 `target`。
2. `type: file` 返回单个路径字符串；文件数组参数返回路径数组。
3. 只映射知识图谱已确认的数据输入，不要填充 CPU、内存、Docker、输出目录等执行参数。
4. Knowledge Card 已有默认值的非文件参数不用返回。
5. 数据缺失或无法确定对应关系时，不得猜测或伪造路径；对应参数不返回，报缺参。
6. 必须保留现有 `data.assets`，`execution_params` 只是把这些资产转换成可直接使用的参数。
7. 用户选择 recommendation 后，应能直接调用：

```json
{
  "pipeline_id": "wes_somatic_maf_landscape",
  "params": { "maf_file": "/hpcdisk1/.../HRA001272-SomaticSNV-1.0.maf" }
}
```

多文件流程示例：

```json
{
  "pipeline_id": "wgcna",
  "execution_params": {
    "counts_tsv": "/data/counts.tsv",
    "clinical_xls": "/data/clinical.xls",
    "metainfo_xlsx": "/data/metainfo.xlsx"
  }
}
```

验收用例：问题“展示肝癌队列 Top30 高频突变基因和不同突变类型分布”返回的 recommendation 中必须包含：

```json
"execution_params": {
  "maf_file": "/hpcdisk1/cbb_group/data/analysis/HRA001272/HRA001272-SomaticSNV-1.0.maf"
}
```

## 二、落地实现

- **键 = `io_slot.builder_param`**：真实参数名（`interface.params[].name`）已在上一轮并入活图 `io_slot.builder_param`，经 `_slot_spec` 透传到 `recommendation.tool.inputs[].builder_param`。`_execution_params` 只遍历带 `builder_param` 的槽（参考索引槽跳过 → 满足规则 3/4）。
- **值 = 真实路径**：取自 `data.assets[].file_path`，且必须通过真实路径校验（以 `/` 开头、非 `NOT_FOUND`、非 `"<name> (<n> bytes)"` 占位）。槽↔资产按规范化 role 配对（复用 `_canonical_asset_role` / `_role_for_input` / `_execution_asset_role`）。
- **参考资源不返回**（规则 4）：canonical role 为 `reference_file` 的槽（基因组索引 / GTF / PoN / known-sites 等，有卡片默认值）既不映射也不报缺。
- **报缺不臆造**（规则 5）：无真实路径的数据参数进入 `execution_params_missing`（`param`/`slot`/`role`/`reason`），不编路径。
- **未绑定的槽也要报**（0823 补）：`builder_param` 为空的**数据**槽以 `reason: "slot_not_bound"`、`param: null` 进入 `execution_params_missing`。此前这类槽是无声跳过，注释断言"无 builder_param 的都是 sample-lookup / 参考索引"——该断言在目录只收录 12 个全绑定工具时成立，0823 清点发现 128 个输入槽有 95 个为空，绝大多数是货真价实的数据输入。无声跳过的后果是回包给出 `execution_params: {}` 且 `missing: []`，即"零个参数且一个都不缺"，消费方按 `not missing` 判可提交。两个例外仍不报：canonical role 为 `reference_file` 的槽（规则 4）、`variant_alias_for` 非空的别名行（真实槽自己会报）。待确认清单见 `docs/待确认_builder_param.md`。
  - `slot_not_bound` 与 `no_confirmed_path` **不可合并**：前者是目录表缺绑定，要人补 `io_slot.csv`；后者是绑定正确但图里没有确认路径，要数据侧补 `file_path`。处置对象不同。
- **`data.assets` 原样保留**（规则 6）。

## 三、已知数据限制

上游 FASTQ（T1）在参考数据里 `file_path` 为 `NOT_FOUND`，故 rnaseq / 配对 WES 等 fastq 输入流程的 `sample_r1`/`sample_r2` 会进入 `execution_params_missing`；需数据侧补齐 T1 `file_path`（或另定路径拼装规则）后才能给出真实路径。maf / 表达矩阵（TPM/count）/ 临床 / metainfo 等 T2 产物路径齐全，可直接给出。

## 四、验收结果（已通过）

`route_pipeline_request("我想展示肝癌队列里 Top30 高频突变基因和不同突变类型分布。")` →
```json
"execution_params": {"maf_file": "/hpcdisk1/cbb_group/data/analysis/HRA001272/HRA001272-SomaticSNV-1.0.maf"}
```
多文件亦通过：immune_infiltration_iobr → `expression_tsv`/`clinical_xls`/`metainfo_xlsx`；survival_analysis → `maf_file`/`clinical_file`/`metainfo_file`（均为真实路径）。
