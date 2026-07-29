// --- 核心实体约束 ---
CREATE CONSTRAINT project_accession_unique IF NOT EXISTS FOR (n:Project) REQUIRE n.project_accession IS UNIQUE;
CREATE CONSTRAINT study_accession_unique IF NOT EXISTS FOR (n:Study) REQUIRE n.study_accession IS UNIQUE;
CREATE CONSTRAINT individual_accession_unique IF NOT EXISTS FOR (n:Individual) REQUIRE n.individual_accession IS UNIQUE;
CREATE CONSTRAINT sample_accession_unique IF NOT EXISTS FOR (n:Sample) REQUIRE n.sample_accession IS UNIQUE;
CREATE CONSTRAINT run_accession_unique IF NOT EXISTS FOR (n:Run) REQUIRE n.run_accession IS UNIQUE;
CREATE CONSTRAINT tool_id_unique IF NOT EXISTS FOR (n:Tool) REQUIRE n.tool_id IS UNIQUE;

// --- T1 & T2 数据文件约束 ---
CREATE CONSTRAINT T1_dataName_unique IF NOT EXISTS FOR (n:T1) REQUIRE n.dataName IS UNIQUE;

// 【重要修改】使用 t2_id 作为唯一主键，而不是 files
CREATE CONSTRAINT T2_id_unique IF NOT EXISTS FOR (n:T2) REQUIRE n.t2_id IS UNIQUE;

// --- 参考字典类约束 ---
CREATE CONSTRAINT cohort_status_unique IF NOT EXISTS FOR (n:Cohort) REQUIRE n.status IS UNIQUE;
CREATE CONSTRAINT format_name_unique IF NOT EXISTS FOR (n:Format) REQUIRE n.format IS UNIQUE;
CREATE CONSTRAINT function_name_unique IF NOT EXISTS FOR (n:Function) REQUIRE n.function IS UNIQUE;
CREATE CONSTRAINT level_value_unique IF NOT EXISTS FOR (n:DataLevel) REQUIRE n.level IS UNIQUE;
CREATE CONSTRAINT tool_type_unique IF NOT EXISTS FOR (n:ToolType) REQUIRE n.type IS UNIQUE;
CREATE CONSTRAINT modal_name_unique IF NOT EXISTS FOR (n:Modal) REQUIRE n.modal IS UNIQUE;
