// 问题描述
//哪些 genomics 工具支持 linux？
//哪些 transcriptomics 工具支持 windows？

MATCH (t:Tool)-[:APPLY_FOR_MULTIOMICS]->(:MultiOmics {name:'genomics'})
MATCH (t)-[:SUPPORTS_PLATFORM]->(:Platform {name:'linux'})
RETURN t.toolId, t.toolName, t.version
ORDER BY t.toolName;