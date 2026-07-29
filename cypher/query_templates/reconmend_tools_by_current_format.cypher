//问题描述
//我现在有 BAM，下一步可以用哪些工具？
//当前是 MAF，可以做什么分析？
//我有 VCF，哪些工具可能能继续处理？

//说明
//这是“下一步推荐”的最基础模板。


MATCH (t:Tool)-[:INPUT]->(:Format {name:'BAM'})
OPTIONAL MATCH (t)-[:OUTPUT]->(o:Format)
RETURN t.toolId, t.toolName, collect(DISTINCT o.name) AS outputs
ORDER BY t.toolName;
