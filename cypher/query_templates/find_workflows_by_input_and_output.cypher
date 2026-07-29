//问题描述
//哪些 workflow 以 FASTQ 为输入并输出 MAF？
//哪些 workflow 以 FASTQ 为输入并输出 CSV？

MATCH (wf:Tool)-[:IS_TOOL_TYPE]->(:ToolType {name:'workflow'})
MATCH (wf)-[:INPUT]->(:Format {name:'FASTQ'})
MATCH (wf)-[:OUTPUT]->(:Format {name:'MAF'})
RETURN wf.toolId, wf.toolName, wf.version
ORDER BY wf.toolName;