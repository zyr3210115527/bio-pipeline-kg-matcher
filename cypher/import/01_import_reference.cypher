// --- Functions ---
LOAD CSV WITH HEADERS FROM 'file:///reference/function.csv' AS row
MERGE (f:Function {function: row.function})
SET f.description = row.description;

// --- Tool Types ---
LOAD CSV WITH HEADERS FROM 'file:///reference/tool_types.csv' AS row
MERGE (tt:ToolType {type: row.type})
SET tt.description = row.description;

// --- Shared Multimodal ---
LOAD CSV WITH HEADERS FROM 'file:///reference/multimodal.csv' AS row
MERGE (m:Modal {modal: row.modal})
SET m.description = row.description;

// --- Shared Formats ---
LOAD CSV WITH HEADERS FROM 'file:///reference/formats.csv' AS row
MERGE (fo:Format {format: COALESCE(row['语义格式'], row['﻿语义格式'])})
SET fo.description = row.description;

// --- Data Level ---
LOAD CSV WITH HEADERS FROM 'file:///reference/data_level.csv' AS row
MERGE (l:DataLevel {level: row.level})
SET l.name = row.name,
    l.description = row.description;

// --- Cohorts ---
LOAD CSV WITH HEADERS FROM 'file:///reference/cohorts.csv' AS row
MERGE (c:Cohort {status: row.status})
SET c.description = row.description;

// --- Cohort hierarchy ---
LOAD CSV WITH HEADERS FROM 'file:///reference/cohort_subclass.csv' AS row
MATCH (ch:Cohort {status: row.child})
MATCH (p:Cohort {status: row.parent})
MERGE (ch)-[:IS_SUBTYPE_OF]->(p);