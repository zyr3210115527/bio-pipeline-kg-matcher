// ===== 0811 图谱唯一约束 =====
// 约束名与 00_clear.cypher 的 11 条 DROP 语句逐一对齐。
// 标签沿用师姐 0811 的小写风格；T1/T2 属于数据层级名称，保持大写。
// T1/T2 绑定到实际属性 T1_id / T2_id（旧版误绑小写 t1_id/t2_id，约束形同虚设）。

CREATE CONSTRAINT project_accession_unique IF NOT EXISTS FOR (n:project) REQUIRE n.project_accession IS UNIQUE;
CREATE CONSTRAINT study_accession_unique IF NOT EXISTS FOR (n:study) REQUIRE n.study_accession IS UNIQUE;
CREATE CONSTRAINT individual_accession_unique IF NOT EXISTS FOR (n:individual) REQUIRE n.individual_accession IS UNIQUE;
CREATE CONSTRAINT sample_accession_unique IF NOT EXISTS FOR (n:sample) REQUIRE n.sample_accession IS UNIQUE;
CREATE CONSTRAINT tool_id_unique IF NOT EXISTS FOR (n:tool) REQUIRE n.tool_id IS UNIQUE;
CREATE CONSTRAINT T1_id_unique IF NOT EXISTS FOR (n:T1) REQUIRE n.T1_id IS UNIQUE;
CREATE CONSTRAINT T2_id_unique IF NOT EXISTS FOR (n:T2) REQUIRE n.T2_id IS UNIQUE;
CREATE CONSTRAINT format_name_unique IF NOT EXISTS FOR (n:format) REQUIRE n.format IS UNIQUE;
CREATE CONSTRAINT function_name_unique IF NOT EXISTS FOR (n:function) REQUIRE n.function IS UNIQUE;
CREATE CONSTRAINT level_value_unique IF NOT EXISTS FOR (n:datalevel) REQUIRE n.level IS UNIQUE;
CREATE CONSTRAINT modal_name_unique IF NOT EXISTS FOR (n:modal) REQUIRE n.modal IS UNIQUE;
