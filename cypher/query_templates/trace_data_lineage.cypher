//问题描述
//Annotated_MAF_Sample_1 是从哪些数据派生来的？
//Count_Matrix_Sample_1 的上游来源是什么？
//某个结果文件是如何一路产生的？

MATCH path = (d:Data {dataName:'Annotated_MAF_Sample_1'})-[:DERIVED_FROM*]->(upstream:Data)
RETURN path;
//结构化版本
//说明
//这是数据追溯的关键模板。

MATCH path = (d:Data {dataName:'Annotated_MAF_Sample_1'})-[:DERIVED_FROM*0..]->(upstream:Data)
RETURN [n IN nodes(path) | n.dataName] AS lineage;
