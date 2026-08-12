// ===== Neo4j 5.x 全量清空脚本（名称与 cypher/schema/constraints.cypher、indexes.cypher 实际创建保持一致）=====

// 1. 删除约束（先删约束，约束自带的后台索引不能单独 DROP INDEX）
DROP CONSTRAINT project_accession_unique IF EXISTS;
DROP CONSTRAINT study_accession_unique IF EXISTS;
DROP CONSTRAINT individual_accession_unique IF EXISTS;
DROP CONSTRAINT sample_accession_unique IF EXISTS;
DROP CONSTRAINT tool_id_unique IF EXISTS;
DROP CONSTRAINT T1_id_unique IF EXISTS;
DROP CONSTRAINT T2_id_unique IF EXISTS;
DROP CONSTRAINT format_name_unique IF EXISTS;
DROP CONSTRAINT function_name_unique IF EXISTS;
DROP CONSTRAINT level_value_unique IF EXISTS;
DROP CONSTRAINT modal_name_unique IF EXISTS;

// 2. 删除普通索引
DROP INDEX project_name_index IF EXISTS;
DROP INDEX tool_name_index IF EXISTS;
DROP INDEX individual_tumor_type_index IF EXISTS;
DROP INDEX individual_primary_site_index IF EXISTS;
DROP INDEX study_tumor_type_index IF EXISTS;
DROP INDEX T1_strategy_index IF EXISTS;
DROP INDEX T1_platform_index IF EXISTS;
DROP INDEX sample_type_index IF EXISTS;
DROP INDEX T2_strategy_index IF EXISTS;
DROP INDEX T2_file_path_index IF EXISTS;

// 3. 删除所有节点和关系
MATCH (n) DETACH DELETE n;

// 4. 验证
SHOW INDEXES;
SHOW CONSTRAINTS;
MATCH (n) RETURN count(n) AS nodeCount;
