// ===== 0811 图谱普通索引 =====
// 与 00_clear.cypher 的 DROP INDEX 清单对齐，唯一约束自带的索引不在此重复创建。
//
// 有意省略 sample_type_index：0811 的 sample 表是 run 级，没有 sample_type 列，
// 该索引在新 schema 下无对应属性（见图谱变更说明 §7）。00_clear 里的 DROP 带
// IF EXISTS，保留无害。

CREATE INDEX project_name_index IF NOT EXISTS FOR (n:project) ON (n.project_name);
CREATE INDEX tool_name_index IF NOT EXISTS FOR (n:tool) ON (n.tool_name);
CREATE INDEX individual_tumor_type_index IF NOT EXISTS FOR (n:individual) ON (n.tumor_type);
CREATE INDEX individual_primary_site_index IF NOT EXISTS FOR (n:individual) ON (n.primary_tumor_site);
CREATE INDEX study_tumor_type_index IF NOT EXISTS FOR (n:study) ON (n.tumor_type);
CREATE INDEX T1_strategy_index IF NOT EXISTS FOR (n:T1) ON (n.strategy);
CREATE INDEX T1_platform_index IF NOT EXISTS FOR (n:T1) ON (n.platform);
CREATE INDEX T2_strategy_index IF NOT EXISTS FOR (n:T2) ON (n.strategy);
CREATE INDEX T2_file_path_index IF NOT EXISTS FOR (n:T2) ON (n.file_path);
