//问题描述
//哪些工具具有 variant_analysis 功能并且输入是 BAM？
//哪些工具做 expression_analysis 且接受 TSV？

MATCH (t:Tool)-[:HAS_FUNCTION]->(:Function {name:'variant_analysis'})
MATCH (t)-[:INPUT]->(:Format {name:'BAM'})
RETURN t.toolId, t.toolName, t.version
ORDER BY t.toolName;