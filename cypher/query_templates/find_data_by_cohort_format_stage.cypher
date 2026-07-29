//问题描述
//liver_cancer 队列中，哪些数据是 BAM 且处于 processed 阶段？
//健康队列中，哪些数据是 FASTQ 且处于 raw 阶段？

MATCH (d:Data)-[:BELONG_TO]->(:Cohort {name:'liver_cancer'})
MATCH (d)-[:IN_FORMAT]->(:Format {name:'BAM'})
MATCH (d)-[:IN_PROCESSING_STAGE]->(:ProcessingStage {name:'processed'})
RETURN d.dataName
ORDER BY d.dataName;