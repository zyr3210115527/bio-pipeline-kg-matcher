// ======================================================
// 1. 节点数量统计 (核对导入总量)
// ======================================================
MATCH (n:Tool) RETURN 'Tool' AS label, count(n) AS count
UNION ALL
MATCH (n:T2) RETURN 'T2' AS label, count(n) AS count
UNION ALL
MATCH (n:T1) RETURN 'T1' AS label, count(n) AS count
UNION ALL
MATCH (n:Study) RETURN 'Study' AS label, count(n) AS count
UNION ALL
MATCH (n:Individual) RETURN 'Individual' AS label, count(n) AS count
UNION ALL
MATCH (n:Project) RETURN 'Project' AS label, count(n) AS count
UNION ALL
MATCH (n:Run) RETURN 'Run' AS label, count(n) AS count
UNION ALL
MATCH (n:Sample) RETURN 'Sample' AS label, count(n) AS count
UNION ALL
MATCH (n:Function) RETURN 'Function' AS label, count(n) AS count
UNION ALL
MATCH (n:ToolType) RETURN 'ToolType' AS label, count(n) AS count
UNION ALL
MATCH (n:Modal) RETURN 'Modal (MultiOmics)' AS label, count(n) AS count
UNION ALL
MATCH (n:Format) RETURN 'Format' AS label, count(n) AS count
UNION ALL
MATCH (n:DataLevel) RETURN 'DataLevel' AS label, count(n) AS count
UNION ALL
MATCH (n:Cohort) RETURN 'Cohort' AS label, count(n) AS count;

// ======================================================
// 2. 异常检测：未关联类型的工具 (检查 tool_id, tool_name)
// ======================================================
MATCH (t:Tool)
// 假设您在导入时建立了与 ToolType 的关系，若无此关系则检查属性
OPTIONAL MATCH (t)-[:IS_TOOL_TYPE]->(tt:ToolType) 
WHERE tt IS NULL AND t.type IS NULL
RETURN t.tool_id, t.tool_name;

// ======================================================
// 3. 异常检测：未关联格式的 T2 数据
// ======================================================
MATCH (d:T2)
OPTIONAL MATCH (d)-[:IN_FORMAT]->(f:Format)
WHERE f IS NULL
RETURN d.t2_id, d.files, d.file_path;

// ======================================================
// 4. 工作流工具列表 (过滤 ToolType 为 workflow 的工具)
// ======================================================
// 这里的逻辑取决于您导入时是将 type 作为属性还是节点
MATCH (t:Tool)
WHERE t.type = 'workflow' OR (t)-[:IS_TOOL_TYPE]->(:ToolType {type:'workflow'})
RETURN t.tool_id, t.tool_name;

// ======================================================
// 5. 工具输入/输出汇总 (核对 04_import_workflow_relations.cypher 结果)
// ======================================================
MATCH (t:Tool)
OPTIONAL MATCH (t)-[:INPUT]->(i:Format)
OPTIONAL MATCH (t)-[:OUTPUT]->(o:Format)
RETURN t.tool_name, 
       collect(DISTINCT i.format) AS inputs, 
       collect(DISTINCT o.format) AS outputs
ORDER BY t.tool_name;

// ======================================================
// 6. 验证 T1 -> Run -> Sample 链路
// ======================================================
MATCH (t1:T1)-[:IN_RUN]->(r:Run)-[:IN_SAMPLE]->(s:Sample)
RETURN t1.runAccession, r.run_accession, s.sample_accession
LIMIT 10;