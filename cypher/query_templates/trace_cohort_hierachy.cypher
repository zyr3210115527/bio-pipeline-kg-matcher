//问题描述
//liver_cancer 属于哪个上位分类？
//疾病分类层级如何组织？

MATCH path = (c:Cohort {name:'liver_cancer'})-[:SUBCLASS_OF*]->(parent:Cohort)
RETURN path;
//结构化版本

MATCH path = (c:Cohort {name:'liver_cancer'})-[:SUBCLASS_OF*0..]->(parent:Cohort)
RETURN [n IN nodes(path) | n.name] AS hierarchy;