# 候选数据集配对角色规则评估

> 只读评估，未修改 `STUDY_ROLE_RULES`、代码、CSV 或 Neo4j。

## 0. 评估方法与口径

本报告复用了 `pipeline_router.py` 中的配对逻辑：

1. `files` 按 R1/R2 文件名模式归到同源配对键（sample/run/file stem）。
2. 仅当同源键下同时存在 R1、R2 时，才算 1 个可配对组。
3. 合格 case 定义：同一个体，肿瘤侧恰好 1 个配对组、正常侧恰好 1 个配对组。
4. 角色按 `specimen_types` 假设映射；未覆盖的样本记为未分类。
5. 测序类型以合并后的 `strategy` 字段为准（优先取 T1.strategy，T1 缺失时回退 T11.data_type）。

## 1. 受试者级 1:1 核对

### HRA001272 (Liver Cancer)

- 全部 FASTQ 文件数：`2360`（DNA 类 WES/WGS：`1500`）
- 有 FASTQ 的 individual 数：`206`
- 两侧都有 FASTQ 的 individual 数：`206`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（全部文件）：`124`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（仅 DNA 文件）：`124`
- 未分类角色的 individual 数：`0`

**两侧配对组数量组合分布（全部文件，(肿瘤侧组数, 正常侧组数) → 个体数）**

- (1, 1): 124
- (2, 1): 12
- (3, 1): 17
- (3, 2): 1
- (4, 1): 20
- (5, 1): 9
- (5, 2): 2
- (6, 1): 8
- (6, 2): 2
- (7, 1): 4
- (7, 2): 1
- (8, 1): 4
- (9, 1): 1
- (12, 2): 1

**两侧配对组数量组合分布（仅 DNA 文件）**

- (1, 1): 124
- (2, 1): 12
- (3, 1): 17
- (3, 2): 1
- (4, 1): 20
- (5, 1): 10
- (5, 2): 1
- (6, 1): 9
- (6, 2): 1
- (7, 1): 4
- (7, 2): 1
- (8, 1): 4
- (9, 1): 1
- (12, 2): 1

**每个 individual 的 specimen_types 组合分布**

- ('Patient Solid Tissue', 'Peritumoral'): 206

### HRA000071 (Glioma)

- 全部 FASTQ 文件数：`1144`（DNA 类 WES/WGS：`1144`）
- 有 FASTQ 的 individual 数：`572`
- 两侧都有 FASTQ 的 individual 数：`0`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（全部文件）：`0`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（仅 DNA 文件）：`0`
- 未分类角色的 individual 数：`0`

**两侧配对组数量组合分布（全部文件，(肿瘤侧组数, 正常侧组数) → 个体数）**

- (0, 1): 286
- (1, 0): 286

**每个 individual 的 specimen_types 组合分布**

- ('Blood',): 286
- ('Patient Solid Tissue',): 286

### HRA003107 (Esophageal Cancer)

- 全部 FASTQ 文件数：`1152`（DNA 类 WES/WGS：`532`）
- 有 FASTQ 的 individual 数：`155`
- 两侧都有 FASTQ 的 individual 数：`155`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（全部文件）：`155`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（仅 DNA 文件）：`127`
- 未分类角色的 individual 数：`0`

**两侧配对组数量组合分布（全部文件，(肿瘤侧组数, 正常侧组数) → 个体数）**

- (1, 1): 155

**两侧配对组数量组合分布（仅 DNA 文件）**

- (0, 1): 3
- (1, 0): 9
- (1, 1): 127

**每个 individual 的 specimen_types 组合分布**

- ('Patient Solid Tissue', 'Peritumoral'): 155

### HRA007169 (Melanoma)

- 全部 FASTQ 文件数：`336`（DNA 类 WES/WGS：`336`）
- 有 FASTQ 的 individual 数：`90`
- 两侧都有 FASTQ 的 individual 数：`51`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（全部文件）：`50`
- 单侧恰好 1 个 R1/R2 对的合格 case 数（仅 DNA 文件）：`50`
- 未分类角色的 individual 数：`25`

**两侧配对组数量组合分布（全部文件，(肿瘤侧组数, 正常侧组数) → 个体数）**

- (1, 0): 38
- (1, 1): 50
- (2, 0): 1
- (2, 1): 1

**每个 individual 的 specimen_types 组合分布**

- ('Blood', 'Patient Solid Tissue'): 25
- ('Patient Solid Tissue',): 14
- ('Patient Solid Tissue', 'Peritumoral'): 51

#### 以 Blood 作为正常侧重新计算

- 合格 case 数（全部文件）：`24`
- 合格 case 数（仅 DNA 文件）：`24`
- 两侧都有 FASTQ 的 individual 数：`25`
**组合分布（全部文件）：**

- (1, 0): 64
- (1, 1): 24
- (2, 0): 1
- (2, 1): 1

- 同时挂有 Peritumoral 和 Blood 的 individual 数：`0`

## 2. 两侧测序类型一致性

### HRA001272

**按推断角色汇总的 strategy 分布（仅 DNA 文件）：**

- tumor: {'WES': 1054}
- normal: {'WES': 446}
- ✅ 所有合格 case 的肿瘤/正常侧 strategy 一致。

### HRA000071

**按推断角色汇总的 strategy 分布（仅 DNA 文件）：**

- tumor: {'WES': 572}
- normal: {'WES': 572}
- ✅ 所有合格 case 的肿瘤/正常侧 strategy 一致。

### HRA003107

**按推断角色汇总的 strategy 分布（仅 DNA 文件）：**

- tumor: {'WGS': 272}
- normal: {'WGS': 260}
- ✅ 所有合格 case 的肿瘤/正常侧 strategy 一致。

### HRA007169

**按推断角色汇总的 strategy 分布（仅 DNA 文件）：**

- tumor: {'WES': 184}
- normal: {'WES': 102}
- unclassified: {'WES': 50}
- ✅ 所有合格 case 的肿瘤/正常侧 strategy 一致。

## 3. 命名后缀信号交叉验证

### HRA001272

**前 40 个 sample_name 与 specimen_types 示例**

| sample_name | specimen_types | 命名信号 |
| --- | --- | --- |
| `M019_LM1_S2010-10889_2` | Patient Solid Tissue | (none) |
| `M019_LM1_S2010-10889_3` | Patient Solid Tissue | (none) |
| `M019_LM2_S2011-21384_1` | Patient Solid Tissue | (none) |
| `M019_NC_S2008-50600_4` | Peritumoral | (none) |
| `M019_NC_S2009-04797_7` | Peritumoral | (none) |
| `M019_RT1_S2009-04797_2` | Patient Solid Tissue | (none) |
| `M019_RT1_S2009-04797_3` | Patient Solid Tissue | (none) |
| `M020_LM1_S2013-33618_1` | Patient Solid Tissue | (none) |
| `M020_LM1_S2013-33618_2` | Patient Solid Tissue | (none) |
| `M020_LM2_S2013-33618_6` | Patient Solid Tissue | (none) |
| `M020_NC_S2012-17847_9` | Peritumoral | (none) |
| `M020_PM_S2013-04700_1` | Patient Solid Tissue | (none) |
| `M020_RT1_S2012-17847_3` | Patient Solid Tissue | (none) |
| `M020_RT1_S2012-17847_5` | Patient Solid Tissue | (none) |
| `M020_RT2_S2012-17847_7` | Patient Solid Tissue | (none) |
| `M021_BM_S2013-16002_1` | Patient Solid Tissue | (none) |
| `M021_BM_S2013-16002_3` | Patient Solid Tissue | (none) |
| `M021_BM_S2013-16002_4` | Patient Solid Tissue | (none) |
| `M021_BM_S2013-16002_5` | Patient Solid Tissue | (none) |
| `M021_NC_S2010-21471_2` | Peritumoral | (none) |
| `M021_NC_S2013-05389_3` | Peritumoral | (none) |
| `M021_PT_S2008-62201_3` | Patient Solid Tissue | (none) |
| `M021_RT1_S2009-25752_1` | Patient Solid Tissue | (none) |
| `M021_RT2_S2010-21471_2` | Patient Solid Tissue | (none) |
| `M021_RT2_S2010-21471_4` | Patient Solid Tissue | (none) |
| `M021_RT3_S2013-05389_1` | Patient Solid Tissue | (none) |
| `M021_RT3_S2013-05389_2` | Patient Solid Tissue | (none) |
| `M021_RT3_S2013-05389_3` | Patient Solid Tissue | (none) |
| `M021_RT3_S2013-05389_4` | Patient Solid Tissue | (none) |
| `M026_AGM_S2011-05254_1` | Patient Solid Tissue | (none) |
| `M026_AGM_S2011-05254_3` | Patient Solid Tissue | (none) |
| `M026_NC_S2009-11336_3` | Peritumoral | (none) |
| `M028_AGM1_S2011-18928_1` | Patient Solid Tissue | (none) |
| `M028_AGM1_S2011-18928_2` | Patient Solid Tissue | (none) |
| `M028_AGM1_S2011-18928_3` | Patient Solid Tissue | (none) |
| `M028_AGM2_S2012-33378_3` | Patient Solid Tissue | (none) |
| `M028_NC_S2009-13981_4` | Peritumoral | (none) |
| `M028_PT_S2009-13981_8` | Patient Solid Tissue | (none) |
| `M029_AGM_S2011-03211_3` | Patient Solid Tissue | (none) |
| `M029_AGM_S2011-03211_4` | Patient Solid Tissue | (none) |

**specimen_types × 命名信号交叉表**

- `Patient Solid Tissue`: {'(none)': 485}
- `Peritumoral`: {'(none)': 213}

### HRA000071

**前 40 个 sample_name 与 specimen_types 示例**

| sample_name | specimen_types | 命名信号 |
| --- | --- | --- |
| `B_CGGA_1217` | Blood | (none) |
| `B_CGGA_1222` | Blood | (none) |
| `B_CGGA_1226` | Blood | (none) |
| `B_CGGA_1227` | Blood | (none) |
| `B_CGGA_1231` | Blood | (none) |
| `B_CGGA_1232` | Blood | (none) |
| `B_CGGA_1237` | Blood | (none) |
| `B_CGGA_1242` | Blood | (none) |
| `B_CGGA_1244` | Blood | (none) |
| `B_CGGA_1250` | Blood | (none) |
| `B_CGGA_1251` | Blood | (none) |
| `B_CGGA_1254` | Blood | (none) |
| `B_CGGA_1255` | Blood | (none) |
| `B_CGGA_1256` | Blood | (none) |
| `B_CGGA_1257` | Blood | (none) |
| `B_CGGA_1259` | Blood | (none) |
| `B_CGGA_1260` | Blood | (none) |
| `B_CGGA_1261` | Blood | (none) |
| `B_CGGA_1263` | Blood | (none) |
| `B_CGGA_1266` | Blood | (none) |
| `B_CGGA_1274` | Blood | (none) |
| `B_CGGA_1277` | Blood | (none) |
| `B_CGGA_1279` | Blood | (none) |
| `B_CGGA_1282` | Blood | (none) |
| `B_CGGA_1287` | Blood | (none) |
| `B_CGGA_1288` | Blood | (none) |
| `B_CGGA_1294` | Blood | (none) |
| `B_CGGA_1295` | Blood | (none) |
| `B_CGGA_1303` | Blood | (none) |
| `B_CGGA_1305` | Blood | (none) |
| `B_CGGA_1306` | Blood | (none) |
| `B_CGGA_1307` | Blood | (none) |
| `B_CGGA_1314` | Blood | (none) |
| `B_CGGA_1317` | Blood | (none) |
| `B_CGGA_1318` | Blood | (none) |
| `B_CGGA_1322` | Blood | (none) |
| `B_CGGA_1325` | Blood | (none) |
| `B_CGGA_1328` | Blood | (none) |
| `B_CGGA_1329` | Blood | (none) |
| `B_CGGA_1330` | Blood | (none) |

**specimen_types × 命名信号交叉表**

- `Blood`: {'(none)': 286}
- `Patient Solid Tissue`: {'(none)': 286}

### HRA003107

**前 40 个 sample_name 与 specimen_types 示例**

| sample_name | specimen_types | 命名信号 |
| --- | --- | --- |
| `BDESCC2-1N` | Peritumoral | N suffix (normal) |
| `BDESCC2-1T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-2N` | Peritumoral | N suffix (normal) |
| `BDESCC2-2T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-3N` | Peritumoral | N suffix (normal) |
| `BDESCC2-3T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-4N` | Peritumoral | N suffix (normal) |
| `BDESCC2-4T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-6N` | Peritumoral | N suffix (normal) |
| `BDESCC2-6T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-9N` | Peritumoral | N suffix (normal) |
| `BDESCC2-9T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-10N` | Peritumoral | N suffix (normal) |
| `BDESCC2-10T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-11N` | Peritumoral | N suffix (normal) |
| `BDESCC2-11T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-12N` | Peritumoral | N suffix (normal) |
| `BDESCC2-12T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-14N` | Peritumoral | N suffix (normal) |
| `BDESCC2-14T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-15N` | Peritumoral | N suffix (normal) |
| `BDESCC2-15T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-16N` | Peritumoral | N suffix (normal) |
| `BDESCC2-16T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-17N` | Peritumoral | N suffix (normal) |
| `BDESCC2-17T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-19N` | Peritumoral | N suffix (normal) |
| `BDESCC2-19T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-20N` | Peritumoral | N suffix (normal) |
| `BDESCC2-20T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-22N` | Peritumoral | N suffix (normal) |
| `BDESCC2-22T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-23N` | Peritumoral | N suffix (normal) |
| `BDESCC2-23T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-24N` | Peritumoral | N suffix (normal) |
| `BDESCC2-24T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-26N` | Peritumoral | N suffix (normal) |
| `BDESCC2-26T` | Patient Solid Tissue | T suffix (tumor) |
| `BDESCC2-29N` | Peritumoral | N suffix (normal) |
| `BDESCC2-29T` | Patient Solid Tissue | T suffix (tumor) |

**specimen_types × 命名信号交叉表**

- `Peritumoral`: {'N suffix (normal)': 155}
- `Patient Solid Tissue`: {'T suffix (tumor)': 155}

### HRA007169

**前 40 个 sample_name 与 specimen_types 示例**

| sample_name | specimen_types | 命名信号 |
| --- | --- | --- |
| `AM21P` | Peritumoral | P suffix (peri/normal) |
| `AM21T` | Patient Solid Tissue | T suffix (tumor) |
| `AM22P` | Peritumoral | P suffix (peri/normal) |
| `AM22T` | Patient Solid Tissue | T suffix (tumor) |
| `AM23B` | Blood | B suffix (blood) |
| `AM23T` | Patient Solid Tissue | T suffix (tumor) |
| `AM24P` | Peritumoral | P suffix (peri/normal) |
| `AM24T` | Patient Solid Tissue | T suffix (tumor) |
| `AM25B` | Blood | B suffix (blood) |
| `AM25T` | Patient Solid Tissue | T suffix (tumor) |
| `AM26B` | Blood | B suffix (blood) |
| `AM26T` | Patient Solid Tissue | T suffix (tumor) |
| `AM27B` | Blood | B suffix (blood) |
| `AM27T` | Patient Solid Tissue | T suffix (tumor) |
| `AM28B` | Blood | B suffix (blood) |
| `AM28T` | Patient Solid Tissue | T suffix (tumor) |
| `AM29B` | Blood | B suffix (blood) |
| `AM29T` | Patient Solid Tissue | T suffix (tumor) |
| `AM30B` | Blood | B suffix (blood) |
| `AM30T` | Patient Solid Tissue | T suffix (tumor) |
| `AM31B` | Blood | B suffix (blood) |
| `AM31T` | Patient Solid Tissue | T suffix (tumor) |
| `AM32B` | Blood | B suffix (blood) |
| `AM32T` | Patient Solid Tissue | T suffix (tumor) |
| `AM33B` | Blood | B suffix (blood) |
| `AM33T` | Patient Solid Tissue | T suffix (tumor) |
| `AM34B` | Blood | B suffix (blood) |
| `AM34T` | Patient Solid Tissue | T suffix (tumor) |
| `AM35B` | Blood | B suffix (blood) |
| `AM35T` | Patient Solid Tissue | T suffix (tumor) |
| `AM36B` | Blood | B suffix (blood) |
| `AM36T` | Patient Solid Tissue | T suffix (tumor) |
| `AM37B` | Blood | B suffix (blood) |
| `AM37T` | Patient Solid Tissue | T suffix (tumor) |
| `AM38B` | Blood | B suffix (blood) |
| `AM38T` | Patient Solid Tissue | T suffix (tumor) |
| `AM39B` | Blood | B suffix (blood) |
| `AM39T` | Patient Solid Tissue | T suffix (tumor) |
| `AM40B` | Blood | B suffix (blood) |
| `AM40T` | Patient Solid Tissue | T suffix (tumor) |

**specimen_types × 命名信号交叉表**

- `Peritumoral`: {'P suffix (peri/normal)': 51}
- `Patient Solid Tissue`: {'T suffix (tumor)': 90, '(none)': 2}
- `Blood`: {'B suffix (blood)': 25}

## 4. Blood 作为正常侧的判定

### 4.1 四个候选数据集的 tumor_type

- `HRA001272`: Liver Cancer
- `HRA000071`: Glioma
- `HRA003107`: Esophageal Cancer
- `HRA007169`: Melanoma

结论：四个数据集均为实体瘤（Glioma、Liver Cancer、Esophageal Cancer、Melanoma），因此从生物学角度，Blood 可作为种系正常对照。但 HRA000071 数据结构上不存在同个体 Solid+Blood。

### 4.2 HRA000071 的 Solid / Blood 是否在同一 individual

- 同时挂有 Solid + Blood 的 individual 数：`0`
- 只挂 Solid 的 individual 数：`286`
- 只挂 Blood 的 individual 数：`286`

因此按当前“同 individual 配对”规则，HRA000071 无法产出任何合格 case。

### 4.3 全库哪些 study 有 Blood 样本

- `HRA000071`: Blood 286 个, tumor_type=Glioma
- `HRA000122`: Blood 42 个, tumor_type=Leukemia
- `HRA007169`: Blood 25 个, tumor_type=Melanoma
- `HRA006499`: Blood 12 个, tumor_type=Liver Cancer
- `HRA001748`: Blood 10 个, tumor_type=Liver Cancer
- `HRA001749`: Blood 10 个, tumor_type=Liver Cancer

## 5. HRA003107 作为 WGS 的说明

HRA003107 的 T1 strategy 为 `WGS`（532 文件）+ `RNA-Seq`（620 文件）。
若仅过滤为 DNA（WGS/WES），合格配对数见上表。

- 当前 `wes_somatic_pair` 的允许 strategy 集合包含 WGS，因此技术上可以纳入。
- 但流程名称是 `wes_somatic_pair`，目录里没有捕获区间建模；是否把 WGS 作为一等公民，需要与目录负责人确认范围定义。

## 6. 登记提案（不实施）

| 数据集 | 建议 | 判据类型 | 预计新增合格配对 | 阻碍/条件 |
| --- | --- | --- | --- | --- |
| HRA001272 | ⚠️ 有条件 | specimen_types | 124 | 需确认单侧恰好 1 对的个体是否接受；当前严格口径为 124 对。 |
| HRA000071 | ❌ 不建议 | Blood 正常侧 | 0 | 当前数据无同 individual Solid+Blood；若支持跨个体配对则有 286 对潜力，需改规则语义。 |
| HRA003107 | ⚠️ 有条件 | specimen_types | 127 | 测序类型为 WGS（DNA 文件 532 个）；流程名为 WES，需确认范围定义。 |
| HRA007169 | ⚠️ 有条件 | specimen_types | 50 (Peri) / 24 (Blood) | 若正常侧取 Peritumoral 得 50 对；取 Blood 得 24 对；需决定 Blood 是否可作为正常侧。 |

当前已登记数据集可用配对总数：`1028`。
若按上表全部登记（HRA007169 取 Peritumoral 口径），总数将变为约：`1329`。

## 7. 影响预估（不实施）

- `wes_somatic_pair` 的可行 study 数将从 2 增加到最多 4（HRA000873、HRA006499 + HRA001272、HRA003107/HRA007169 视条件而定）。
- 演示查询“配对肿瘤正常 WES”当前已绑定 HRA000873；加入 HRA001272 后，由于 HRA000873 的配对数（1015）远高于 HRA001272（124），默认排序大概率仍选 HRA000873。
- 若移除排序加分并启用“有角色规则且能产出合格 case 的 study 优先”，HRA000873 仍占优，因此演示脚本依赖的 HRA000873 绑定风险较低。

## 8. 判断与建议

- **最优先登记**：HRA001272。标本类型映射清晰（Solid Tissue = tumor，Peritumoral = normal），且个体级 1:1 结构最干净；需先确认 124 对严格 case 是否满足业务口径。
- **最大风险点**：HRA000071 的 Blood 正常侧是新语义。当前没有同 individual 配对证据；若将来要支持 Blood 作为正常侧，需要明确区分“肿瘤种系对照”与“血液肿瘤”场景。
- **未问到但值得查**：这四个数据集的 `sample_name` 几乎没有 `_T/_N` 后缀，无法像 HRA006499 那样做独立验证；登记后应通过运行样本抽检确认角色正确率。

## 9. 实际执行的脚本

本报告所有数字来自只读脚本：

- `scripts/python/evaluate_candidate_study_roles.py`

该脚本读取 `data/csv/entities/T1.csv`、`data/csv/T11.csv`、`data/csv/entities/sample.csv`、`data/csv/entities/study.csv` 以及 `data/csv/relations/T1_in_format.csv`，复现 `pipeline_router._load_normalized_t1` 与 `_paired_fastq_groups` 的合并/配对逻辑，未写入任何源数据文件。
