# 目录迁移路径（方案，不实施）

> 本文是给目录、编排和资产绑定负责人的实施计划。本轮不修改 CSV、Neo4j 或运行时。行数估计是评审粒度，不是承诺。

## 1. 不能拆开的五处耦合

依赖顺序是：

```
显式槽身份
    ↓
NEXT 四元组多边
    ↓
配对资产取得（同个体、同样本 R1/R2）
    ↓
mate + sample_role 绑定
    ↓
输入 variant 选择与必需性
    ↓
新具名槽 + 新 NEXT + 新 atomic tools 同时启用
```

### 1.1 显式槽身份

| 项目 | 估计 |
|---|---|
| 主要文件 | `data/csv/relations/tool_input_format.csv`, `tool_output_format.csv`, 新 `tool_input_variant.csv`; `scripts/python/sync_neo4j_tool_catalog.py:158-269`; `scripts/python/validate_csv.py:118-210`; `neo4j_observability.py:304-360`; `workflow_composer.py:128-193` |
| 代码改动 | 同步器约 70–110 行，CSV 校验约 60–90 行，Neo4j 读取/目录 model 约 30–50 行，测试 80–120 行 |
| schema 变更 | **有**：CSV 新列 + variant 表；`io_slot` 新增 `wdl_type/dimension/dimension_value/variant`；`slot_id` 基于 `slot_name` |
| 验收 | 同一工具可同时存在 `raw_fastq_read_r1`/`raw_fastq_read_r2`，artifact 都为 `raw_fastq_read`；重复 slot_name 失败关闭；旧 CSV 扩展后的 34 槽读出完全不变 |
| 独立发布 | 可，但只能发布兼容读写能力和 legacy 等价数据；不得先加新槽 |

少这一环，`_sync_tool()` 仍在 `sync_neo4j_tool_catalog.py:224-252` 用 artifact 生成 `slot_id/slot_name/required`；R1/R2 或 tumor/normal 会合并成一个 Neo4j 槽。

### 1.2 NEXT 四元组多边

| 项目 | 估计 |
|---|---|
| 主要文件 | `scripts/python/sync_neo4j_tool_catalog.py:360-438`; `scripts/python/validate_csv.py`; `neo4j_observability.py:59-70,351-360`; `workflow_composer.py:158-193` |
| 代码改动 | 同步器 20–35 行，校验 25–40 行，目录读取/消费 15–25 行，测试 50–80 行 |
| schema 变更 | Neo4j relationship 属性不新增，但 **MERGE identity 改变**；CSV 唯一键改为 5 列 |
| 验收 | 同时存在 `fastp.clean_r1→bwa.clean_r1` 和 `fastp.clean_r2→bwa.clean_r2`；`samtools→gatk` 可有 single/tumor/normal 多边；重复四元组失败；`allowed_next_tool_ids` 仍只显示去重的 tool ids |
| 独立发布 | 可，先改 MERGE/read/dedupe 但保持旧 14 边，行为不变 |

当前 `sync_neo4j_tool_catalog.py:430` 的 `MERGE (a)-[r:NEXT {source:...}]->(b)` 不包含 `kind/output/input`，同一工具对只留一条 relationship。少这一环，R2 边会覆盖 R1 边，或 tumor 边被 normal 边覆盖；目录看似有槽，四元组校验仍无法通过正确链。

### 1.3 配对资产取得

| 项目 | 估计 |
|---|---|
| 主要文件 | `pipeline_router.py:341-460,1023-1145,1760-1821`; 资产回归测试 |
| 代码改动 | 路由/组合约 40–70 行，契约 debug/provenance 10–20 行，测试 80–120 行 |
| schema 变更 | 无 CSV/Neo4j 工具 schema 变更；asset record 必须稳定保留 `individual_accession/sample_accession or run_accession/sample_role/mate` |
| 验收 | paired RNA 只返回同键 R1/R2；paired WES 只返回同 individual 的 tumor R1/R2 + normal R1/R2；任一方缺失或多义时 fail closed；输出 assets 四件都保留 role/mate |
| 独立发布 | 可，是收紧选择的安全改动；新槽尚未启用时不会改变工具接口 |

仓库已有 `_paired_fastq_groups()` 和 `_pair_wes_somatic_cases()` 的基础，但迁移验收要求这些维度从 matcher 一直传到 `agent_input.assets`，不能在 `file_details` 或列表截断中丢失。少这一环，后续绑定器没有足够信息做正确选择。

### 1.4 mate + sample_role 绑定

| 项目 | 估计 |
|---|---|
| 主要文件 | `workflow_composer.py:2069-2150,2200-2310`，尤其 `_build_assets()`、`_role_for_input()`、`_canonical_asset_role()`、`_select_asset()`、`_custom_tool_chain()` |
| 代码改动 | 资产维度与索引 50–80 行，绑定 50–90 行，测试 100–160 行 |
| schema 变更 | tool-chain/v1 **无变更**；目录 input spec 向内存 model 增加 `dimension/dimension_value`；asset 保留 role/mate metadata |
| 验收 | R1 槽只能选 mate=r1，R2 只能选 mate=r2；tumor 槽只能选 sample_role=tumor，normal 同理；同一资产不可被相互冲突的槽复用；没有精确候选时 missing_assets，不按列表位置回退 |
| 独立发布 | 可先以“识别新维度但旧目录不使用”的 dormant 能力发布；与新配对槽数据的启用必须原子发布 |

当前 `_select_asset()` 在 `workflow_composer.py:2307-2309` 使用角色内序号，候选用尽后会复用最后一个资产。它不看 `sample_role`。因此只补目录时，normal 链可能拿到 tumor R2，或 GATK normal BAM 拿到 tumor BAM。这是静默错绑，比目前诚实阻断更严重。

### 1.5 条件必需性 / variant 校验

| 项目 | 估计 |
|---|---|
| 主要文件 | `workflow_composer.py:128-147,1579-1717`; `scripts/python/sync_neo4j_tool_catalog.py`; `scripts/python/validate_csv.py`; Neo4j 目录读取；新 variant 测试 |
| 代码改动 | 目录 model 20–40 行，custom validator 70–110 行，同步/静态校验 50–80 行，测试 120–180 行 |
| schema 变更 | **有**：`tool_input_variant.csv` 与 slot.variant；运行时 method contract 增加 variants；tool-chain/v1 不变 |
| 验收 | fastp/STAR 单端只要 R1，双端必须 R1+R2；GATK single 不要 tumor/normal 槽，paired 必须两个 role + BAI；混用两个 variant 失败；MultiQC 所有 producer 槽都空时失败 |
| 独立发布 | 可先发布 legacy 变体兼容读取；新 variant 数据的启用必须与第 1.4 步和新槽原子发布 |

少这一环，有两种坏结果：把所有槽都标 required 会让单端/GATK single 永远缺数据；全标 optional 会让 paired 在缺 R2 或 normal 时通过。

## 2. 中间态安全性矩阵

| 中间态 | 可发布 | 原因 |
|---|---|---|
| 代码支持显式槽，数据仍为 legacy | 是 | 对当前 34 槽是等价读取 |
| NEXT MERGE 支持四元组，边仍为现有 14 条 | 是 | 不改变当前路径 |
| 资产取得更严格，槽仍为 legacy | 是 | 只会增加 fail-closed，不会扩大绑定 |
| 绑定器识别 dimension，但目录暂无 dimension | 是 | dormant 能力 |
| validator 识别 variant，但所有现有工具是 legacy variant | 是 | 行为等价 |
| 只加 R1/R2 或 tumor/normal 目录槽 | **否** | 现有绑定按角色列表取值并复用末项，可静默错绑 |
| 加新槽+新边，但无 variant | **否** | 单端/配对的必需集无法同时正确 |
| 五处代码都兼容，同一 release 切新槽/新边/新工具 | 是 | 这是第一个能安全启用目标数据的状态 |

结论：五处代码能力可逐步以向后兼容方式部署；**目标 CSV/Neo4j 数据、绑定启用和 variant 启用必须是一个原子发布边界**。

## 3. 同步器和静态校验的具体改动

### 3.1 `sync_neo4j_tool_catalog.py`

- `load_catalog()`（当前 158-190）：读完整 input/output schema 和 variant 表；不再只保存 semantic string list。
- `_sync_tool()`（当前 193-269）：`slot_id = tool_id::direction::slot_name`；`slot_name/artifact/required/wdl_type/dimension/variant` 均从 CSV 显式读取；移除 `OPTIONAL_INPUT_SLOTS` 作为生产真源。
- NEXT（当前 423-438）：不应先删全部再逐条覆盖。MERGE identity 包含 `source/kind/output/input`，或使用显式 `edge_id`；同步结束验证实际四元组集与 CSV 完全相等。
- 旧 slot/NEXT 清理要在新图校验成功后执行，并保留可恢复备份。

### 3.2 `workflow_composer.py` / catalog reader

- `RegisteredMethodCatalog._load()`（当前 158-193）的 `next_by_id[source].append(target)` 改为顺序去重；`data_edges` 仍保留完整四元组，不去重到工具对。
- method input spec 向 validator/binder 传播 `variant/dimension/dimension_value/execution_managed`，不再用 input name substring 作为主真源。
- `_validate_custom_steps()` 先从已绑定槽确定唯一 variant，再校验该 variant 的 required/min_present；无唯一解时 fail closed。

### 3.3 `validate_csv.py`

除现有 FK 外新增：

1. `(tool_id,direction,slot_name)` 唯一且非空；artifact 必须在 artifact/reference 枚举中。
2. required 只接受 `true/false`；input 必须属于已定义 variant。
3. 每个多 variant 工具 `exactly_one_variant=true`；每个 variant 至少有一槽，`min_present` 不超过可用槽数。
4. `dimension=mate` 只允许 r1/r2，`sample_role` 只允许 tumor/normal，同一 variant 不能重复 dimension value。
5. NEXT 五元组唯一；data 边的源/目标槽必须存在，方向必须 output→input，artifact 必须相同或在显式 compatibility 表中。
6. order 边必须留空 output/input；不允许 self-loop。
7. `wdl_binding` 应能在 `docs/wdl_inventory.json` 中找到；`command:` 例外必须有人工评审标记。

## 4. 迁移验收清单

- 四条 FASTQ 资产随机打乱后，tumor R1/R2 和 normal R1/R2 仍分别进入正确 step/slot。
- 交换任两个 `sample_role` 或 mate 标签时校验失败，不是运行成 ready。
- 同一 samtools step 不能同时填 tumor 和 normal GATK 槽；两个独立样本链必须在 GATK 汇合。
- paired_end 缺 R2、GATK paired 缺 normal/BAI、MultiQC 无任何 report 均失败关闭。
- single_end 不因 R2 缺失报 missing；GATK single 不要求 tumor/normal。
- 同一工具对的 R1/R2 两条 NEXT 和 samtools→GATK 多条 NEXT 全部在 Neo4j 存在，四元组逐条校验通过。
- stage-two 菜单的 `allowed_next_tool_ids` 无重复，但 validator 不因去重丢失 data edge 精度。
- CSV 静态校验、目录 dry-run、Neo4j 影子图对比、当前实测的 64 个旧用例和新增配对/variant 用例全通过后才能切换。

## 5. 拆解开工前必须决策

1. **槽命名真源**：建议用目录级稳定语义名，另存 WDL binding；不直接选 `read1`、`sample_r1`、`fastq_1` 中任一套局部名。
2. **多子命令边界**：建议一个可恢复的生物学阶段一节点，用 `operation_profile` 说明 samtools/GATK/bcftools 命令组；如坚持一子命令一节点，必须先决定 `tool-chain/v1` 是否新增 subcommand 字段和中间 artifact。
3. **报告粒度**：本规格建议“每 producer 一个 Array[File] 报告束”。需确认执行端能物化和 MultiQC 能消费；否则必须为 HTML/JSON/TXT 各建槽并解决聚合。
4. **16 工具 artifact**：只有 cellranger、driver_gene_gender、tmb_calculation 有独立 task 依据。其余 13 个先定 WDL 边界，再定 artifact；不要由包名猜测接口。
5. **variant 选择权**：是由 stage-two 显式输出 variant，还是 validator 从已绑槽唯一推导。本计划为了不改 tool-chain/v1，建议后者；无唯一解必须阻断。

## 6. 判断

最高风险的中间态已经明确：“目录有新槽，绑定器仍按角色列表顺序取值”。这不会继续诚实阻断，而会产生带 `sample_role` 展示的错误契约，所以新目录数据绝对不能单独上线。

多子命令工具应先围绕可物化的产物边界分阶段，再记录 operation profile。WDL 实际把许多子命令放在一个 task 内，说明“每个 CLI 子命令都是原子工具”并非现有执行契约。

1.5 节之外最重要的缺口是 MultiQC 的 `min_present=1` 和多 producer 扇入；它表明 variant 模型不只为 single/paired 服务，还要表达“若干可选输入中至少一个”。

如果明天开工，第一个 PR 应只实现显式槽 schema/NEXT 多边的向后兼容读写和校验，不加任何新目录行。第二阶段完成精确资产维度、绑定和 variant。只有两阶段都经过影子图验收，才在一个原子 release 切换目标目录数据。
