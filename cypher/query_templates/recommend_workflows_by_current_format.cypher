//问题描述
//我当前有 FASTQ，可以走哪些 workflow？
//BAM 可以进入哪些 workflow？
//给定当前格式，推荐可用 workflow


MATCH (wf:Tool)-[:IS_TOOL_TYPE]->(:ToolType {name:'workflow'})
MATCH (wf)-[:INPUT]->(:Format {name:'FASTQ'})
RETURN wf.toolId, wf.toolName, wf.version
ORDER BY wf.toolName;