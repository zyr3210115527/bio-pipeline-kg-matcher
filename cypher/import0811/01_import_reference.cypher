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