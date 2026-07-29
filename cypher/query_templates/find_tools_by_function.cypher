//问题描述
//哪些工具具有 variant_analysis 功能？
//哪些工具可用于 expression_analysis？
//哪些工具做 annotation？

MATCH (t:Tool)-[:HAS_FUNCTION]->(f:Function {name:'variant_analysis'})
RETURN t.toolId, t.toolName, t.version
ORDER BY t.toolName;