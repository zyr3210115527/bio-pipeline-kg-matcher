//问题描述
//我现在有 Aligned_BAM_Sample_1，下一步可以用什么工具？
//给定具体数据实例，推荐候选工具

MATCH (d:Data {dataName:'Aligned_BAM_Sample_1'})-[:IN_FORMAT]->(f:Format)
MATCH (t:Tool)-[:INPUT]->(f)
RETURN d.dataName AS current_data,
       f.name AS current_format,
       collect(DISTINCT t.toolName) AS candidate_tools;