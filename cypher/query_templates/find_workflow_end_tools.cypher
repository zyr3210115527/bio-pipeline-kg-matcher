//问题描述
//当前图中哪些工具可能是流程终点？
//哪些工具只有入边没有出边？

MATCH (t:Tool)
WHERE NOT EXISTS {MATCH (:Tool)-[:NEXT_TOOL]->(t)}
AND EXISTS {MATCH (t)-[:NEXT_TOOL]->(Tool)}
RETURN DISTINCT t.toolId, t.toolName
ORDER BY t.toolName;