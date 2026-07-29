//问题描述
//哪些工具支持 linux？
//哪些工具支持 windows？
//某个平台可用哪些工具？

MATCH (t:Tool)-[:SUPPORTS_PLATFORM]->(p:Platform {name:'linux'})
RETURN t.toolId, t.toolName, t.version
ORDER BY t.toolName;