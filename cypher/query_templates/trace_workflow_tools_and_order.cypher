//问题描述
//某个 workflow 内有哪些工具，以及它们之间已有的顺序链是什么？
//说明
//由于当前 NEXT_TOOL 不是 workflow-scoped，这个查询通过 USES_TOOL 做了一层局部过滤。


MATCH (wf:Tool {toolName: 'RNASeq_DE_Analysis_Workflow'})-[:USES_TOOL]->(t:Tool)
OPTIONAL MATCH (t)-[:NEXT_TOOL]->(t2:Tool)
WHERE t2 IS NULL OR EXISTS {
    MATCH (wf)-[:USES_TOOL]->(t2)
}
RETURN wf.toolName AS workflow,
       t.toolName AS from_tool,
       t2.toolName AS to_tool
ORDER BY from_tool, to_tool;