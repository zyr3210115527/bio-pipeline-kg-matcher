//问题描述
//从 FastQC 出发，当前图中能走到哪些工具路径？
//从 BWA 出发可能有哪些后续链？

MATCH path = (start:Tool {toolName:'FastQC'})-[:NEXT_TOOL*]->(end:Tool)
RETURN path;
//结构化版本

MATCH path = (start:Tool {toolName:'FastQC'})-[:NEXT_TOOL*0..]->(end:Tool)
RETURN [n IN nodes(path) | n.toolName] AS tool_path;