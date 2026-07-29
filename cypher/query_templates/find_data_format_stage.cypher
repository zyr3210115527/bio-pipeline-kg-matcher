//问题描述
//Raw_FASTQ_Sample_1 是什么格式？处于哪个 processing stage？
//Annotated_MAF_Sample_1 当前属于什么阶段？
//说明
//这是 Data 侧最基础的实例查询。


MATCH (d:Data {dataName:'Raw_FASTQ_Sample_1'})
OPTIONAL MATCH (d)-[:IN_FORMAT]->(f:Format)
OPTIONAL MATCH (d)-[:IN_PROCESSING_STAGE]->(s:ProcessingStage)
RETURN d.dataName, f.name AS format, s.name AS processing_stage;
