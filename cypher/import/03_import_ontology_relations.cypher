// 1. Individual - IN_STUDY -> Study
LOAD CSV WITH HEADERS FROM 'file:///relations/individual_in_study.csv' AS row
MERGE (i:Individual {individual_accession: row.individual_accession})
ON CREATE SET i.placeholder = true
MATCH (st:Study {study_accession: row.study_accession})
MERGE (i)-[:IN_STUDY]->(st);

// 2. Run - IN_SAMPLE -> Sample
LOAD CSV WITH HEADERS FROM 'file:///relations/run_in_sample.csv' AS row
MERGE (r:Run {run_accession: row.run_accession}) 
WITH r, row
MERGE (s:Sample {sample_accession: row.sample_accession})
ON CREATE SET s.placeholder = true
MERGE (r)-[:IN_SAMPLE]->(s);

// 3. Sample - IN_INDIVIDUAL -> Individual
LOAD CSV WITH HEADERS FROM 'file:///relations/sample_in_individual.csv' AS row
MERGE (s:Sample {sample_accession: row.sample_accession})
ON CREATE SET s.placeholder = true
MERGE (i:Individual {individual_accession: row.individual_accession})
ON CREATE SET i.placeholder = true
MERGE (s)-[:IN_INDIVIDUAL]->(i);

// 4. Study - IN_PROJECT -> Project
LOAD CSV WITH HEADERS FROM 'file:///relations/study_in_project.csv' AS row
MATCH (st:Study {study_accession: row.study_accession})
MATCH (p:Project {project_accession: row.project_accession})
MERGE (st)-[:IN_PROJECT]->(p);

// 5. T1 - IN_FORMAT -> Format (T1使用dataName属性匹配CSV中的files列)
LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_format.csv' AS row
MATCH (t1:T1 {dataName: row.files})
MATCH (f:Format {format: row.format})
MERGE (t1)-[:IN_FORMAT]->(f);

// 6. T1 - IN_LEVEL -> DataLevel
LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_level.csv' AS row
MATCH (t1:T1 {dataName: row.files})
MATCH (l:DataLevel {level: row.data_level}) 
MERGE (t1)-[:IN_LEVEL]->(l);

// 7. T1 - IN_RUN -> Run
LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_run.csv' AS row
MATCH (t1:T1 {dataName: row.files})
MATCH (r:Run {run_accession: row.run_accession})
MERGE (t1)-[:IN_RUN]->(r);

// 8. T1 - IN_STUDY -> Study
LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_study.csv' AS row
MATCH (t1:T1 {dataName: row.files})
MATCH (st:Study {study_accession: row.study_accession})
MERGE (t1)-[:IN_STUDY]->(st);

// 9. T2 - IN_FORMAT -> Format
LOAD CSV WITH HEADERS FROM 'file:///relations/T2_in_format.csv' AS row
MATCH (t2:T2 {t2_id: row.t2_id})
MATCH (f:Format {format: row.format})
MERGE (t2)-[:IN_FORMAT]->(f);

// 10. T2 - IN_LEVEL -> DataLevel
LOAD CSV WITH HEADERS FROM 'file:///relations/T2_in_level.csv' AS row
MATCH (t2:T2 {t2_id: row.t2_id})
MATCH (l:DataLevel {level: row.level}) 
MERGE (t2)-[:IN_LEVEL]->(l);

// 11. T2 - IN_STUDY -> Study
LOAD CSV WITH HEADERS FROM 'file:///relations/T2_in_study.csv' AS row
MATCH (t2:T2 {t2_id: row.t2_id})
MATCH (st:Study {study_accession: row.study_accession})
MERGE (t2)-[:IN_STUDY]->(st);


// 12. Tool - HAS_FUNCTION -> Function 
LOAD CSV WITH HEADERS FROM 'file:///relations/tool_has_function.csv' AS row
MATCH (t:Tool {tool_id: row.tool_id})
MATCH (f:Function {function: row.function}) 
MERGE (t)-[:HAS_FUNCTION]->(f);
