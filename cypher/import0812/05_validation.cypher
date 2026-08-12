// 1. 节点数量统计
MATCH (n) 
RETURN labels(n) AS label, count(n) AS count;

// 2. 检查 T1 是否成功关联到 Sample 和 Study
MATCH (t1:T1)
OPTIONAL MATCH (t1)-[:in_sample]->(s:sample)
OPTIONAL MATCH (t1)-[:in_study]->(st:study)
RETURN t1.T1_id, s.sample_accession, st.study_accession
LIMIT 20;

// 3. 检查 T2 是否追溯到 T1
MATCH (t2:T2)-[:generated_from]->(t1:T1)
RETURN t2.T2_id, t1.T1_id
LIMIT 20;

// 4. 工具工作流验证
MATCH (t1:tool)-[:next_tool]->(t2:tool)
RETURN t1.tool_name, t2.tool_name
LIMIT 20;

// 5. 异常检测：未关联 DataLevel 的数据
MATCH (d) WHERE d:T1 OR d:T2
OPTIONAL MATCH (d)-[:in_level]->(l:datalevel)
WHERE l IS NULL
RETURN labels(d), d.T1_id, d.T2_id, d.file_name;

// 6. 语义格式覆盖率：T1/T2 未连上 Format 节点的行（T2 占位表的语义格式待映射，属已知项）
MATCH (d) WHERE d:T1 OR d:T2
OPTIONAL MATCH (d)-[:in_format]->(f:format)
WHERE f IS NULL
RETURN labels(d), coalesce(d.T1_id, d.T2_id) AS data_id, d.file_name
LIMIT 30;
