// --- Tools ---
LOAD CSV WITH HEADERS FROM 'file:///entities/tool.csv' AS row
MERGE (t:Tool {tool_id: row.tool_id})
SET t.tool_name = row.tool_name,
    t.function = row.function,
    t.input_format_raw = row['输入格式'],
    t.output_format_raw = row['输出格式'],
    t.input_semantic = row['语义输入格式 (Semantic Input)'],
    t.output_semantic = row['语义输出格式 (Semantic Output)'],
    t.downstream_tools = row['下游工具'],
    t.omics = row['适用组学'];

// --- T1: one node per data file; paired reads share runAccession ---
LOAD CSV WITH HEADERS FROM 'file:///entities/T1.csv' AS row
MERGE (t1:T1 {dataName: row.dataName})
SET t1.runAccession = row.runAccession,
    t1.studyAccession = row.studyAccession,
    t1.individualAccession = row.individualAccession,
    t1.individualName = row.individualName,
    t1.sampleAccession = row.sampleAccession,
    t1.sampleDescription = row.sampleDescription,
    t1.sampleName = row.sampleName,
    t1.gender = row.gender,
    t1.experimentAccession = row.experimentAccession,
    t1.platform = row.platform,
    t1.strategy = row.strategy;


// --- T2 (修改后的部分) ---
LOAD CSV WITH HEADERS FROM 'file:///entities/T2.csv' AS row
MERGE (t2:T2 {t2_id: row.t2_id})
SET t2.study_accession = row.study_accession,
    t2.files = row.files,
    t2.file_type = row.file_type,
    t2.format = row.format,
    t2.size = row.size,
    t2.data_level = row.data_level,
    t2.size_bytes = row.size_bytes,
    t2.file_path = row.file_path,
    t2.strategy = row.strategy;


// --- Study ---
LOAD CSV WITH HEADERS FROM 'file:///entities/study.csv' AS row
MERGE (st:Study {study_accession: row.study_accession})
SET st.title = row.title,
    st.study_description = row.study_description,
    st.study_type = row.study_type,
    st.tumor_type = row.tumor_type,
    st.individual_count = toInteger(row.individual_count),
    st.sample_count = toInteger(row.sample_count),
    st.information_source = row.information_source;

// --- Project ---
LOAD CSV WITH HEADERS FROM 'file:///entities/project.csv' AS row
MERGE (p:Project {project_accession: row.project_accession})
SET p.project_name = row.project_name,
    p.project_code = row.project_code,
    p.relevance = row.relevance,
    p.project_description = row.project_description,
    p.data_types = row.data_types,
    p.organisms = row.organisms,
    p.sample_scope = row.sample_scope,
    p.individual_count = toInteger(row.individual_count),
    p.country = row.country,
    p.tumor_type = row.tumor_type,
    p.study_accession = row.study_accession,
    p.type = row.type,
    p.health_conditions = row.health_conditions,
    p.organization = row.organization,
    p.submission_date = row.submission_date,
    p.release_date = row.release_date,
    p.information_source = row.information_source;

// --- Individual ---
LOAD CSV WITH HEADERS FROM 'file:///entities/individual.csv' AS row
MERGE (i:Individual {individual_accession: row.individual_accession})
SET i.project_accession = row.project_accession,
    i.study_accession = row.study_accession,
    i.individual_id = row.individual_id,
    i.project_name = row.project_name,
    i.tumor_type = row.tumor_type,
    i.tumor_subtype = row.tumor_subtype,
    i.primary_tumor_site = row.primary_tumor_site,
    i.primary_tumor_location = row.primary_tumor_location,
    i.gender = row.gender,
    i.country = row.country,
    i.race = row.race,
    i.age = row.age,
    i.family_history = row.family_history,
    i.smoking = row.smoking,
    i.tumor_grade = row.tumor_grade,
    i.tumor_stage = row.tumor_stage,
    i.pathologic_t = row.pathologic_t,
    i.pathologic_n = row.pathologic_n,
    i.pathologic_m = row.pathologic_m,
    i.clinical_t = row.clinical_t,
    i.clinical_n = row.clinical_n,
    i.clinical_m = row.clinical_m,
    i.residual_tumor = row.residual_tumor,
    i.lymphatic_invasion = row.lymphatic_invasion,
    i.vessel_invasion = row.vessel_invasion,
    i.nerve_invasion = row.nerve_invasion,
    i.treatment_intent_type = row.treatment_intent_type,
    i.neoadjuvant_treatment_type = row.neoadjuvant_treatment_type,
    i.neoadjuvant_treatment_agents = row.neoadjuvant_treatment_agents,
    i.tmb = row.tmb,
    i.msi_score = row.msi_score,
    i.sample_type = row.sample_type,
    i.specimen_types = row.specimen_types,
    i.overall_survival_status = row.overall_survival_status,
    i.overall_survival_days = toInteger(row.overall_survival_days),
    i.overall_survival_time = row.overall_survival_time,
    i.progression_free_survival_status = row.progression_free_survival_status,
    i.disease_free_survival_time = row.disease_free_survival_time,
    i.gleason_score = row.gleason_score,
    i.neoadjuvant_treatment_outcome_pathological_response = row.neoadjuvant_treatment_outcome_pathological_response,
    i.adjuvant_treatment_agents = row.adjuvant_treatment_agents,
    i.adjuvant_treatment_outcome_response = row.adjuvant_treatment_outcome_response,
    i.tmb_status = row.tmb_status,
    i.fraction_genome_altered = row.fraction_genome_altered,
    i.msi_status = row.msi_status,
    i.dfs_status = row.dfs_status,
    i.overall_vital_status = row.overall_vital_status;

// --- Sample ---
LOAD CSV WITH HEADERS FROM 'file:///entities/sample.csv' AS row
MERGE (s:Sample {sample_accession: row.sample_accession})
SET s.study_accession = row.study_accession,
    s.sample_name = row.sample_name,
    s.sample_description = row.sample_description,
    s.individual_accession = row.individual_accession,
    s.individual_name = row.individual_name,
    s.biospecimen_anatomic_site = row.biospecimen_anatomic_site,
    s.sample_type = row.sample_type,
    s.specimen_types = row.specimen_types,
    s.strategy = row.strategy,
    s.tissue_type = row.tissue_type;
