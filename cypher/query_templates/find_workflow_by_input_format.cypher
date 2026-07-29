//问题描述
//哪些 workflow 以 FASTQ 为输入？
//哪些 workflow 接受 BAM 作为输入？
//说明
//这是 workflow 层面的入口查询。


MATCH (wf:Tool)-[:IS_TOOL_TYPE]->(:ToolType {name:'workflow'})
MATCH (wf)-[:INPUT]->(f:Format {name:'FASTQ'})
RETURN wf.toolId, wf.toolName, wf.version
ORDER BY wf.toolName;
