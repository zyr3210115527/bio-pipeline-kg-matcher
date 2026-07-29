//问题描述
//RNASeq_DE_Analysis_Workflow 使用了哪些工具？
//SomaticVariant_Analysis_Workflow 由哪些工具组成？
//说明
//这是最直接的 workflow 展开方式。


MATCH (wf:Tool {toolName:'RNASeq_DE_Analysis_Workflow'})-[:USES_TOOL]->(t:Tool)
RETURN wf.toolName AS workflow, collect(t.toolName) AS used_tools;
