// --- 1. Data Level ---
LOAD CSV WITH HEADERS FROM 'file:///reference/data_level.csv' AS row
MERGE (l:datalevel {level: row.level})
SET l.name = row.name,
    l.description = row.description;

// --- 2. Shared Formats (处理BOM头和中英文字段名) ---
LOAD CSV WITH HEADERS FROM 'file:///reference/formats.csv' AS row
MERGE (fo:format {format: COALESCE(row['语义格式'], row['﻿语义格式'])})
SET fo.description = row.description;

// --- 3. Functions ---
LOAD CSV WITH HEADERS FROM 'file:///reference/function.csv' AS row
MERGE (f:function {function: row.function})
SET f.description = row.description;

// --- 4. Shared Multimodal ---
LOAD CSV WITH HEADERS FROM 'file:///reference/multimodal.csv' AS row
MERGE (m:modal {modal: row.modal})
SET m.description = row.description;

// --- 5. Format 父子关系（0812 新增）---
// 数据侧标的是具体格式（HRR*.BQSR.bam 标 DNA_ALIGNMENT_BQSR_BAM），工具侧写的是
// 通用格式（DNA_GENOMIC_ALIGNMENT_BAM）。这张表把两者挂上父子边，图上按语义格式
// 找工具时可以沿边向上找。必须放在 formats 之后。
LOAD CSV WITH HEADERS FROM 'file:///reference/format_subclass.csv' AS row
MATCH (child:format {format: row.child})
MATCH (parent:format {format: row.parent})
MERGE (child)-[:subclass_of]->(parent);