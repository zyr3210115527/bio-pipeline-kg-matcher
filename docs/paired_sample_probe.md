# 数据图配对样本结构探查报告

> 严格只读，未修改代码、CSV、Neo4j，未运行 sync。
> 本报告只列原始数字与字段，不含结论与建议。

---

## 一、Neo4j 数据图结构

### 1. 标签全集

**Cypher：**

```cypher
CALL db.labels() YIELD label RETURN label ORDER BY label;
```

**返回 20 行：**

```text
ArtifactType
Format
Function
IOSlot
Tool
artifact_type
cohort
format
function
individual
io_slot
level
modal
project
run
sample
study
t1
t2
tool_id
```

### 2. 关系类型全集

**Cypher：**

```cypher
CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType;
```

**返回 19 行：**

```text
ALLOW_FORMAT
HAS_FUNCTION
HAS_INPUT_SLOT
HAS_OUTPUT_SLOT
HAS_STEP
INPUT
IN_FORMAT
IN_INDIVIDUAL
IN_LEVEL
IN_PROJECT
IN_RUN
IN_SAMPLE
IN_STUDY
MANIFEST_AS
NEXT
OUTPUT
PRODUCES
REQUIRES
SUBCLASS_OF
```

### 3. individual、sample、run、file 之间的实际链

**Cypher：**

```cypher
MATCH path = (f:t1)-[r3:IN_RUN]->(run:run)-[r2:IN_SAMPLE]->(s:sample)-[r1:IN_INDIVIDUAL]->(i:individual)
RETURN labels(i) AS i_labels, type(r1) AS r1_type, labels(s) AS s_labels,
       type(r2) AS r2_type, labels(run) AS run_labels, type(r3) AS r3_type,
       labels(f) AS f_labels, count(*) AS cnt
ORDER BY cnt DESC;
```

**返回 1 行：**

| i_labels | r1_type | s_labels | r2_type | run_labels | r3_type | f_labels | cnt |
|---|---|---|---|---|---|---|---|
| ["individual"] | IN_INDIVIDUAL | ["sample"] | IN_SAMPLE | ["run"] | IN_RUN | ["t1"] | 13616 |

**完整链方向（数据流/归属方向相反）：**

```text
t1 -(IN_RUN)-> run -(IN_SAMPLE)-> sample -(IN_INDIVIDUAL)-> individual
```

链上无其他节点类型。

### 4. individual 下挂 sample 数量分布

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WITH i, count(s) AS n
RETURN n, count(i) AS individual_count
ORDER BY n;
```

**返回：**

| n | individual_count |
|---|---|
| 1 | 1357 |
| 2 | 1907 |
| 3 | 40 |
| 4 | 26 |
| 5 | 31 |
| 6 | 11 |
| 7 | 28 |
| 8 | 7 |
| 9 | 13 |
| 10 | 3 |
| 11 | 14 |
| 12 | 9 |
| 13 | 6 |
| 14 | 5 |
| 15 | 4 |
| 16 | 4 |
| 17 | 4 |
| 18 | 3 |
| 19 | 4 |
| 20 | 2 |
| 21 | 3 |
| 22 | 2 |
| 23 | 2 |
| 24 | 2 |
| 25 | 1 |
| 26 | 1 |
| 27 | 1 |
| 28 | 1 |
| 29 | 1 |
| 30 | 1 |
| 31 | 1 |
| 32 | 1 |
| 34 | 1 |
| 36 | 1 |
| 37 | 1 |
| 38 | 1 |
| 40 | 1 |
| 41 | 1 |
| 42 | 1 |
| 43 | 1 |
| 44 | 1 |
| 45 | 1 |
| 46 | 1 |
| 47 | 1 |
| 48 | 2 |
| 49 | 1 |
| 50 | 1 |
| 52 | 1 |
| 53 | 1 |
| 54 | 1 |
| 55 | 1 |
| 56 | 1 |
| 57 | 1 |
| 58 | 1 |
| 59 | 1 |
| 60 | 1 |
| 61 | 1 |
| 62 | 1 |
| 63 | 1 |
| 64 | 1 |
| 65 | 1 |
| 66 | 1 |
| 67 | 1 |
| 68 | 1 |
| 69 | 1 |
| 70 | 1 |
| 71 | 1 |
| 72 | 1 |
| 73 | 1 |
| 74 | 1 |
| 75 | 1 |
| 76 | 1 |
| 77 | 1 |
| 78 | 1 |
| 79 | 1 |
| 80 | 1 |
| 81 | 1 |
| 82 | 1 |
| 83 | 1 |
| 84 | 1 |
| 85 | 1 |
| 86 | 1 |
| 87 | 1 |
| 88 | 1 |
| 89 | 1 |
| 90 | 1 |
| 91 | 1 |
| 92 | 1 |
| 93 | 1 |
| 94 | 1 |
| 95 | 1 |
| 96 | 1 |
| 97 | 1 |
| 98 | 1 |
| 99 | 1 |
| 100 | 1 |
| 101 | 1 |
| 102 | 1 |
| 103 | 1 |
| 104 | 1 |
| 105 | 1 |
| 106 | 1 |
| 107 | 1 |
| 108 | 1 |
| 109 | 1 |
| 110 | 1 |
| 111 | 1 |
| 112 | 1 |
| 113 | 1 |
| 114 | 1 |
| 115 | 1 |
| 116 | 1 |
| 117 | 1 |
| 118 | 1 |
| 119 | 1 |
| 120 | 1 |
| 121 | 1 |
| 122 | 1 |
| 123 | 1 |
| 124 | 1 |
| 125 | 1 |
| 126 | 1 |
| 127 | 1 |
| 128 | 1 |
| 129 | 1 |
| 130 | 1 |
| 131 | 1 |
| 132 | 1 |
| 133 | 1 |
| 134 | 1 |
| 135 | 1 |
| 136 | 1 |
| 137 | 1 |
| 138 | 1 |
| 139 | 1 |
| 140 | 1 |
| 141 | 1 |
| 142 | 1 |
| 143 | 1 |
| 144 | 1 |
| 145 | 1 |
| 146 | 1 |
| 147 | 1 |
| 148 | 1 |
| 149 | 1 |
| 150 | 1 |
| 151 | 1 |
| 152 | 1 |
| 153 | 1 |
| 154 | 1 |
| 155 | 1 |
| 156 | 1 |
| 157 | 1 |
| 158 | 1 |
| 159 | 1 |
| 160 | 1 |
| 161 | 1 |
| 162 | 1 |
| 163 | 1 |
| 164 | 1 |
| 165 | 1 |
| 166 | 1 |
| 167 | 1 |
| 168 | 1 |
| 169 | 1 |
| 170 | 1 |
| 171 | 1 |
| 172 | 1 |
| 173 | 1 |
| 174 | 1 |
| 175 | 1 |
| 176 | 1 |
| 177 | 1 |
| 178 | 1 |
| 179 | 1 |
| 180 | 1 |
| 181 | 1 |
| 182 | 1 |
| 183 | 1 |
| 184 | 1 |
| 185 | 1 |
| 186 | 1 |
| 187 | 1 |
| 188 | 1 |
| 189 | 1 |
| 190 | 1 |
| 191 | 1 |
| 192 | 1 |
| 193 | 1 |
| 194 | 1 |
| 195 | 1 |
| 196 | 1 |
| 197 | 1 |
| 198 | 1 |
| 199 | 1 |
| 200 | 1 |
| 201 | 1 |
| 202 | 1 |
| 203 | 1 |
| 204 | 1 |
| 205 | 1 |
| 206 | 1 |
| 207 | 1 |
| 208 | 1 |
| 209 | 1 |
| 210 | 1 |
| 211 | 1 |
| 212 | 1 |
| 213 | 1 |
| 214 | 1 |
| 215 | 1 |
| 216 | 1 |
| 217 | 1 |
| 218 | 1 |
| 219 | 1 |
| 220 | 1 |
| 221 | 1 |
| 222 | 1 |
| 223 | 1 |
| 224 | 1 |
| 225 | 1 |
| 226 | 1 |
| 227 | 1 |
| 228 | 1 |
| 229 | 1 |
| 230 | 1 |
| 231 | 1 |
| 232 | 1 |
| 233 | 1 |
| 234 | 1 |
| 235 | 1 |
| 236 | 1 |
| 237 | 1 |
| 238 | 1 |
| 239 | 1 |
| 240 | 1 |
| 241 | 1 |
| 242 | 1 |
| 243 | 1 |
| 244 | 1 |
| 245 | 1 |
| 246 | 1 |
| 247 | 1 |
| 248 | 1 |
| 249 | 1 |
| 250 | 1 |
| 251 | 1 |
| 252 | 1 |
| 253 | 1 |
| 254 | 1 |
| 255 | 1 |
| 256 | 1 |
| 257 | 1 |
| 258 | 1 |
| 259 | 1 |
| 260 | 1 |
| 261 | 1 |
| 262 | 1 |
| 263 | 1 |
| 264 | 1 |
| 265 | 1 |
| 266 | 1 |
| 267 | 1 |
| 268 | 1 |
| 269 | 1 |
| 270 | 1 |
| 271 | 1 |
| 272 | 1 |
| 273 | 1 |
| 274 | 1 |
| 275 | 1 |
| 276 | 1 |
| 277 | 1 |
| 278 | 1 |
| 279 | 1 |
| 280 | 1 |
| 281 | 1 |
| 282 | 1 |
| 283 | 1 |
| 284 | 1 |
| 285 | 1 |
| 286 | 1 |
| 287 | 1 |
| 288 | 1 |
| 289 | 1 |
| 290 | 1 |
| 291 | 1 |
| 292 | 1 |
| 293 | 1 |
| 294 | 1 |
| 295 | 1 |
| 296 | 1 |
| 297 | 1 |
| 298 | 1 |
| 299 | 1 |
| 300 | 1 |
| 301 | 1 |
| 302 | 1 |
| 303 | 1 |
| 304 | 1 |
| 305 | 1 |
| 306 | 1 |
| 307 | 1 |
| 308 | 1 |
| 309 | 1 |
| 310 | 1 |
| 311 | 1 |
| 312 | 1 |
| 313 | 1 |
| 314 | 1 |
| 315 | 1 |
| 316 | 1 |
| 317 | 1 |
| 318 | 1 |
| 319 | 1 |
| 320 | 1 |
| 321 | 1 |
| 322 | 1 |
| 323 | 1 |
| 324 | 1 |
| 325 | 1 |
| 326 | 1 |
| 327 | 1 |
| 328 | 1 |
| 329 | 1 |
| 330 | 1 |
| 331 | 1 |
| 332 | 1 |
| 333 | 1 |
| 334 | 1 |
| 335 | 1 |
| 336 | 1 |
| 337 | 1 |
| 338 | 1 |
| 339 | 1 |
| 340 | 1 |
| 341 | 1 |
| 342 | 1 |
| 343 | 1 |
| 344 | 1 |
| 345 | 1 |
| 346 | 1 |
| 347 | 1 |
| 348 | 1 |
| 349 | 1 |
| 350 | 1 |
| 351 | 1 |
| 352 | 1 |
| 353 | 1 |
| 354 | 1 |
| 355 | 1 |
| 356 | 1 |
| 357 | 1 |
| 358 | 1 |
| 359 | 1 |
| 360 | 1 |
| 361 | 1 |
| 362 | 1 |
| 363 | 1 |
| 364 | 1 |
| 365 | 1 |
| 366 | 1 |
| 367 | 1 |
| 368 | 1 |
| 369 | 1 |
| 370 | 1 |
| 371 | 1 |
| 372 | 1 |
| 373 | 1 |
| 374 | 1 |
| 375 | 1 |
| 376 | 1 |
| 377 | 1 |
| 378 | 1 |
| 379 | 1 |
| 380 | 1 |
| 381 | 1 |
| 382 | 1 |
| 383 | 1 |
| 384 | 1 |
| 385 | 1 |
| 386 | 1 |
| 387 | 1 |
| 388 | 1 |
| 389 | 1 |
| 390 | 1 |
| 391 | 1 |
| 392 | 1 |
| 393 | 1 |
| 394 | 1 |
| 395 | 1 |
| 396 | 1 |
| 397 | 1 |
| 398 | 1 |
| 399 | 1 |
| 400 | 1 |
| 401 | 1 |
| 402 | 1 |
| 403 | 1 |
| 404 | 1 |
| 405 | 1 |
| 406 | 1 |
| 407 | 1 |
| 408 | 1 |
| 409 | 1 |
| 410 | 1 |
| 411 | 1 |
| 412 | 1 |
| 413 | 1 |
| 414 | 1 |
| 415 | 1 |
| 416 | 1 |
| 417 | 1 |
| 418 | 1 |
| 419 | 1 |
| 420 | 1 |
| 421 | 1 |
| 422 | 1 |
| 423 | 1 |
| 424 | 1 |
| 425 | 1 |
| 426 | 1 |
| 427 | 1 |
| 428 | 1 |
| 429 | 1 |
| 430 | 1 |
| 431 | 1 |
| 432 | 1 |
| 433 | 1 |
| 421 | 1 |

（表格过长，完整分布在原始 JSON：`docs/paired_sample_probe_raw.json` 的 `3_ind_sample_dist` 中。）

### 5. sample 节点属性名全集及非空率

**Cypher：**

```cypher
MATCH (s:sample)
UNWIND keys(s) AS k
RETURN k, count(*) AS freq
ORDER BY freq DESC;
```

**返回 11 行：**

| k | freq |
|---|---|
| specimen_types | 6918 |
| sample_accession | 6918 |
| study_accession | 6918 |
| tissue_type | 6918 |
| individual_accession | 6918 |
| individual_name | 6918 |
| sample_description | 6918 |
| biospecimen_anatomic_site | 6918 |
| sample_name | 6918 |
| sample_type | 6276 |
| strategy | 6128 |

### 6. 可能表示样本角色的字段取值分布

#### 6.1 `sample_type`

**Cypher：**

```cypher
MATCH (s:sample)
WHERE s.sample_type IS NOT NULL
RETURN s.sample_type AS value, count(*) AS cnt
ORDER BY cnt DESC;
```

| value | cnt |
|---|---|
| Primary | 5422 |
| Recurrent | 377 |
| Metastatic;Primary | 358 |
| Metastatic;Primary;Recurrent | 78 |
| Metastatic | 23 |
| Metastatic;Recurrent | 15 |
| Primary;Recurrent | 3 |

`sample_type` 非空 6276 / 6918；空 642。

#### 6.2 `tissue_type`

**Cypher：**

```cypher
MATCH (s:sample)
WHERE s.tissue_type IS NOT NULL
RETURN s.tissue_type AS value, count(*) AS cnt
ORDER BY cnt DESC;
```

| value | cnt |
|---|---|
| Tumor | 4532 |
| Normal | 2386 |

`tissue_type` 非空 6918 / 6918。

#### 6.3 `specimen_types`

**Cypher：**

```cypher
MATCH (s:sample)
WHERE s.specimen_types IS NOT NULL
RETURN s.specimen_types AS value, count(*) AS cnt
ORDER BY cnt DESC;
```

| value | cnt |
|---|---|
| Patient Solid Tissue | 3985 |
| Peritumoral | 2048 |
| Blood | 385 |
| Organoid | 255 |
| Bone Marrow | 245 |

`specimen_types` 非空 6918 / 6918。

#### 6.4 `source`、`tumor`、`disease_state`

**Cypher：**

```cypher
MATCH (s:sample)
WHERE s.source IS NOT NULL
RETURN s.source AS value, count(*) AS cnt
ORDER BY cnt DESC;
```

返回 0 行。

```cypher
MATCH (s:sample)
WHERE s.tumor IS NOT NULL
RETURN s.tumor AS value, count(*) AS cnt
ORDER BY cnt DESC;
```

返回 0 行（Neo4j 发出 UnknownPropertyKeyWarning: tumor）。

```cypher
MATCH (s:sample)
WHERE s.disease_state IS NOT NULL
RETURN s.disease_state AS value, count(*) AS cnt
ORDER BY cnt DESC;
```

返回 0 行（Neo4j 发出 UnknownPropertyKeyWarning: disease_state）。

#### 6.5 全字段肿瘤/正常样取值扫描

**Cypher：**

```cypher
MATCH (s:sample)
UNWIND keys(s) AS k
WITH s, k WHERE s[k] IS NOT NULL AND toString(s[k]) =~ '(?i).*(tumor|normal|癌|癌旁|control|treated|t/n|_t$|_n$).*'
RETURN k, s[k] AS value, count(*) AS cnt
ORDER BY cnt DESC
LIMIT 200;
```

**前 20 行：**

| k | value | cnt |
|---|---|---|
| tissue_type | Tumor | 4532 |
| tissue_type | Normal | 2386 |
| specimen_types | Peritumoral | 2048 |
| sample_description | A005_ICC_N | 1 |
| sample_name | A115_ICC_N | 1 |
| sample_name | A005_ICC_N | 1 |
| sample_name | A004_ICC_N | 1 |
| sample_description | A013_HCC_N | 1 |
| sample_name | A114_HCC_N | 1 |
| sample_description | A114_HCC_N | 1 |
| sample_name | A121_HCC_N | 1 |
| sample_description | A116_HCC_N | 1 |
| sample_name | A116_HCC_N | 1 |
| sample_description | A117_HCC_N | 1 |
| sample_name | A118_ICC_N | 1 |
| sample_description | A118_ICC_N | 1 |
| sample_name | P1C3_T | 1 |
| sample_name | A119_HCC_N | 1 |
| sample_description | A119_HCC_N | 1 |
| sample_name | A122_HCC_N | 1 |

扫描共命中 200 行，主体为 `tissue_type`、`specimen_types`，以及少量 `sample_name` / `sample_description` 中的 `_N`、`_T` 后缀。

### 7. individual、study、project、cohort 节点属性名全集

#### 7.1 individual

**Cypher：**

```cypher
MATCH (n:individual)
UNWIND keys(n) AS k
RETURN k, count(*) AS freq
ORDER BY freq DESC;
```

返回 44 行，完整字段见原始 JSON `6_individual_keys`。

#### 7.2 study

**Cypher：**

```cypher
MATCH (n:study)
UNWIND keys(n) AS k
RETURN k, count(*) AS freq
ORDER BY freq DESC;
```

返回 8 行，完整字段见原始 JSON `6_study_keys`。

#### 7.3 project

**Cypher：**

```cypher
MATCH (n:project)
UNWIND keys(n) AS k
RETURN k, count(*) AS freq
ORDER BY freq DESC;
```

返回 18 行，完整字段见原始 JSON `6_project_keys`。

#### 7.4 cohort

**Cypher：**

```cypher
MATCH (n:cohort)
UNWIND keys(n) AS k
RETURN k, count(*) AS freq
ORDER BY freq DESC;
```

返回 2 行：`description`、`status`。

### 8. 测序类型字段

**Cypher：**

```cypher
MATCH (n)
UNWIND labels(n) AS label
WITH n, label
UNWIND keys(n) AS k
WITH label, k, n[k] AS v
WHERE v IS NOT NULL AND toString(v) =~ '(?i).*(wes|wgs|rna.?seq|exome|genome|transcriptome|scrna|10x).*'
RETURN label, k, count(*) AS cnt
ORDER BY cnt DESC;
```

**返回：**

| label | k | cnt |
|---|---|---|
| sample | strategy | 6128 |
| t1 | strategy | 4656 |
| run | strategy | 4656 |
| t2 | strategy | 99 |
| project | omics | 11 |
| study | omics | 11 |
| tool_id | omics | 9 |
| tool_id | input_format | 5 |
| tool_id | output_format | 5 |
| tool_id | description | 4 |
| project | project_name | 2 |
| study | study_description | 2 |
| study | title | 2 |
| tool_id | omics | 2 |
| tool_id | input_format | 2 |
| tool_id | output_format | 2 |
| tool_id | description | 2 |
| project | project_name | 1 |
| study | title | 1 |
| study | study_description | 1 |
| tool_id | description | 1 |
| tool_id | input_format | 1 |
| tool_id | omics | 1 |
| tool_id | output_format | 1 |
| tool_id | input_format | 1 |
| tool_id | description | 1 |
| tool_id | input_format | 1 |
| tool_id | omics | 1 |
| tool_id | output_format | 1 |
| tool_id | omics | 1 |
| tool_id | input_format | 1 |
| tool_id | output_format | 1 |
| tool_id | input_format | 1 |
| tool_id | output_format | 1 |
| tool_id | omics | 1 |
| tool_id | input_format | 1 |
| tool_id | output_format | 1 |
| tool_id | description | 1 |
| tool_id | input_format | 1 |
| tool_id | output_format | 1 |

sample 节点上的 `strategy` 字段可直接标明测序类型（见第 9 条取值分布）。

### 9. 26 个 cohort 列表

**Cypher：**

```cypher
MATCH (c:cohort)
RETURN properties(c) AS props
ORDER BY c.status;
```

| status | description |
|---|---|
| Acral Melanoma | A rare subtype of melanoma occurring on the palms |
| Brain Cancer | Disease cohort category |
| Breast Cancer | Disease cohort category |
| CRC | Disease cohort category |
| Disease cohort category | Disease cohort category |
| Esophageal Cancer | Disease cohort category |
| Gastrointestinal Cancer | Disease cohort category |
| Glioma | Disease cohort category |
| Healthy cohort | Healthy cohort |
| Hematologic Cancer | Disease cohort category |
| Liver Cancer | Disease cohort category |
| Lung Cancer | Disease cohort category |
| Melanoma | Disease cohort category |
| Pan-cancer | Disease cohort category |
| Rare Cancer | Disease cohort category |
| Skin Cancer | Disease cohort category |
| Solid Tumor | Disease cohort category |
| Stomach Cancer | Disease cohort category |
| Urologic Cancer | Disease cohort category |
| acute lymphoblastic leukemia | Disease cohort category |
| disease | Disease cohort category |
| glioma | Disease cohort category |
| health | Healthy cohort |
| liver cancer | Disease cohort category |
| skin cancer | Disease cohort category |
| tumor | Disease cohort category |

返回 26 行。

---

## 二、CSV 侧（实际匹配用的）

### 10. `data/csv/entities/` 下每个文件的列名与行数

**Python：**

```python
from pathlib import Path
import csv
for p in sorted(Path('data/csv/entities').glob('*.csv')):
    with open(p, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, [])
        rows = sum(1 for _ in reader)
    print(p.name, header, rows)
```

| 文件 | 列名 | 行数 |
|---|---|---|
| T1.csv | studyAccession, individualAccession, individualName, sampleAccession, sampleDescription, sampleName, gender, runAccession, dataName, experimentAccession, platform, strategy | 13772 |
| T2.csv | studyAccession, individualAccession, individualName, sampleAccession, sampleDescription, sampleName, gender, runAccession, dataName, experimentAccession, platform, strategy | 99 |
| individual.csv | individualAccession, individualName, gender, cohort, ...（共 44 列，详见原始 JSON `6_individual_keys` 与 `9_csv_entities`） | 3494 |
| project.csv | projectAccession, projectName, title, omics, ... | 11 |
| sample.csv | studyAccession, sampleAccession, sampleName, sampleDescription, individualAccession, individualName, biospecimenAnatomicSite, sampleType, specimenTypes, strategy, tissueType | 6918 |
| study.csv | studyAccession, projectAccession, projectName, studyType, tumorType, title, ... | 14 |
| tool.csv | toolId, catalogId, toolName, toolKind, omics, inputFormat, outputFormat, description, catalogSource | 24 |

完整列名见 `docs/paired_sample_probe_raw.json` 的 `9_csv_entities`。

### 11. sample.csv / individual.csv / T1 / T2 中的样本角色字段

#### 11.1 sample.csv 字段取值分布

| 字段 | 非空数 | 取值分布（前几位） |
|---|---|---|
| tissueType | 6918 | Tumor: 4532, Normal: 2386 |
| sampleType | 6276 | Primary: 5422, Recurrent: 377, Metastatic;Primary: 358, ... |
| specimenTypes | 6918 | Patient Solid Tissue: 3985, Peritumoral: 2048, Blood: 385, Organoid: 255, Bone Marrow: 245 |
| strategy | 6128 | WGS: 3046, WES: 1059, RNA-Seq: 723, WES,RNA-Seq: 698, WGS,RNA-Seq: 310, scRNA-Seq: 292 |

#### 11.2 individual.csv 中无专门样本角色字段

individual.csv 列以个体临床/人口学字段为主，无 `tissue_type`、`sample_type`、`specimen_types` 等 sample-level 角色字段。

#### 11.3 T1.csv / T2.csv 中无样本角色字段

T1.csv / T2.csv 列：`studyAccession, individualAccession, individualName, sampleAccession, sampleDescription, sampleName, gender, runAccession, dataName, experimentAccession, platform, strategy`。

无 `tissueType`、`sampleType`、`specimenTypes`。

### 12. 样本名 / FASTQ 文件名中的角色信号

#### 12.1 样本名 sample_name 后缀分布

**Python（sample.csv）：**

```python
ends_t = sum(1 for r in sample_rows if r['sample_name'] and r['sample_name'].upper().endswith('_T'))
ends_n = sum(1 for r in sample_rows if r['sample_name'] and r['sample_name'].upper().endswith('_N'))
```

| 后缀 | 计数 |
|---|---|
| `_T` / `_t` | 149 |
| `_N` / `_n` | 72 |
| 其他 | 6697 |

#### 12.2 前 50 个样本名（原样）

```text
CGGA_1002
CGGA_1003
CGGA_1010
CGGA_1012
CGGA_1014
CGGA_1017
CGGA_1018
CGGA_103
CGGA_1030
CGGA_1032
CGGA_1033
CGGA_1036
CGGA_1037
CGGA_1041
CGGA_1048
CGGA_1051
CGGA_1055
CGGA_1057
CGGA_1058
CGGA_106
CGGA_1063
CGGA_1065
CGGA_1066
CGGA_1069
CGGA_107
CGGA_1075
CGGA_108
CGGA_1082
CGGA_1086
CGGA_1087
CGGA_109
CGGA_1091
CGGA_1093
CGGA_1095
CGGA_1098
CGGA_110
CGGA_1100
CGGA_1102
CGGA_1103
CGGA_1104
CGGA_1105
CGGA_1106
CGGA_1107
CGGA_1108
CGGA_1109
CGGA_111
CGGA_1110
CGGA_1111
CGGA_1112
CGGA_1113
```

完整 50 条见原始 JSON `12_sample_names`。

#### 12.3 前 50 个 FASTQ 文件名（原样，来自 T1.csv dataName）

```text
HRR024685_f1.fq.gz
HRR024685_r2.fq.gz
HRR024686_f1.fq.gz
HRR024686_r2.fq.gz
HRR024687_f1.fq.gz
HRR024687_r2.fq.gz
HRR024688_f1.fq.gz
HRR024688_r2.fq.gz
HRR024689_f1.fq.gz
HRR024689_r2.fq.gz
HRR024690_f1.fq.gz
HRR024690_r2.fq.gz
HRR024691_f1.fq.gz
HRR024691_r2.fq.gz
HRR024692_f1.fq.gz
HRR024692_r2.fq.gz
HRR024693_f1.fq.gz
HRR024693_r2.fq.gz
HRR024694_f1.fq.gz
HRR024694_r2.fq.gz
HRR024695_f1.fq.gz
HRR024695_r2.fq.gz
HRR024696_f1.fq.gz
HRR024696_r2.fq.gz
HRR024697_f1.fq.gz
HRR024697_r2.fq.gz
HRR024698_f1.fq.gz
HRR024698_r2.fq.gz
HRR024699_f1.fq.gz
HRR024699_r2.fq.gz
HRR024700_f1.fq.gz
HRR024700_r2.fq.gz
HRR024701_f1.fq.gz
HRR024701_r2.fq.gz
HRR024702_f1.fq.gz
HRR024702_r2.fq.gz
HRR024703_f1.fq.gz
HRR024703_r2.fq.gz
HRR024704_f1.fq.gz
HRR024704_r2.fq.gz
HRR024705_f1.fq.gz
HRR024705_r2.fq.gz
HRR024706_f1.fq.gz
HRR024706_r2.fq.gz
HRR024707_f1.fq.gz
HRR024707_r2.fq.gz
HRR024708_f1.fq.gz
HRR024708_r2.fq.gz
HRR024709_f1.fq.gz
HRR024709_r2.fq.gz
HRR024710_f1.fq.gz
HRR024710_r2.fq.gz
```

完整 50 条见原始 JSON `12_fastq_names`。

### 13. `_paired_fastq_groups` 用的 sample_accession / run_accession 来源

`pipeline_router.CsvKGDataMatcher` 中不存在 `_paired_fastq_groups` 方法。存在的方法是 `_guess_read_pair`：

```python
def _guess_read_pair(self, name: str) -> str:
    n = name.lower()
    if re.search(r"(_r?1|_f1|read1)", n):
        return "R1"
    if re.search(r"(_r?2|_r2|read2)", n):
        return "R2"
    return ""
```

实际匹配中 `sample_accession` / `run_accession` 来自 CSV 列：

- `sampleAccession`：`data/csv/entities/T1.csv`、`data/csv/entities/sample.csv`
- `runAccession`：`data/csv/entities/T1.csv`

非空率：T1.csv 13772 行，`sampleAccession` 非空 13772，`runAccession` 非空 13772。

### 14. Neo4j 数据图与 CSV 的关系

| 维度 | Neo4j | CSV |
|---|---|---|
| sample 数量 | 6918 | 6918 |
| individual 数量 | 3494 | 3494 |
| t1 文件节点数 | 15692 | T1.csv 行数 13772 |
| run 数量 | 8354 | — |

sample 与 individual 数量完全对得上；t1 节点数（15692）与 T1.csv 行数（13772）不一致，差 1920。

关系对照：

- `sample.csv` 的 `sampleAccession` 对应 Neo4j `:sample.sample_accession`。
- `individual.csv` 的 `individualAccession` 对应 Neo4j `:individual.individual_accession`。
- `T1.csv` 的 `sampleAccession` / `runAccession` / `dataName` 对应 Neo4j `:t1.sample_accession` / `:t1.run_accession` / `:t1.files`。

CSV 是 Neo4j 的导入源，但 t1 节点在导入后被拆分/扩展（见第 17 条 read_pair 分布：7338 R1 + 7338 R2 + 1016 bam = 15692）。

---

## 三、配对样本存在性

### 15. 同时挂着两种不同角色 sample 的 individual 数量

#### 15.1 以 `tissue_type` 为角色字段

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.tissue_type IS NOT NULL
WITH i, collect(DISTINCT s.tissue_type) AS types
WHERE size(types) > 1
RETURN count(i) AS individual_count;
```

**返回：** `individual_count = 0`

#### 15.2 以 `sample_type` 为角色字段

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.sample_type IS NOT NULL
WITH i, collect(DISTINCT s.sample_type) AS types
WHERE size(types) > 1
RETURN count(i) AS individual_count;
```

**返回：** `individual_count = 0`

#### 15.3 以 `specimen_types` 为角色字段

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.specimen_types IN ['Peritumoral', 'Patient Solid Tissue', 'Blood']
WITH i, collect(DISTINCT s.specimen_types) AS types
WHERE 'Peritumoral' IN types AND ('Patient Solid Tissue' IN types OR 'Blood' IN types)
RETURN count(i) AS individual_count;
```

**返回：** `individual_count = 1957`

#### 15.4 推断：以 `sample_name` 的 `_T` / `_N` 后缀为角色判据

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.sample_name =~ '.*_[Tt]$' OR s.sample_name =~ '.*_[Nn]$'
WITH i,
     collect(DISTINCT CASE WHEN s.sample_name =~ '.*_[Tt]$' THEN s.sample_accession END) AS t_samples,
     collect(DISTINCT CASE WHEN s.sample_name =~ '.*_[Nn]$' THEN s.sample_accession END) AS n_samples
WHERE any(x IN t_samples WHERE x IS NOT NULL) AND any(x IN n_samples WHERE x IS NOT NULL)
RETURN count(i) AS individual_count;
```

**返回：** `individual_count = 40`

**判据说明：** 把 `sample_name` 以 `_T`/`_t` 结尾视为 tumor 角色，以 `_N`/`_n` 结尾视为 normal 角色；要求同一个 `individual` 下同时存在两种后缀。

### 16. 上一步中的 individual，两边都有 FASTQ 文件的数量

#### 16.1 基于 `sample_name` `_T` / `_N` 后缀的 40 个 individual

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.sample_name =~ '.*_[Tt]$' OR s.sample_name =~ '.*_[Nn]$'
WITH i, collect(DISTINCT s) AS samples
WHERE any(s IN samples WHERE s.sample_name =~ '.*_[Tt]$') AND any(s IN samples WHERE s.sample_name =~ '.*_[Nn]$')
WITH i, samples
UNWIND samples AS s
OPTIONAL MATCH (s)<-[:IN_SAMPLE]-(:run)<-[:IN_RUN]-(:t1)
WITH i, s, count(*) AS fcnt
WITH i, collect({name: s.sample_name, acc: s.sample_accession, has_fastq: fcnt>0}) AS sample_flags
WHERE any(x IN sample_flags WHERE x.name =~ '.*_[Tt]$' AND x.has_fastq) AND any(x IN sample_flags WHERE x.name =~ '.*_[Nn]$' AND x.has_fastq)
RETURN count(i) AS individual_count;
```

**返回：** `individual_count = 40`

即 40 个推断配对 individual 中，T 侧与 N 侧均至少有一个 sample 关联到 FASTQ 文件。

#### 16.2 涉及的 study

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.sample_name =~ '.*_[Tt]$' OR s.sample_name =~ '.*_[Nn]$'
WITH i, s
WHERE any(s2 IN [(i)<-[:IN_INDIVIDUAL]-(sx:sample) | sx] WHERE s2.sample_name =~ '.*_[Tt]$')
  AND any(s2 IN [(i)<-[:IN_INDIVIDUAL]-(sx:sample) | sx] WHERE s2.sample_name =~ '.*_[Nn]$')
RETURN s.study_accession AS study_accession, count(DISTINCT i) AS individual_count
ORDER BY individual_count DESC;
```

**返回：**

| study_accession | individual_count |
|---|---|
| HRA006499 | 40 |

全部 40 个推断配对 individual 来自 study `HRA006499`。

#### 16.3 每个 individual 的样本角色组合示例

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.sample_name =~ '.*_[Tt]$' OR s.sample_name =~ '.*_[Nn]$'
WITH i, collect(DISTINCT s) AS samples
WHERE any(s IN samples WHERE s.sample_name =~ '.*_[Tt]$') AND any(s IN samples WHERE s.sample_name =~ '.*_[Nn]$')
RETURN i.individual_accession AS individual_accession,
       [s IN samples | {accession: s.sample_accession, name: s.sample_name, tissue: s.tissue_type, specimen: s.specimen_types, study: s.study_accession}] AS samples
ORDER BY individual_accession
LIMIT 5;
```

**返回（前 5 条）：**

| individual_accession | samples |
|---|---|
| HRI783931 | HRS1029933/P3C2_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029935/P3C4_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029936/P3_N/Tumor/Patient Solid Tissue/HRA006499, HRS1029934/P3C3_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029932/P3C1_T/Tumor/Patient Solid Tissue/HRA006499 |
| HRI783932 | HRS1029942/P4C3_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029940/P4C1_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029941/P4C2_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029943/P4_N/Tumor/Patient Solid Tissue/HRA006499 |
| HRI783934 | HRS1029959/P6C3_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029960/P6C4_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029957/P6C1_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029961/P6_N/Tumor/Patient Solid Tissue/HRA006499, HRS1029958/P6C2_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029951/P6C5_T/Tumor/Patient Solid Tissue/HRA006499 |
| HRI783935 | HRS1029964/P7_N/Tumor/Patient Solid Tissue/HRA006499, HRS1029963/P7C1_T/Tumor/Patient Solid Tissue/HRA006499 |
| HRI783936 | HRS1029967/P8C3_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029968/P8_N/Tumor/Patient Solid Tissue/HRA006499, HRS1029971/P8C2_T/Tumor/Patient Solid Tissue/HRA006499, HRS1029970/P8C1_T/Tumor/Patient Solid Tissue/HRA006499 |

**注意：** 这些 sample 的 `tissue_type` 全部为 `Tumor`，包括 `_N` 后缀样本；`specimen_types` 全部为 `Patient Solid Tissue`。

### 17. 追加确认（因第 10、11 步按角色字段为 0）

#### 17.1 数据集里 FASTQ 文件总数与分属 sample 数

**Cypher：**

```cypher
MATCH (f:t1)
RETURN count(f) AS total_fastq;
```

**返回：** `total_fastq = 15692`

**Cypher：**

```cypher
MATCH (f:t1)-[:IN_RUN]->(r:run)-[:IN_SAMPLE]->(s:sample)
RETURN count(DISTINCT s) AS sample_count;
```

**返回：** `sample_count = 6631`

#### 17.2 FASTQ read_pair 分布

**Cypher：**

```cypher
MATCH (f:t1)
RETURN f.read_pair AS read_pair, count(*) AS cnt
ORDER BY cnt DESC;
```

| read_pair | cnt |
|---|---|
| R1 | 7338 |
| R2 | 7338 |
| bam | 1016 |

#### 17.3 只有下游产物、没有原始 FASTQ 的 sample 数

**Cypher：**

```cypher
MATCH (s:sample)
WHERE NOT (s)<-[:IN_SAMPLE]-(:run)<-[:IN_RUN]-(:t1)
RETURN count(s) AS cnt;
```

**返回：** `cnt = 287`

#### 17.4 MAF 文件

**Cypher：**

```cypher
MATCH (f:t1)
WHERE f.files IS NOT NULL AND toLower(f.files) ENDS WITH '.maf'
RETURN f.files AS name, count(*) AS cnt
ORDER BY cnt DESC
LIMIT 50;
```

**返回 0 行。**

T1 / t1 节点中无 `.maf` 文件。

#### 17.5 strategy 分布

**Cypher（sample）：**

```cypher
MATCH (s:sample)
WHERE s.strategy IS NOT NULL
RETURN s.strategy AS strategy, count(*) AS cnt
ORDER BY cnt DESC;
```

| strategy | cnt |
|---|---|
| WGS | 3046 |
| WES | 1059 |
| RNA-Seq | 723 |
| WES,RNA-Seq | 698 |
| WGS,RNA-Seq | 310 |
| scRNA-Seq | 292 |

**Cypher（t1）：**

```cypher
MATCH (f:t1)
WHERE f.strategy IS NOT NULL
RETURN f.strategy AS strategy, count(*) AS cnt
ORDER BY cnt DESC;
```

| strategy | cnt |
|---|---|
| WES | 2644 |
| RNA-Seq | 1480 |
| WGS | 532 |

#### 17.6 WES 相关样本与配对

**Cypher：**

```cypher
MATCH (s:sample)
WHERE s.strategy = 'WES'
RETURN count(*) AS cnt;
```

**返回：** `cnt = 1059`

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.strategy = 'WES'
WITH i, count(DISTINCT s) AS n
WHERE n > 1
RETURN count(i) AS cnt;
```

**返回：** `cnt = 93`

**Cypher（WES + _T/_N 后缀配对）：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WHERE s.strategy = 'WES' AND (s.sample_name =~ '.*_[Tt]$' OR s.sample_name =~ '.*_[Nn]$')
WITH i, collect(DISTINCT s) AS samples
WHERE any(s IN samples WHERE s.sample_name =~ '.*_[Tt]$') AND any(s IN samples WHERE s.sample_name =~ '.*_[Nn]$')
RETURN count(i) AS cnt;
```

**返回：** `cnt = 40`

---

## 四、目录侧确认

### 18. `wes_somatic_pair` 是否在 Neo4j 目录里

**Cypher：**

```cypher
MATCH (n)
WHERE n.tool_id = 'wes_somatic_pair'
RETURN labels(n) AS labels, properties(n) AS props;
```

**返回 0 行。**

**运行时查询：** `wes_somatic_pair` 未注册为 Neo4j 中的 pipeline-level tool。

`wes_somatic_maf_landscape` 注册存在（见原始 JSON `20_pipeline_reg`），其输入槽 `somatic_maf` 需要 MAF 文件。

### 19. `cellranger_workflow` 是否在 Neo4j 目录里

**Cypher：**

```cypher
MATCH (n)
WHERE n.tool_id = 'cellranger_workflow'
RETURN labels(n) AS labels, properties(n) AS props;
```

**返回 0 行。**

### 20. 两套平行工具图是否存在

**Cypher：**

```cypher
MATCH (t:Tool)
RETURN t.tool_id AS tool_id, labels(t) AS labels
LIMIT 50;
```

**Cypher：**

```cypher
MATCH (t:tool_id)
RETURN t.tool_id AS tool_id, t.catalog_id AS catalog_id, labels(t) AS labels
LIMIT 50;
```

**结果：** 所有工具节点同时带有 `Tool` 和 `tool_id` 两个标签；并非两套平行图。

**计数：**

- `MATCH (t:Tool) RETURN count(t)` → 24
- `MATCH (t:tool_id) RETURN count(t)` → 24

`tool_id` 属性值是字符串名（如 `fastp`），`catalog_id` 才是 `T01` 编号。因此：

- `(:Tool {tool_id: 'T01'})` 返回 0 行。
- `(:tool_id {tool_id: 'fastp', catalog_id: 'T01'})` 返回 1 行。

运行时 catalog 查询使用 `tool_id` 标签（见 `neo4j_observability.py` 中的 `TOOL_CATALOG_QUERY`、`TOOL_SLOT_QUERY` 等）。

### 21. WES target BED / interval list 的资产角色

#### 21.1 注册原子方法的输入 artifact 扫描

**Python：**

```python
from workflow_composer import WorkflowComposer
c = WorkflowComposer()
for m in c.registered_methods.methods.values():
    for inp in m.inputs:
        art = inp.get('artifact', '').lower()
        if any(x in art for x in ['bed', 'interval', 'target', 'capture', 'bait']):
            print(m.tool_id, inp['name'], inp.get('artifact'), inp.get('formats'))
```

**输出：** 空。

#### 21.2 `_role_for_input` 与 `_contract_asset_role` 中的 reference_file 规则

`workflow_composer.py` 中：

```python
EXECUTION_MANAGED_ASSET_ROLES = {"reference_file"}

# _role_for_input
if any(token in name for token in (
    "ref", "reference", "index", "genome", "gtf", "gff", "annotation",
    "interval", "known_site", "pon", "resource",
)):
    return "reference_file"
```

当前没有任何原子工具的输入名包含 `interval` / `bed` / `target`，因此运行时不会生成 `interval` / `bed` 类 `asset_role`。

---

## 附录：原始数据文件

- `docs/paired_sample_probe_raw.json`：第 1–19 条批量查询原始结果。
- `docs/paired_sample_probe_extra.json`：配对样本追加查询原始结果。
- `docs/paired_sample_probe_extra2.json`：目录侧与资产角色追加查询原始结果。


---

## 附录二：样本角色字段语义确认（追加）

### 22. 三字段交叉表

**Cypher：**

```cypher
MATCH (s:sample)
RETURN s.tissue_type    AS tissue_type,
       s.specimen_types AS specimen_types,
       s.sample_type    AS sample_type,
       count(*)         AS n
ORDER BY n DESC;
```

**返回 35 行，总和 6918：**

| tissue_type | specimen_types | sample_type | n |
|---|---|---|---|
| Tumor | Patient Solid Tissue | Primary | 1968 |
| Tumor | Peritumoral | Primary | 1028 |
| Normal | Patient Solid Tissue | Primary | 913 |
| Normal | Peritumoral | Primary | 847 |
| Tumor | Patient Solid Tissue | None | 363 |
| Tumor | Patient Solid Tissue | Recurrent | 271 |
| Tumor | Patient Solid Tissue | Metastatic;Primary | 228 |
| Tumor | Organoid | Primary | 214 |
| Normal | Blood | Primary | 209 |
| Tumor | Bone Marrow | Primary | 145 |
| Normal | Blood | Recurrent | 106 |
| Tumor | Bone Marrow | None | 100 |
| Normal | Peritumoral | None | 84 |
| Normal | Patient Solid Tissue | None | 84 |
| Normal | Patient Solid Tissue | Metastatic;Primary | 62 |
| Tumor | Patient Solid Tissue | Metastatic;Primary;Recurrent | 60 |
| Tumor | Blood | Primary | 57 |
| Tumor | Peritumoral | Metastatic;Primary | 53 |
| Normal | Organoid | Primary | 41 |
| Tumor | Peritumoral | Metastatic;Primary;Recurrent | 13 |
| Normal | Peritumoral | Metastatic;Primary | 13 |
| Tumor | Patient Solid Tissue | Metastatic;Recurrent | 12 |
| Tumor | Patient Solid Tissue | Metastatic | 12 |
| Normal | Blood | None | 10 |
| Normal | Patient Solid Tissue | Metastatic | 6 |
| Normal | Patient Solid Tissue | Metastatic;Primary;Recurrent | 4 |
| Tumor | Peritumoral | Metastatic;Recurrent | 3 |
| Tumor | Peritumoral | Metastatic | 3 |
| Normal | Patient Solid Tissue | Primary;Recurrent | 2 |
| Normal | Peritumoral | Metastatic | 2 |
| Normal | Blood | Metastatic;Primary | 1 |
| Normal | Peritumoral | Primary;Recurrent | 1 |
| Normal | Peritumoral | Metastatic;Primary;Recurrent | 1 |
| Tumor | Blood | Metastatic;Primary | 1 |
| Tumor | Blood | None | 1 |

#### sample_type 独立取值分布

**Cypher：**

```cypher
MATCH (s:sample)
RETURN s.sample_type AS sample_type, count(*) AS n
ORDER BY n DESC;
```

| sample_type | n |
|---|---|
| Primary | 5422 |
| None | 642 |
| Recurrent | 377 |
| Metastatic;Primary | 358 |
| Metastatic;Primary;Recurrent | 78 |
| Metastatic | 23 |
| Metastatic;Recurrent | 15 |
| Primary;Recurrent | 3 |

### 23. 用 HRA006499 的 `_T` / `_N` 命名 ground truth 反查

**Cypher：**

```cypher
MATCH (s:sample)
WHERE s.sample_name =~ '.*_[TN]$'
RETURN CASE WHEN s.sample_name =~ '.*_T$' THEN 'name_T' ELSE 'name_N' END AS name_suffix,
       s.tissue_type    AS tissue_type,
       s.specimen_types AS specimen_types,
       s.sample_type    AS sample_type,
       count(*)         AS n
ORDER BY name_suffix, n DESC;
```

| name_suffix | tissue_type | specimen_types | sample_type | n |
|---|---|---|---|---|
| name_N | Tumor | Patient Solid Tissue | Primary | 51 |
| name_N | Tumor | Peritumoral | Primary | 13 |
| name_N | Normal | Patient Solid Tissue | Primary | 7 |
| name_N | Tumor | Peritumoral | Metastatic;Primary | 1 |
| name_T | Tumor | Patient Solid Tissue | Primary | 109 |
| name_T | Normal | Patient Solid Tissue | Primary | 40 |

`_N` 结尾样本中：
- `tissue_type = Tumor`：64（51+13）
- `tissue_type = Normal`：7

`_T` 结尾样本中：
- `tissue_type = Tumor`：109
- `tissue_type = Normal`：40

### 24. 按 `specimen_types` 判定为配对且两侧都有原始数据的 individual

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WITH i, collect(DISTINCT s.specimen_types) AS types
WHERE size(types) > 1
WITH i, types
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)
OPTIONAL MATCH (f:t1)-[:IN_RUN]->(:run)-[:IN_SAMPLE]->(s2)
WITH i, s2.specimen_types AS st, count(f) AS files
WHERE files > 0
WITH i, collect(DISTINCT st) AS sides_with_data
WHERE size(sides_with_data) > 1
RETURN count(i) AS paired_individuals_with_data_both_sides;
```

**返回：** `paired_individuals_with_data_both_sides = 2045`

#### 按 study 拆分

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WITH i, collect(DISTINCT s.specimen_types) AS types
WHERE size(types) > 1
WITH i, types
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)
OPTIONAL MATCH (f:t1)-[:IN_RUN]->(:run)-[:IN_SAMPLE]->(s2)
WITH i, s2.specimen_types AS st, count(f) AS files, s2.study_accession AS study
WHERE files > 0
WITH i, study, collect(DISTINCT st) AS sides_with_data
WHERE size(sides_with_data) > 1
RETURN study, count(DISTINCT i) AS individual_count
ORDER BY individual_count DESC;
```

| study | individual_count |
|---|---|
| HRA000873 | 1015 |
| HRA000021 | 508 |
| HRA001272 | 206 |
| HRA003107 | 155 |
| HRA007169 | 76 |
| HRA006499 | 71 |
| HRA001748 | 14 |

#### 文件格式分布

**Cypher：**

```cypher
MATCH (s:sample)-[:IN_INDIVIDUAL]->(i:individual)
WITH i, collect(DISTINCT s.specimen_types) AS types
WHERE size(types) > 1
WITH i, types
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)
OPTIONAL MATCH (f:t1)-[:IN_RUN]->(:run)-[:IN_SAMPLE]->(s2)
WITH i, s2.specimen_types AS st, count(f) AS files
WHERE files > 0
WITH i, collect(DISTINCT st) AS sides_with_data
WHERE size(sides_with_data) > 1
WITH i
MATCH (i)<-[:IN_INDIVIDUAL]-(s3:sample)<-[:IN_SAMPLE]-(:run)<-[:IN_RUN]-(f3:t1)
RETURN f3.format AS format, count(*) AS cnt
ORDER BY cnt DESC;
```

| format | cnt |
|---|---|
| fq.gz | 9230 |
| bam | 1016 |

### 25. `specimen_types` 完整取值分布

**Cypher：**

```cypher
MATCH (s:sample)
RETURN s.specimen_types AS specimen_types, count(*) AS n
ORDER BY n DESC;
```

| specimen_types | n |
|---|---|
| Patient Solid Tissue | 3985 |
| Peritumoral | 2048 |
| Blood | 385 |
| Organoid | 255 |
| Bone Marrow | 245 |

合计 6918，无其他取值。

### 26. 回归验证："我有 TPM 矩阵想做无监督聚类"

**调用：**

```python
from workflow_composer import WorkflowComposer
result = WorkflowComposer().plan("我有TPM矩阵想做无监督聚类")
```

**关键字段：**

| 字段 | 值 |
|---|---|
| `selection_status` | `ready` |
| `orchestration_status` | `ready` |
| `agent_input.feasibility.status` | `ready` |
| `agent_input.feasibility.missing_assets` | `[]` |
| `agent_input.feasibility.data_ready` | `true` |
| `agent_input.feasibility.message` | 流程所需的用户样本数据已匹配。 |
| `agent_input.assets` | 1 条，role=`count_matrix`，path=`/hpcdisk1/cbb_group/data/analysis/HRA000074/HRA000074-Genes-counts-1.0.tsv` |
| `pipeline_assessments[0].input_match` | `mismatch` |
| `pipeline_assessments[0].note` | 该流程需要 raw count 矩阵作为输入，用户提供的是 TPM 矩阵，无法直接使用 |

**说明：** `pipeline_assessment` 已正确标 `input_match=mismatch`，但 `agent_input.feasibility` 仍报 `ready`，因为资产匹配选中了 study `HRA000074` 的 `count_matrix` 文件，未按用户声明的 TPM 类型拦截。`_role_satisfies` 本身对 `expression_count` / `expression_abundance` 返回 False，但当前问题点是资产选择阶段未使用 `intent.quant_hint` 过滤，导致 count 文件被当作可行资产。

完整输出 JSON 见 `tpm_cluster_regression_check.json`。

## 附录三：配对组合拆分与修复验证（追加）

> 本节数据来自 Neo4j 运行时查询（密码从 `.env.local` 加载），只列原始数字与字段。

### 三.1 按 `specimen_types` 拆分配对个体

**Cypher：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WITH i, collect(DISTINCT s.specimen_types) AS combo
WHERE size(combo) > 1
RETURN i.individual_id AS individual_id, combo
```

在 Python 中对 `combo` 排序后聚合，结果如下（仅列出个体数 > 0 的组合）：

| 组合 | 个体数 |
|---|---|
| Patient Solid Tissue + Peritumoral | 1939 |
| Organoid + Patient Solid Tissue | 56 |
| Blood + Patient Solid Tissue | 25 |
| Blood + Patient Solid Tissue + Peritumoral | 10 |
| Blood + Organoid + Patient Solid Tissue | 7 |
| Blood + Organoid + Patient Solid Tissue + Peritumoral | 5 |
| Organoid + Patient Solid Tissue + Peritumoral | 3 |

合计 2045 个 multi-specimen individual，与 §22 一致。

### 三.2 各组合的 study / 文件格式

#### Patient Solid Tissue + Peritumoral

**Cypher：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.specimen_types IN ['Patient Solid Tissue', 'Peritumoral']
WITH i, collect(DISTINCT s.specimen_types) AS types_seen
WHERE size(types_seen) > 1
WITH i
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)<-[:IN_SAMPLE]-(:run)<-[:IN_RUN]-(f:t1)
RETURN s2.study_accession AS study, f.format AS format, count(*) AS cnt
ORDER BY study, format
```

| study | format | cnt |
|---|---|---|
| HRA000021 | bam | 1016 |
| HRA000873 | fq.gz | 4060 |
| HRA001272 | fq.gz | 2360 |
| HRA001748 | fq.gz | 80 |
| HRA003107 | fq.gz | 1152 |
| HRA006499 | fq.gz | 264 |
| HRA007169 | fq.gz | 206 |

#### Organoid + Patient Solid Tissue

| study | format | cnt |
|---|---|---|
| HRA006499 | fq.gz | 1270 |

#### Blood + Patient Solid Tissue

| study | format | cnt |
|---|---|---|
| HRA001748 | fq.gz | 64 |
| HRA006499 | fq.gz | 282 |
| HRA007169 | fq.gz | 102 |

### 三.3 测序策略分布（`sample.strategy`）

**Cypher：**

```cypher
MATCH (s:sample)
WHERE s.study_accession IN ['HRA000873','HRA000021','HRA006499','HRA000122','HRA000071','HRA007169','HRA001748','HRA001749','HRA001272','HRA003107']
RETURN s.study_accession AS study, s.strategy AS strategy, count(*) AS n
ORDER BY study, n DESC
```

| study | strategy | n |
|---|---|---|
| HRA000021 | WGS | 1016 |
| HRA000071 | WES | 286 |
| HRA000071 | null | 286 |
| HRA000122 | WES | 287 |
| HRA000873 | WGS | 2030 |
| HRA001272 | WES,RNA-Seq | 698 |
| HRA001748 | null | 111 |
| HRA001748 | scRNA-Seq | 49 |
| HRA001749 | null | 178 |
| HRA003107 | WGS,RNA-Seq | 310 |
| HRA006499 | WES | 482 |
| HRA007169 | null | 138 |
| HRA007169 | RNA-Seq | 30 |

### 三.4 HRA000873 / HRA000021 细节

**HRA000873 每个个体的 sample 数量分布：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA000873'
WITH i, count(DISTINCT s) AS sample_count
RETURN sample_count, count(i) AS individual_count ORDER BY sample_count
```

| sample_count | individual_count |
|---|---|
| 2 | 1015 |

**HRA000021 每个个体的 sample 数量分布：**

| sample_count | individual_count |
|---|---|
| 2 | 508 |

### 三.5 HRA006499 `_T` / `_N` 命名个体

**Cypher：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA006499' AND s.sample_name =~ '.*_[TN]$'
WITH i, collect(DISTINCT s.specimen_types) AS types
RETURN count(DISTINCT i) AS tn_individual_count, types
```

**返回：** `tn_individual_count = 78`，`types = ["Patient Solid Tissue"]`。

这些 `_T` / `_N` 后缀样本的 `specimen_types` 全部是 `Patient Solid Tissue`，没有标成 `Peritumoral`。

**文件格式：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA006499' AND s.sample_name =~ '.*_[TN]$'
WITH i
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)<-[:IN_SAMPLE]-(:run)<-[:IN_RUN]-(f:t1)
RETURN f.format AS format, count(*) AS cnt ORDER BY cnt DESC
```

| format | cnt |
|---|---|
| fq.gz | 4422 |

### 三.6 Organoid / Bone Marrow / Blood 归属

#### Organoid

| study | n |
|---|---|
| HRA006499 | 255 |

Organoid 共现类型（仅统计有 individual 链接的样本）：

| co_type | n |
|---|---|
| Organoid | 913 |
| Patient Solid Tissue | 638 |
| Blood | 38 |
| Peritumoral | 35 |

#### Bone Marrow

| study | n |
|---|---|
| HRA000122 | 245 |

**注意：** 245 个 Bone Marrow 样本没有任何 `(sample)-[:IN_INDIVIDUAL]->(individual)` 关系，因此不存在共现类型统计。

#### Blood

| study | n |
|---|---|
| HRA000071 | 286 |
| HRA000122 | 42 |
| HRA007169 | 25 |
| HRA006499 | 12 |
| HRA001748 | 10 |
| HRA001749 | 10 |

Blood 共现类型：

| co_type | n |
|---|---|
| Blood | 333 |
| Patient Solid Tissue | 70 |
| Organoid | 38 |
| Peritumoral | 15 |

### 三.7 修复后回归验证："我有 TPM 矩阵想做无监督聚类"

**修改位置：** `bio-pipeline-kg-matcher/workflow_composer.py` `_apply_agent_contract`。

**修改内容：** 扫描 `plan["coverage_assessment"]["pipeline_assessments"]`，任一 `input_match == "mismatch"` 时，将对应说明前置进 `missing_assets`，强制 `orchestration_status = "missing_data"`、`selection_status = "missing_assets"`，并在 `feasibility.message` 中说明数据类型不匹配。

**修复后调用：**

```python
from workflow_composer import WorkflowComposer
result = WorkflowComposer().plan("我有 TPM 矩阵想做无监督聚类")
```

**关键字段：**

| 字段 | 值 |
|---|---|
| `workflow_mode` | `standard` |
| `selection_status` | `missing_assets` |
| `orchestration_status` | `missing_data` |
| `agent_input.feasibility.status` | `missing_assets` |
| `agent_input.feasibility.data_ready` | `false` |
| `agent_input.feasibility.message` | 流程选择已确定，但输入数据类型不匹配: 该流程需要 expression_count_matrix（例如 featureCounts 输出），用户提供的是 TPM 矩阵。若用户能提供 count 矩阵或进行 TPM 到 count 的转换，则可直接使用。 |
| `agent_input.feasibility.missing_assets[0].step_id` | `rnaseq_unsupervised_cluster` |
| `agent_input.feasibility.missing_assets[0].input` | `data_type_match` |
| `agent_input.feasibility.missing_assets[0].role` | `user_input` |
| `agent_input.feasibility.missing_assets[0].reason` | 该流程需要 expression_count_matrix（例如 featureCounts 输出），用户提供的是 TPM 矩阵。若用户能提供 count 矩阵或进行 TPM 到 count 的转换，则可直接使用。 |
| `pipeline_assessments[0].input_match` | `mismatch` |

### 三.8 全量测试与六条查询验证

**全量 unittest：**

```bash
.venv/bin/python -m unittest discover -s tests
```

**结果：** Ran 63 tests in 23.268s — OK (skipped=3)

**六条查询验证结果摘要：**

| 查询 | workflow_mode | selection_status | orchestration_status | 备注 |
|---|---|---|---|---|
| 配对 WES FASTQ 体细胞变异检测 | custom | no_match | no_match | `execution_status = blocked_by_incomplete_method_decomposition`，但 `decomposition_gaps` 仍为空 |
| RNA-seq 上游 trim_galore 换 fastp | custom | no_match | no_match | 验证错误：fastqc 未与前序输出衔接 |
| 双端 FASTQ RNA-seq 上游 | standard | ready | ready | 未受修复影响 |
| TPM 矩阵无监督聚类 | standard | **missing_assets** | **missing_data** | 修复生效 |
| GO + KEGG 富集 | standard | ready | ready | 未受修复影响 |
| 单样本 WES FASTQ 变异检测 | custom | draft | draft | 未命中 standard pipeline，进入自助餐草案 |

### 三.9 代码 diff

**文件：** `bio-pipeline-kg-matcher/workflow_composer.py`
**函数：** `_apply_agent_contract`（约 1694 行起）

修改要点（行号基于修改后文件）：

- 1707-1726：生成工具链后，扫描 `coverage_assessment.pipeline_assessments`，将 `input_match == "mismatch"` 的条目以 `{step_id, input: "data_type_match", role: "user_input", reason}` 形式前置到 `missing_assets`。
- 1727-1736：状态判定增加 `mismatch_assessments` 优先分支，强制进入 `missing_data`。
- 1747-1755：构造 `feasibility_message`，mismatch 时用 assessment.note 说明数据类型不匹配。
- 1763-1768：contract 中 `feasibility.message` 使用上述 `feasibility_message`。

完整 diff 见本次会话输出或 `git diff`（当前仓库无提交历史，diff 需用 `diff -u` 手动生成）。


---

## 附录四：配对组合 × 测序策略 × FASTQ 侧覆盖（2026-07-23 追加）

> 严格只读。Neo4j 查询密码从 `.env.local` 加载。本节只列原始数字与实际查询，不含结论；结论见文末「判断」一节。
> 与附录三口径的差异：本节额外拆出「测序策略」「两侧都有 FASTQ 的个体数」（区别于附录三的「两侧都有文件」），并补 CSV↔Neo4j 同源核对。

### 四.1 specimen_types 组合拆分（Neo4j，全部组合）

**查询（拉全量后在 Python 侧按个体聚合排序）：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WITH i, collect(DISTINCT s.specimen_types) AS combo
WHERE size([x IN combo WHERE x IS NOT NULL]) > 1
MATCH (i)<-[:IN_INDIVIDUAL]-(s2:sample)
OPTIONAL MATCH (f:t1)-[:IN_RUN]->(:run)-[:IN_SAMPLE]->(s2)
WITH i, s2,
     count(CASE WHEN f.read_pair IN ['R1','R2'] THEN 1 END) AS fastq_files,
     count(CASE WHEN f.read_pair = 'bam' THEN 1 END) AS bam_files
RETURN i.individual_accession AS ind, s2.study_accession AS study,
       s2.specimen_types AS specimen, s2.strategy AS strategy, fastq_files, bam_files
```

| 组合 | 个体数 |
|---|---|
| Patient Solid Tissue + Peritumoral | 1939 |
| Organoid + Patient Solid Tissue | 56 |
| Blood + Patient Solid Tissue | 25 |
| Blood + Patient Solid Tissue + Peritumoral | 10 |
| Blood + Organoid + Patient Solid Tissue | 7 |
| Blood + Organoid + Patient Solid Tissue + Peritumoral | 5 |
| Organoid + Patient Solid Tissue + Peritumoral | 3 |

合计 2045，与附录三、§24 一致。

### 四.2 每组合的 study / 测序策略 / 两侧覆盖

「策略」列为**样本级**计数（组合内所有样本按 `sample.strategy` 聚合）；「两侧都有 FASTQ 的个体数」= 该个体的两个及以上 specimen 侧各自都至少挂 1 个 `read_pair ∈ {R1,R2}` 的 t1 文件；「两侧都有文件」= 两侧各自至少挂 1 个 t1 文件（含 bam）。

| 组合 | 个体数 | study（个体数） | 策略（样本级） | 两侧都有 FASTQ | 两侧都有文件 |
|---|---|---|---|---|---|
| Patient Solid Tissue + Peritumoral | 1939 | HRA000873:1015 / HRA000021:508 / HRA001272:206 / HRA003107:155 / HRA007169:51 / HRA001748:4 | WGS:3046 / WES,RNA-Seq:698 / WGS,RNA-Seq:310 / RNA-Seq:8 / scRNA-Seq:4 | 1431 | 1939 |
| Organoid + Patient Solid Tissue | 56 | HRA006499:56 | WES:281 | 56 | 56 |
| Blood + Patient Solid Tissue | 25 | HRA007169:25 | RNA-Seq:22 | 25 | 25 |
| Blood + Patient Solid Tissue + Peritumoral | 10 | HRA001748:10 | （strategy 全为 null） | 10 | 10 |
| Blood + Organoid + Patient Solid Tissue | 7 | HRA006499:7 | WES:44 | 7 | 7 |
| Blood + Organoid + Patient Solid Tissue + Peritumoral | 5 | HRA006499:5 | WES:43 | 5 | 5 |
| Organoid + Patient Solid Tissue + Peritumoral | 3 | HRA006499:3 | WES:35 | 3 | 3 |

**个体级策略分布**（该个体是否含某策略的样本，按组合）：

| 组合 | 个体级策略 |
|---|---|
| Patient Solid Tissue + Peritumoral | WGS:1523 / WES,RNA-Seq:206 / WGS,RNA-Seq:155 / RNA-Seq:4 / scRNA-Seq:2 |
| Organoid + Patient Solid Tissue | WES:56 |
| Blood + Patient Solid Tissue | RNA-Seq:11 |
| Blood + Organoid + Patient Solid Tissue | WES:7 |
| Blood + Organoid + Patient Solid Tissue + Peritumoral | WES:5 |
| Organoid + Patient Solid Tissue + Peritumoral | WES:3 |

（Patient Solid Tissue + Peritumoral 组合个体级策略求和 1890 < 1939，差值 49 个个体的样本 `strategy` 为 null；Blood + Patient Solid Tissue + Peritumoral 组合 10 个个体 strategy 全 null，故无个体级策略行。）

### 四.3 HRA000873 / HRA000021 展开

**HRA000873：**

- sample 数分布：`sample_count=2 → 1015 个体`（每个体恰好 2 个 sample）
- specimen_types：`Patient Solid Tissue:1015`、`Peritumoral:1015`
- strategy：`WGS:2030`（全 WGS）
- 每个体典型规模：`samples=2, runs=2, files=4 → 1015 个体`（fq.gz 双端，每 sample 1 run 2 文件）

**HRA000021：**

- sample 数分布：`sample_count=2 → 508 个体`
- specimen_types：`Peritumoral:508`、`Patient Solid Tissue:508`
- strategy：`WGS:1016`（全 WGS）
- 每个体典型规模：`samples=2, runs=2, files=2 → 508 个体`（bam，每 sample 1 run 1 bam）

**HRA000873 前 10 个体 sample 列表（原样，`{acc/name/tissue/specimen/strategy/sample_type}`）：**

```
HRI104775  HRS169394/CRC1_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169395/CRC1_N1/Tumor/Peritumoral/WGS/Primary
HRI104776  HRS169396/CRC2_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169397/CRC2_N1/Tumor/Peritumoral/WGS/Primary
HRI104777  HRS169398/CRC3_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169399/CRC3_N1/Tumor/Peritumoral/WGS/Primary
HRI104778  HRS169400/CRC4_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169401/CRC4_N1/Tumor/Peritumoral/WGS/Primary
HRI104779  HRS169402/CRC5_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169403/CRC5_N1/Tumor/Peritumoral/WGS/Primary
HRI104780  HRS169404/CRC6_T2/Tumor/Patient Solid Tissue/WGS/Primary   HRS169405/CRC6_N3/Tumor/Peritumoral/WGS/Primary
HRI104781  HRS169406/CRC7_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169407/CRC7_N1/Tumor/Peritumoral/WGS/Primary
HRI104782  HRS169408/CRC8_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169409/CRC8_N1/Tumor/Peritumoral/WGS/Primary
HRI104783  HRS169410/CRC9_T1/Tumor/Patient Solid Tissue/WGS/Primary   HRS169411/CRC9_N1/Tumor/Peritumoral/WGS/Primary
HRI104784  HRS169412/CRC10_T1/Tumor/Patient Solid Tissue/WGS/Primary  HRS169413/CRC10_N1/Tumor/Peritumoral/WGS/Primary
```

**HRA000021 前 10 个体 sample 列表（原样）：**

```
HRI035286  HRS039793/BDESCC0004T/Normal/Patient Solid Tissue/WGS/Primary  HRS039792/BDESCC0004N/Normal/Peritumoral/WGS/Primary
HRI035287  HRS039795/BDESCC0006T/Normal/Patient Solid Tissue/WGS/Primary  HRS039794/BDESCC0006N/Normal/Peritumoral/WGS/Primary
HRI035288  HRS039797/BDESCC0007T/Normal/Patient Solid Tissue/WGS/Primary  HRS039796/BDESCC0007N/Normal/Peritumoral/WGS/Primary
HRI035289  HRS039799/BDESCC0008T/Normal/Patient Solid Tissue/WGS/Primary  HRS039798/BDESCC0008N/Normal/Peritumoral/WGS/Primary
HRI035290  HRS039801/BDESCC0009T/Normal/Patient Solid Tissue/WGS/Primary  HRS039800/BDESCC0009N/Normal/Peritumoral/WGS/Primary
HRI035291  HRS039803/BDESCC0010T/Normal/Patient Solid Tissue/WGS/Primary  HRS039802/BDESCC0010N/Normal/Peritumoral/WGS/Primary
HRI035292  HRS039805/BDESCC0011T/Normal/Patient Solid Tissue/WGS/Primary  HRS039804/BDESCC0011N/Normal/Peritumoral/WGS/Primary
HRI035293  HRS039807/BDESCC0013T/Normal/Patient Solid Tissue/WGS/Primary  HRS039806/BDESCC0013N/Normal/Peritumoral/WGS/Primary
HRI035294  HRS039809/BDESCC0014T/Normal/Patient Solid Tissue/WGS/Primary  HRS039808/BDESCC0014N/Normal/Peritumoral/WGS/Primary
HRI035295  HRS039811/BDESCC0015T/Normal/Patient Solid Tissue/WGS/Primary  HRS039810/BDESCC0015N/Normal/Peritumoral/WGS/Primary
```

**注意（原样记录，不下结论）：** HRA000873 两侧 `tissue_type` 全为 `Tumor`（含 `_N1` 侧）；HRA000021 两侧 `tissue_type` 全为 `Normal`（含 `T` 侧）。命名后缀（T/N）与 specimen（Patient Solid Tissue / Peritumoral）在两个 study 内部一致，`tissue_type` 与命名相反或恒定。

### 四.4 HRA006499 的 `_T`/`_N` 命名个体校准

**查询：**

```cypher
MATCH (i:individual)<-[:IN_INDIVIDUAL]-(s:sample)
WHERE s.study_accession = 'HRA006499' AND (s.sample_name =~ '.*_[Tt]$' OR s.sample_name =~ '.*_[Nn]$')
WITH i, collect(DISTINCT s) AS samples
WHERE any(x IN samples WHERE x.sample_name =~ '.*_[Tt]$') AND any(x IN samples WHERE x.sample_name =~ '.*_[Nn]$')
UNWIND samples AS s
RETURN s.specimen_types AS specimen, s.strategy AS strategy, s.tissue_type AS tissue, count(*) AS n
ORDER BY n DESC
```

| specimen | strategy | tissue_type | n |
|---|---|---|---|
| Patient Solid Tissue | WES | Tumor | 110 |
| Patient Solid Tissue | WES | Normal | 33 |

- 配对个体数（同一 individual 同时有 `_T` 与 `_N` 命名 sample）：**40**
- specimen 全部是 `Patient Solid Tissue`（无 Peritumoral），strategy 全部 `WES`
- `tissue_type` 在这批命名可信样本上仍不一致（143 个 T/N 命名样本里 110 标 Tumor、33 标 Normal，与后缀不逐一对应）

### 四.5 Organoid / Bone Marrow / Blood 归属与共现

| specimen | study（样本数） | 同个体共现 specimen（样本数） |
|---|---|---|
| Organoid | HRA006499:255 | Organoid:913 / Patient Solid Tissue:638 / Blood:38 / Peritumoral:35 |
| Bone Marrow | HRA000122:245 | **无**（245 个 Bone Marrow 样本在 Neo4j 中无 `IN_INDIVIDUAL` 关系，见四.6） |
| Blood | HRA000071:286 / HRA000122:42 / HRA007169:25 / HRA006499:12 / HRA001748:10 / HRA001749:10 | Blood:333 / Patient Solid Tissue:70 / Organoid:38 / Peritumoral:15 |

### 四.6 CSV ↔ Neo4j 同源核对

**Neo4j 计数：** `samples=6918, individuals=3494, t1=15692`。

**CSV（`data/csv/entities/`，列名为 snake_case，非附录三所记的 camelCase）：**

| 项 | 数值 |
|---|---|
| sample.csv 行数 | 6918 |
| sample.csv 中 distinct `individual_accession` | **4041** |
| individual.csv 行数 | 3494 |
| sample.csv 中 individual 不在 individual.csv 的行数 | **828** |

这 828 个「孤儿」sample 行的 study/specimen 分布：

- study：HRA000122:287 / HRA000071:286 / HRA001749:178 / HRA007167:77
- specimen：Patient Solid Tissue:447 / Bone Marrow:245 / Peritumoral:84 / Blood:52

**关键核对：** 把 CSV 的多 specimen 个体计算**限制在 individual.csv 存在的个体**（模拟 Neo4j `IN_INDIVIDUAL` 建边逻辑）后：

| 口径 | 多 specimen 个体数 |
|---|---|
| CSV 全量（按 sample.csv 的 individual_accession） | 2171 |
| CSV 仅计 individual.csv 内个体 | **2045** |
| Neo4j `IN_INDIVIDUAL` | **2045** |

限定后 CSV 精确复现 Neo4j 的 2045 与逐组合数字（Patient Solid Tissue + Peritumoral 1939 等）。CSV 全量比 Neo4j 多出的 126 个多 specimen 个体，主要是 `Blood + Bone Marrow`（42）等——它们的个体不在 individual.csv，故 Neo4j 未建 `IN_INDIVIDUAL` 边、也不出现在 §24 / 四.1 的配对统计里。

### 四.7 六条查询重跑（本轮修复后）

| 查询 | workflow_mode | selection_status | orchestration_status |
|---|---|---|---|
| 配对 WES FASTQ 体细胞变异检测 | custom | no_match | no_match |
| RNA-seq 上游 trim_galore 换 fastp | custom | no_match | no_match |
| 双端 FASTQ RNA-seq 上游 | standard | ready | ready |
| **TPM 矩阵无监督聚类** | standard | **missing_assets** | **missing_data** |
| GO + KEGG 富集 | standard | ready | ready |
| 单样本 WES FASTQ 变异检测 | custom | draft | draft |

全量 unittest：`Ran 63 tests — OK (skipped=3)`。TPM 完整输出见 `tpm_cluster_regression_check.json`。

---

## 附录五：任务 B 修复 diff 与代码位置（2026-07-23）

**文件：** `workflow_composer.py`，函数 `_apply_agent_contract`（1694 起）+ 新增私有方法 `_data_type_mismatches`。

**这次的实际起点与附录三.7-三.9 的差异：** 附录三.7-三.9 描述的 mismatch→missing_data 修复**当前不在代码里**（`_apply_agent_contract` 无相关扫描，实测 TPM 聚类返回 `ready/ready`，见 §26 状态）。本轮按同一意图重新实现。

**改动点（行号基于修改后文件）：**

- `1710-1717`：`_standard_tool_chain` 生成工具链后，standard 模式下调 `_data_type_mismatches(plan, tool_chain)`，扫描 `plan["coverage_assessment"]["pipeline_assessments"]`，对**被选中 pipeline**（`tool_id` 出现在 tool_chain 中）且 `input_match == "mismatch"` 的条目，生成 `{step_id, input:"data_type_match", role:"user_input", reason:note}`。
- `1719-1729`：状态判定新增 `elif type_mismatches:` 分支，强制 `orchestration_status = "missing_data"`（`selection_status` 随之为 `missing_assets`）。放在 `missing` 之后、`custom`/`ready` 之前，故仅在流程选对（tool_chain 有效、plan_validation.ok）且不缺其他资产时，把「类型不匹配」单独提升为缺数据。
- `1739-1748`：`combined_missing = type_mismatches + missing`；`feasibility_message` 在 type_mismatches 非空时用 assessment.note 说明数据类型不匹配。
- `1756-1760`：`feasibility` 的 `status/missing_assets/data_ready/message` 全部改用 `combined_missing` 与 `feasibility_message`。
- 新增 `_data_type_mismatches`（约 `1808` 起）。

**未改：** 未恢复 `_standard_has_coverage_gap` 里被删的 `input_match=="mismatch"→custom` 降级分支；pipeline 选择、mode、资产匹配逻辑均未动。TPM 聚类仍是 `standard` + `rnaseq_unsupervised_cluster`，只是状态从 `ready` 变 `missing_data`。

**手工 diff（关键段）：**

```diff
             tool_chain, missing, _parameters = self._custom_tool_chain(plan, assets)
+        type_mismatches: List[Dict[str, Any]] = []
+        if plan["mode"] == "standard":
+            type_mismatches = self._data_type_mismatches(plan, tool_chain)
         plan_validation = plan.get("validation") or {}
         if not tool_chain or not plan_validation.get("ok"):
             orchestration_status = "no_match"
         elif missing:
             orchestration_status = "missing_data"
+        elif type_mismatches:
+            orchestration_status = "missing_data"
         elif plan["mode"] == "custom":
             orchestration_status = "draft"
         else:
             orchestration_status = "ready"
```

---

## 附录六：任务 A/B 的判断（这一节是结论，与上面的原始数字分开）

### 六.1 对第三节推理的审视

用户第三节的核心论断是「2045 是上界，真实可用 somatic 配对在 40–2045 之间，且更要紧的是这些配对是 DNA 还是 RNA」。数据支持其方向，但几处需要修正：

1. **「40 是下界」不成立——40 是另一个数据集的巧合，不是同一集合的保守估计。** 那 40 个来自 HRA006499、靠 `_T/_N` 命名判定、全 WES、specimen 全是 `Patient Solid Tissue`（四.4）；而 2045 的主体（HRA000873+HRA000021 共 1523 个体）靠 `Patient Solid Tissue + Peritumoral` 判定、全 WGS。两者是**不同 study、不同判据、几乎不重叠**的集合（HRA006499 在 2045 里只贡献 71，且是 Organoid/Blood 组合那几行）。把 40 当作 2045 的下界是把两把尺子叠在一起。真正的「WES/WGS somatic 可用配对」应按测序策略重新框定，而不是 40–2045 区间。

2. **「DNA 还是 RNA」这个变量数据已经能回答，且答案偏向 DNA。** 2045 里最大两块 HRA000873(1015)、HRA000021(508) 全是 WGS（四.3），主组合 Patient Solid Tissue + Peritumoral 的个体级策略里 WGS 系（WGS + WGS,RNA-Seq）占 1678/1939。纯 RNA-Seq 的配对个体极少（主组合里个体级只有 4）。唯一明确是 RNA-seq 的配对是 `Blood + Patient Solid Tissue`（HRA007169，25 个体，RNA-Seq）——但那反而是最不像 somatic 对照的组合（血 vs 实体瘤做 RNA 差异表达，不是 germline 对照）。所以「大头是 RNA 配对、跟 somatic 无关」这个担心，数据不支持；大头恰恰是 DNA。

3. **specimen_types 混维度的判断正确，但「Solid + Blood = 标准 germline 对照」在本数据里几乎不存在。** `Blood + Patient Solid Tissue` 只有 25 个体且是 RNA-Seq（HRA007169），不是 WES/WGS 的胚系对照。真正的 germline 对照式组合（Solid + Blood + WES/WGS）在 2045 里查不到独立成规模的一块。本数据的「肿瘤 vs 正常」几乎全部是 **Solid Tissue vs Peritumoral（癌旁）**，不是 vs 血。

4. **`tissue_type` 不仅「不可用」，而且是 study 级恒定的坏字段。** 四.3 显示 HRA000873 整个 study 两侧全标 Tumor、HRA000021 整个 study 两侧全标 Normal。这不是随机填错，是导入时按 study 灌了一个常量。所以任何依赖 `tissue_type` 区分肿瘤/正常的逻辑，在这两个最大 study 上都会整体失效——比命名后缀的噪声严重得多。配对角色应以 **specimen_types（Peritumoral=正常侧）+ 命名后缀** 为准，`tissue_type` 直接弃用。

**结论：** 可用于 somatic 配对（肿瘤 + 匹配正常、DNA 测序、两侧都有原始 reads）的规模，比「40」大得多、但比「2045」小——主要落在 HRA000873(WGS,fq.gz,1015) 与 HRA006499 的 WES 那批；HRA000021 虽 508 对但只有 bam（无 fq.gz，四.2 两侧都有 FASTQ 计入的是 1431 而非 1939，差的 508 正是它）。这些数字受当前 catalog 硬限制（gatk 单 BAM 槽）约束，能识别但仍组不出双链——与任务一的 honest block 结论一致。

### 六.2 CSV 与 Neo4j 是否同源

**同源，但个体分辨率不同。** sample 数两边都是 6918、逐组合数字在「限定 individual.csv 内个体」后精确对上 2045（四.6）。差异只在个体维度：sample.csv 引用了 4041 个 individual_accession，其中 828 行（612 个个体）不在 individual.csv，Neo4j 因此没给它们建 `IN_INDIVIDUAL` 边。后果是 **Bone Marrow（HRA000122，245 样本）在 Neo4j 里完全没有配对信号**，`Blood + Bone Marrow`（CSV 里 42 对）在图查询中不可见。对本任务无影响（这些不是 somatic 配对目标），但如果日后要按个体聚合 HRA000122/HRA000071/HRA001749，Neo4j 会漏掉它们——这是 import 的已知缺口，不是查询写错。

对实际匹配的影响：`CsvKGDataMatcher` 读 CSV，不读 Neo4j 的 `IN_INDIVIDUAL` 边。它按文件名/format/strategy 打分选文件，本来就不消费「个体级配对结构」。所以 Neo4j 里这套配对拓扑（无论 2045 还是 2171）在当前匹配路径上都用不上——配对编排的瓶颈在 catalog（gatk 单槽）和 prompt，不在数据图缺不缺边。

### 六.3 `_select_asset` 是否读 quant_hint（只报告，未改）

**不读。** `_select_asset`（`workflow_composer.py:2078` 附近，原任务书说的 :1887 已随文件增长后移）签名是 `_select_asset(self, role, assets, usage)`，只接收一个字符串 `role` 和资产列表，**完全不接触 `intent`**，因此拿不到 `intent.quant_hint`。它的选择逻辑纯按 `asset.role == role` 精确匹配，外加三条兜底：`fastq_file` 回退 r1/r2；`count_matrix`/`expression_matrix` 回退通用 `expression_file`；`data_file` 回退任意资产（`2081-2098`）。role 由 `_role_for_input(spec["name"])`（`2015`）从**工具注册的输入名**推断，也与用户意图无关。

**这意味着什么：** 上游 `pipeline_router` 的 `CsvKGDataMatcher` 在打分阶段用了 `quant_hint`（`pipeline_router.py:636-640`，会给 diff_expr 的 TPM/FPKM、聚类的 counts 加权），但那只影响**候选文件排序**，不构成硬过滤。一旦候选里存在某个 study 的 count 文件（如 HRA000074 的 `*-Genes-counts-1.0.tsv`），即便用户明说手里是 TPM，`_select_asset` 仍会因 `role==count_matrix` 精确命中而把它绑上去，`missing` 为空，最终误报 ready——这正是 §26 观察到的现象的资产侧根因。

本轮任务 B 的修复是在**输出状态层**兜住这个问题（assessment 报 mismatch 就翻成 missing_data），但没有触及资产选择本身。更深的修法（把 `intent.quant_hint` 传进 `_select_asset`，让 count/abundance 的选择对齐用户声明的数据类型，而不是只靠 role 名）留给后续——按任务书要求先不动，仅在此说明当前行为与代码位置。

