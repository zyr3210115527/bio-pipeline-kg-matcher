//问题描述
//当前图中的工具先后顺序关系是什么？
//RNA-seq 分析链条大致顺序是什么？

//说明
//当前你的 NEXT_TOOL 还是工具级全局顺序，不是 workflow 局部顺序。
//所以这个查询返回的是全图已有顺序关系

MATCH (t1:Tool)-[:NEXT_TOOL]->(t2:Tool)
RETURN t1.toolName AS from_tool, t2.toolName AS to_tool
ORDER BY from_tool, to_tool;


