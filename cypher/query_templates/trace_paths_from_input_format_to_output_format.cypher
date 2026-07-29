//问题描述
//从 FASTQ 到 TSV，当前图中有哪些可能路径？
//从 FASTQ 到 MAF，图中有哪些候选工具链？

MATCH (startTool:Tool)-[:INPUT]->(:Format {name:'FASTQ'})
MATCH (endTool:Tool)-[:OUTPUT]->(:Format {name:'TSV'})
MATCH path = (startTool)-[:NEXT_TOOL*0..5]->(endTool)
RETURN path;
//结构化版本
//说明
//这里 0..5 是原型阶段给路径长度一个上限，避免路径爆炸。

MATCH (startTool:Tool)-[:INPUT]->(:Format {name:'FASTQ'})
MATCH (endTool:Tool)-[:OUTPUT]->(:Format {name:'TSV'})
MATCH path = (startTool)-[:NEXT_TOOL*0..5]->(endTool)
RETURN [n IN nodes(path) | n.toolName] AS tool_path;
