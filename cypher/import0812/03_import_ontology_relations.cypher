// 1. Individual - IN_STUDY -> Study
LOAD CSV WITH HEADERS FROM 'file:///relations/individual_in_study.csv' AS row
MATCH (i:individual {individual_accession: row.individual_accession})
MATCH (st:study {study_accession: row.study_accession})
MERGE (i)-[:in_study]->(st);

// 2. Sample - IN_INDIVIDUAL -> Individual
LOAD CSV WITH HEADERS FROM 'file:///relations/sample_in_individual.csv' AS row
MATCH (s:sample {sample_accession: row.sample_accession})
MATCH (i:individual {individual_accession: row.individual_accession})
MERGE (s)-[:in_individual]->(i);

// 3. Study - IN_PROJECT -> Project
LOAD CSV WITH HEADERS FROM 'file:///relations/study_in_project.csv' AS row
MATCH (st:study {study_accession: row.study_accession})
MATCH (p:project {project_accession: row.project_accession})
MERGE (st)-[:in_project]->(p);

// 4. T1 - IN_SAMPLE -> Sample
LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_sample.csv' AS row
MATCH (t1:T1 {T1_id: row.T1_id})
MATCH (s:sample {sample_accession: row.sample_accession})
MERGE (t1)-[:in_sample]->(s);

// 5. T1 - IN_STUDY -> Study
LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_study.csv' AS row
MATCH (t1:T1 {T1_id: row.T1_id})
MATCH (st:study {study_accession: row.study_accession})
MERGE (t1)-[:in_study]->(st);

// 6. T1 Reference Relations (Format, Level, Modal)
LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_format.csv' AS row
MATCH (t1:T1 {T1_id: row.T1_id})
MATCH (f:format {format: row.semantic_format})
MERGE (t1)-[:in_format]->(f);

LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_level.csv' AS row
MATCH (t1:T1 {T1_id: row.T1_id})
MATCH (l:datalevel {level: row.data_level})
MERGE (t1)-[:in_level]->(l);

LOAD CSV WITH HEADERS FROM 'file:///relations/T1_in_modal.csv' AS row
MATCH (t1:T1 {T1_id: row.T1_id})
MATCH (m:modal {modal: row.modal})
MERGE (t1)-[:in_modal]->(m);

// 7. T2 - GENERATED_FROM -> T1
LOAD CSV WITH HEADERS FROM 'file:///relations/T2_generated_from_T1.csv' AS row
MATCH (t2:T2 {T2_id: row.T2_id})
MATCH (t1:T1 {T1_id: row.T1_id})
MERGE (t2)-[:generated_from]->(t1);

// 8. T2 - IN_STUDY -> Study
LOAD CSV WITH HEADERS FROM 'file:///relations/T2_in_study.csv' AS row
MATCH (t2:T2 {T2_id: row.T2_id})
MATCH (st:study {study_accession: row.study_accession})
MERGE (t2)-[:in_study]->(st);

// 9. T2 Reference Relations (Format, Level, Modal)
LOAD CSV WITH HEADERS FROM 'file:///relations/T2_in_format.csv' AS row
MATCH (t2:T2 {T2_id: row.T2_id})
MATCH (f:format {format: row.semantic_format})
MERGE (t2)-[:in_format]->(f);

LOAD CSV WITH HEADERS FROM 'file:///relations/T2_in_level.csv' AS row
MATCH (t2:T2 {T2_id: row.T2_id})
MATCH (l:datalevel {level: row.data_level})
MERGE (t2)-[:in_level]->(l);

LOAD CSV WITH HEADERS FROM 'file:///relations/T2_in_modal.csv' AS row
MATCH (t2:T2 {T2_id: row.T2_id})
MATCH (m:modal {modal: row.modal})
MERGE (t2)-[:in_modal]->(m);