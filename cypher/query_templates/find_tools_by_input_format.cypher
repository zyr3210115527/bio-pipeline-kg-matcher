//问题描述
//哪些工具可以处理 FASTQ？
//哪些工具接受 BAM 作为输入？
//当前格式是 TSV，可以用什么工具继续分析？
//可替换参数 把 'FASTQ' 改成：'BAM''TSV''VCF''MAF'说明这是你后面做“工具推荐”的基础模板之一


MATCH (t:Tool)-[:INPUT]->(f:Format {name: 'FASTQ'})
RETURN t.toolId, t.toolName, t.version
ORDER BY t.toolName;
