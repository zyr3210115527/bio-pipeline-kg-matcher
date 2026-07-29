//问题描述
//我当前有 FASTQ/BAM 对应的数据实例，可以走哪些 workflow？

MATCH (d:Data {dataName:'Raw_FASTQ_Sample_1'})-[:IN_FORMAT]->(f:Format)
MATCH (wf:Tool)-[:IS_TOOL_TYPE]->(:ToolType {name:'workflow'})
MATCH (wf)-[:INPUT]->(f)
RETURN d.dataName AS current_data,
       f.name AS current_format,
       collect(DISTINCT wf.toolName) AS candidate_workflows;
