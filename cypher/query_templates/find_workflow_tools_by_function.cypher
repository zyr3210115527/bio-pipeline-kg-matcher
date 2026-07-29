//问题描述
//RNASeq workflow 中哪些工具负责 expression_analysis？
//体细胞变异 workflow 中哪些工具负责 annotation？


MATCH (wf:Tool {toolName:'RNASeq_DE_Analysis_Workflow'})-[:USES_TOOL]->(t:Tool)
MATCH (t)-[:HAS_FUNCTION]->(:Function {name:'expression_analysis'})
RETURN wf.toolName AS workflow, collect(t.toolName) AS matched_tools;