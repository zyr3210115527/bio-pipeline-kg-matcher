//问题描述
//liver_cancer 队列下有哪些数据实例？
//某个疾病队列有哪些数据？

MATCH (d:Data)-[:BELONG_TO]->(c:Cohort {name:'liver_cancer'})
RETURN d.dataName
ORDER BY d.dataName;