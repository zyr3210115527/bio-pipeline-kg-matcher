//问题描述
//当前图中有哪些 workflow？
//workflow 类型的工具有哪些？
//说明
//因为 workflow 仍然是 Tool 实例，所以这里通过 IS_TOOL_TYPE -> workflow 识别。


MATCH (wf:Tool)-[:IS_TOOL_TYPE]->(:ToolType {name:'workflow'})
RETURN wf.toolId, wf.toolName, wf.version
ORDER BY wf.toolName;
