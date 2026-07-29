//问题描述
//哪些工具会输出 BAM？
//哪些工具会输出 VCF？
//哪些工具会输出 MAF？
//说明
//这个模板适合做“结果格式导向的工具筛选”。


MATCH (t:Tool)-[:OUTPUT]->(f:Format {name: 'BAM'})
RETURN t.toolId, t.toolName, t.version
ORDER BY t.toolName;
