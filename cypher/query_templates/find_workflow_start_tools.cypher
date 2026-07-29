//问题描述
//当前图中哪些工具可能是流程起点？
//哪些工具只有出边没有入边？
//说明
//这是基于当前全局 NEXT_TOOL 图的起点推测。

MATCH (t:Tool)
WHERE NOT EXISTS {
    MATCH (:Tool)-[:NEXT_TOOL]->(t)
}
AND EXISTS {
    MATCH (t)-[:NEXT_TOOL]->(:Tool)
}
RETURN t.toolId, t.toolName
ORDER BY t.toolName;