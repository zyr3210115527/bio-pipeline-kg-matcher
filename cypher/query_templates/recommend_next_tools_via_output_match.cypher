// 问题描述
//STAR 之后还能接哪些工具？
//某个工具输出的格式，哪些工具可以继续接？
//说明
//这是非常适合智能体做“下一步推荐”的基础模板。

MATCH (t1:Tool {toolName:'STAR'})-[:OUTPUT]->(f:Format)
MATCH (t2:Tool)-[:INPUT]->(f)
WHERE t1 <> t2
RETURN t1.toolName AS current_tool,
       f.name AS intermediate_format,
       collect(DISTINCT t2.toolName) AS candidate_next_tools;