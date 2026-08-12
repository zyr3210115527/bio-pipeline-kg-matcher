//问题描述
//某个研究里每个个体挂了哪些样本，用于人工判断是否成对。
//
//注意：0811 的 sample 表是 run 级，不带样本级 specimen_types，所以**图里查不出
//权威的 tumor/normal 角色**。运行时的角色判定走
//data/0811_supplement/sample_specimen_backfill.csv 旁路映射
//（见 pipeline_router.STUDY_ROLE_RULES 与 Neo4jKGDataMatcher._apply_specimen_sidecar）。
//这条模板只能给出图里现有的线索：sample_description 和 sample_name。

MATCH (s:sample)-[:in_individual]->(i:individual)
WHERE s.study_accession = $study_accession
WITH i,
     collect(DISTINCT s.sample_accession) AS samples,
     collect(DISTINCT s.sample_name) AS sample_names,
     collect(DISTINCT s.sample_description) AS descriptions
WHERE size(samples) > 1
RETURN i.individual_accession AS individual,
       samples,
       sample_names,
       descriptions
ORDER BY individual
LIMIT 50;
