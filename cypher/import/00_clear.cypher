// ===== Neo4j 5.x 全量清空脚本 =====

// 1. 删除所有图数据
MATCH (n)
DETACH DELETE n;

// 2. 删除普通索引
DROP INDEX tool_name_index IF EXISTS;
DROP INDEX data_name_index IF EXISTS;
DROP INDEX study_accession_index IF EXISTS;
DROP INDEX project_accession_index IF EXISTS;
DROP INDEX individual_accession_index IF EXISTS;
DROP INDEX T1_name_index IF EXISTS;
DROP INDEX sample_accession_index IF EXISTS;


// 3. 删除约束
DROP CONSTRAINT tool_id_unique IF EXISTS;
DROP CONSTRAINT data_id_unique IF EXISTS;
DROP CONSTRAINT function_name_unique IF EXISTS;
DROP CONSTRAINT programming_language_name_unique IF EXISTS;
DROP CONSTRAINT tool_type_name_unique IF EXISTS;
DROP CONSTRAINT multiomics_name_unique IF EXISTS;
DROP CONSTRAINT format_name_unique IF EXISTS;
DROP CONSTRAINT data_level_name_unique IF EXISTS;
DROP CONSTRAINT cohort_name_unique IF EXISTS;
DROP CONSTRAINT study_accession_unique IF EXISTS;
DROP CONSTRAINT individual_accession_unique IF EXISTS;
DROP CONSTRAINT cohort_name_unique IF EXISTS;
DROP CONSTRAINT T2_name_unique IF EXISTS;
DROP CONSTRAINT data_level_name_unique IF EXISTS;
DROP CONSTRAINT format_name_unique IF EXISTS;
DROP CONSTRAINT function_name_unique IF EXISTS;
DROP CONSTRAINT individual_accession_unique IF EXISTS;
DROP CONSTRAINT multiomics_name_unique IF EXISTS;
DROP CONSTRAINT project_accession_unique IF EXISTS;
DROP CONSTRAINT run_accession_unique  IF EXISTS;
DROP CONSTRAINT study_accession_unique IF EXISTS;
DROP CONSTRAINT tool_id_unique IF EXISTS;
DROP CONSTRAINT tool_type_name_unique IF EXISTS;


// 4. 可选验证
SHOW INDEXES;
SHOW CONSTRAINTS;
MATCH (n) RETURN count(n) AS nodeCount;