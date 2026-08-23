# 0821 交付：sample 字段口径

这份对应 light 版 `web/manual_compact.md` 的同名章节。两边结论一致，但**落点不同**：
light 版是 LLM 直接写 Cypher，所以规则写在手册里给模型看；本仓库是代码自己查图、
LLM 只做编排，所以四条规则必须落到代码里才有效——写进文档而不改代码，等于没改。

对应的代码落点与回归防护：

| 规则 | 代码落点 | 锁在哪 |
| --- | --- | --- |
| `tumor_descriptor` 不可用 | `UNRELIABLE_SAMPLE_FIELDS` | `UnreliableFieldsStayUnused` |
| `biospecimen_anatomic_site` 不可用 | 同上 | 同上 |
| 分原发/转移/复发看样本名 | `sample_lesion()` / `LESION_BY_NAME_CODE` | `LesionComesFromSampleName` |
| `gender` 一律小写 | `normalize_gender()` | `GenderIsCaseInconsistent` |
| `specimen_type` 用子串不用等号 | `specimen_tokens()` | `SpecimenTypeIsMultiValued` |

---

## 0. 这批坏值为什么值得单开一份文档

不是空、不是乱码、不是缺列。每一格都填满，每个值单看都合理，结构完全合法——
0821 那版把若干**研究级别的默认值**覆盖到了**样本级别的事实**上。

最清楚的一个例子，HRA001272（肝癌，698 个样本）：

```
旧 biospecimen_anatomic_site: Liver 522, Lung 70, Peritoneal 38, Bone 20,
                              Adrenal Gland 19, Lymph Node 19, Brain 5,
                              Kidney 2, Spleen 2, Diaphragm 1
新 biospecimen_anatomic_site: Liver And Intrahepatic Bile Ducts  698   ← 全部
```

而样本名自己就写着取材部位：`M019_LM1_…`（LM=肺转移）、`M021_BM_…`（BM=骨转移）、
`M026_AGM_…`（AGM=肾上腺转移）、`M033_KM_…`（KM=肾转移）——**全被改写成了"肝"**。

查回包看不出任何异常。只有拿样本名这种**独立信号**交叉验证才露馅。这正是本项目
反复出现的那类错：**错得像对**。

同一件事也发生在 `tumor_descriptor` 上：这 698 个样本的 Metastatic 176、Recurrent 28
全部变成了 `Primary`。

---

## 1. `tumor_descriptor` 不能用来分原发/转移/复发

```
全库 Metastatic：210 → 0
全库 Recurrent ：407 → 0
其中 605 个样本明确从 Metastatic/Recurrent 改写成了 Primary
新数据剩下：Primary 8551 / Metastasis 12 / 空 1902
```

新值里那 12 个 `Metastasis`（注意连拼写都换了）**全部落在 `tissue_type=Normal` 的
样本上**。反过来，**1476 个 `tissue_type=Normal` 的样本带上了肿瘤分期**
（Primary 1470、Metastasis 6）——正常样本标着"原发肿瘤"。

HRA000071 丢掉的 106 个 `Recurrent` 尤其要命：原发/复发配对本来就是 CGGA 这个队列的
核心设计，这一列没了，这个队列最主要的用法就没了。

## 2. `biospecimen_anatomic_site` 是研究级原发部位，不是样本取材部位

1886 个样本的该字段被改写，全库不同取值 19 → 18。HRA001272 的塌缩见上；HRA006499
的 `['Blood','Liver']` 同样被压成单值。**拿它筛转移部位必然全错。**

## 3. 要分原发/转移/复发，看 `sample_name`

`LESION_BY_NAME_CODE`（`pipeline_router.py`）登记的是核对过的队列。HRA001272 的编码
（正则 `^[A-Za-z]?\d+[_.]([A-Za-z]+)\d*[_.]`，形如 `M019_LM1_S2010-10889_2`）：

| 代码 | 含义 | 数量 | 代码 | 含义 | 数量 |
| --- | --- | ---: | --- | --- | ---: |
| `PT` | 原发 | 263 | `LNM` | 淋巴结转移 | 19 |
| `NC` | 癌旁对照 | 205 | `BM` | 骨转移 | 20 |
| `LM` | 肺转移 | 65 | `BRM` | 脑转移 | 5 |
| `PM` | 腹膜转移 | 31 | `KM` | 肾转移 | 2 |
| `RT` | 复发 | 28 | `DM` | 远处转移 | 1 |
| `AGM` | 肾上腺转移 | 19 | *(不合模式)* | | 40 |

> 计数口径：上表是按上述正则数**样本**，合计 698。light 版手册给的是另一组数
> （PT 143 / NC 85 …，合计 417），差在口径不在结论——两边认定的代码含义完全一致，
> 十种转移灶都实打实存在。要引用数字时说明数的是样本还是个体。

**与 `tissue_type` 的一致性已核对**：HRA001272 的 `NC` 全部 205 个是 `Normal`，其余
代码全部是 `Tumor`，无一例外。所以这张表补的是**原发/转移/复发**这一维，
不是 tumor/normal 那一维——角色照常走 `_sample_role()`。

只登记核对过的队列，是因为命名习惯各队列不同：`BM` 在这里是 Bone Metastasis，
而全库有 1208 个样本的 `specimen_type` 就叫 `Bone_Marrow`。**分不出就返回 None**，
绝不回头去读 `tumor_descriptor` 凑一个答案——那个字段会给出一个填满的、看着合理的、
错的值。

## 4. `gender` 大小写不统一

```
旧: Male 6532, Female 3932, 空 1
新: Male 6474, Female 3931, male 56, female 3, missing 1
```

`== "Male"` 会**静默漏掉 56 个样本**。字面量 `missing` 是"没这个信息"被写成了字符串，
不归一化会让性别分层分析多出一个不存在的第三组。一律走 `normalize_gender()`。

## 5. `specimen_type` 各队列口径不一，且新增了分号多值

```
Patient_Solid_Tissue           7282
Bone_Marrow                    1208
Blood                           944
Peritumoral                     508
Organoid;Patient_Solid_Tissue   486   ← 新增的多值
Organoid                         30
(空)                              7
```

**癌旁 `Peritumoral` 只在 HRA000021（508）保留**，另外六个队列的 525 个被并成了
`Patient_Solid_Tissue`：HRA001272 213、HRA003107 155、HRA001749 84、HRA007169 51、
HRA001748 14、HRA006499 8。这比"统一丢失"更阴险——同一个概念在不同队列不同写法。

好消息是这 525 个的 `tissue_type` 仍然全是 `Normal`，**配对分析走 `tissue_type`
不受影响**，所以这条的严重性低一档。

那 486 个分号多值在 HRA005191（54）与 HRA006499（432）。**用等号比会把它们整个漏掉，
而且不报错**——这些样本只是悄悄判不出角色，用户看到的是"配不出对"，而不是
"有 486 个样本没被算进去"。一律走 `specimen_tokens()`。

---

## 6. 还有两条，一条是真损坏，一条影响判存在性

**45 个 `Blood` → `Patient_Solid_Tissue`**：HRA007169 25、HRA001748 10、HRA001749 10。
样本名 `A116_HCC_B`、`AM42B`、`A120_HCC.B` 的 `B` 后缀说明它们确实是血样。**血样被
标成了实体瘤**，这条是真损坏。这三个队列都不在 `STUDY_ROLE_OVERRIDES` 里，角色回退
到 `tissue_type`，所以暂时没被引爆——但谁要给这几个队列加 `specimen_type` 规则，
就会踩上。

**`tissue_type` 有 829 个样本为空**（且其中带着 `tumor_descriptor`），分布在
HRA000074 543、HRA005191 243、HRA000122 42、HRA000087 1。判存在性用"非空"，
不要假定它一定有值。`_sample_role()` 遇到空值返回 `None`，这是对的行为——
判不出就是判不出。

---

## 7. 这次交付确实修对了的

打回去的时候得把这几条一起说，否则像是在否定整次交付：

* **sample→run 多值补全**（师兄 0821 提的正是这条）：1955 个样本补上了此前缺失的
  run，run 编号总数 10234 → 13736（+3502）；`experiment_accession` 2176 条、
  `strategy` 2345 条同步补全。
* **下划线粘连修复**：`sample_description` 1745 条（`'Primary_tumor_(liver)'` →
  `'Primary tumor (liver)'`）、`individual_name` 182 条（`'A_066'` → `'A066'`）。
* **HRA000071 的 `tissue_type` 是真修对了**。这条我一开始误判成事故：111 个
  Tumor→Normal 翻转，看着像数据损坏。拿样本名交叉验证后**旧数据才是错的**——
  572 个样本 `B_` 前缀 286 / `T_` 前缀 286 完美配对，新数据 B→Normal 286、
  T→Tumor 286 且 specimen_type 恰好 Blood 286 / Solid 286，内部自洽；旧数据是
  B→182 Normal + 104 Tumor，自相矛盾。
  **这条记在这里是因为它证明了方法本身**：同一套样本名交叉验证，既能证伪新数据
  （第 0 节），也能证伪旧数据。只朝一个方向用，就成了找茬。

## 8. 一条口径分歧，不是谁错

`project_accession` 909 条，两边说的都成立，基线不同：

* 对 **CSV vs CSV**：909 条全是 `''` → `PRJCA***` 的补全，纯改进。
* 对 **已加载的图谱 vs 新 CSV**：909 条是有值 → 不同有值（如 HRA006117 的
  `PRJCA020863` → `PRJCA010519`），一条空值都没有。

也就是说图里现有的 `project_accession` 不是从上一版 sample.csv 来的（那一版是空），
而是别的路径填进去的，**它和 0821 CSV 的断言不一致**。哪个对需要师兄确认，
优先级低——本仓库没有按 project 过滤的逻辑。

---

## 9. 复跑

```bash
python3 -m unittest discover -s tests -t tests -p 'test_sample_field_semantics.py' -v
```
