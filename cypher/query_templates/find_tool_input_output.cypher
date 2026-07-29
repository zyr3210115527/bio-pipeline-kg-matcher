//问题描述
//STAR 的输入输出是什么？
//GATK 接受什么格式，输出什么格式？
//DESeq2 的输入是什么？
//说明
//这对工具说明和智能体回答都很有用。

MATCH (t:Tool {toolName:'STAR'})
OPTIONAL MATCH (t)-[:INPUT]->(i:Format)
OPTIONAL MATCH (t)-[:OUTPUT]->(o:Format)
RETURN t.toolName,
       collect(DISTINCT i.name) AS inputs,
       collect(DISTINCT o.name) AS outputs;
