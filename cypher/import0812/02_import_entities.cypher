// --- 1. Project ---
LOAD CSV WITH HEADERS FROM 'file:///entities/project.csv' AS row
MERGE (p:project {project_accession: row.project_accession})
SET p.study_accession = nullIf(row.study_accession, ''),
    p.project_name = nullIf(row.project_name, ''),
    p.relevance = nullIf(row.relevance, ''),
    p.data_type = nullIf(row.data_type, ''),
    p.organism = nullIf(row.organism, ''),
    p.project_description = nullIf(row.project_description, ''),
    p.sample_scope = nullIf(row.sample_scope, ''),
    p.project_code = nullIf(row.project_code, ''),
    p.data_types = nullIf(row.data_types, ''),
    p.individual_count = toInteger(row.individual_count),
    p.country = nullIf(row.country, ''),
    p.tumor_type = nullIf(row.tumor_type, ''),
    p.type = nullIf(row.type, ''),
    p.organization = nullIf(row.organization, ''),
    p.release_date = nullIf(row.release_date, ''),
    p.submission_date = nullIf(row.submission_date, ''),
    p.information_source = nullIf(row.information_source, '');

// --- 2. Study ---
LOAD CSV WITH HEADERS FROM 'file:///entities/study.csv' AS row
MERGE (st:study {study_accession: row.study_accession})
SET st.title = nullIf(row.Title, ''),
    st.study_description = nullIf(row.study_description, ''),
    st.study_type = nullIf(row.study_type, ''),
    st.tumor_type = nullIf(row.tumor_type, ''),
    st.individual_count = toInteger(row.individual_count),
    st.sample_count = toInteger(row.sample_count),
    st.information_source = nullIf(row.information_source, '');

// --- 3. Individual (包含所有104个字段) ---
LOAD CSV WITH HEADERS FROM 'file:///entities/individual.csv' AS row
WITH row, coalesce(row.individual_accession, row['﻿individual_accession']) AS individual_accession
WHERE individual_accession IS NOT NULL
MERGE (i:individual {individual_accession: individual_accession})
SET i.project_accession = nullIf(row.project_accession, ''),
    i.study_accession = nullIf(row.study_accession, ''),
    i.individual_id = nullIf(row.individual_id, ''),
    i.project_name = nullIf(row.project_name, ''),
    i.tumor_type = nullIf(row.tumor_type, ''),
    i.tumor_subtype = nullIf(row.tumor_subtype, ''),
    i.primary_tumor_site = nullIf(row.primary_tumor_site, ''),
    i.primary_tumor_location = nullIf(row.primary_tumor_location, ''),
    i.gender = nullIf(row.gender, ''),
    i.country = nullIf(row.country, ''),
    i.race = nullIf(row.race, ''),
    i.age = nullIf(row.age, ''),
    i.family_history = nullIf(row.family_history, ''),
    i.smoking = nullIf(row.smoking, ''),
    i.tumor_grade = nullIf(row.tumor_grade, ''),
    i.tumor_stage = nullIf(row.tumor_stage, ''),
    i.pathologic_t = nullIf(row.pathologic_t, ''),
    i.pathologic_n = nullIf(row.pathologic_n, ''),
    i.pathologic_m = nullIf(row.pathologic_m, ''),
    i.clinical_t = nullIf(row.clinical_t, ''),
    i.clinical_n = nullIf(row.clinical_n, ''),
    i.clinical_m = nullIf(row.clinical_m, ''),
    i.residual_tumor = nullIf(row.residual_tumor, ''),
    i.lymphatic_invasion = nullIf(row.lymphatic_invasion, ''),
    i.vessel_invasion = nullIf(row.vessel_invasion, ''),
    i.nerve_invasion = nullIf(row.nerve_invasion, ''),
    i.treatment_intent_type = nullIf(row.treatment_intent_type, ''),
    i.tmb = nullIf(row.tmb, ''),
    i.msi_score = nullIf(row.msi_score, ''),
    i.survival_status = nullIf(row.survival_status, ''),
    i.survival_days = nullIf(row.survival_days, ''),
    i.sample_type = nullIf(row.sample_type, ''),
    i.specimen_types = nullIf(row.specimen_types, ''),
    i.survival_information = nullIf(row.survival_information, ''),
    i.sample_name = nullIf(row.sample_name, ''),
    i.run_accession = nullIf(row.run_accession, ''),
    i.neoadjuvant_treatment_type = nullIf(row.neoadjuvant_treatment_type, ''),
    i.neoadjuvant_treatment_agents = nullIf(row.neoadjuvant_treatment_agents, ''),
    i.survival_time = nullIf(row.survival_time, ''),
    i.vital_status = nullIf(row.vital_status, ''),
    i.project_id = nullIf(row.project_id, ''),
    i.sample_accession = nullIf(row.sample_accession, ''),
    i.program = nullIf(row.program, ''),
    i.ethinicity = nullIf(row.ethinicity, ''),
    i.who_classification_2022 = nullIf(row.who_classification_2022, ''),
    i.surgery = nullIf(row.surgery, ''),
    i.neoadjuvant_treatment_outcome_radiological_response = nullIf(row.neoadjuvant_treatment_outcome_radiological_response, ''),
    i.neoadjuvant_treatment_outcome_pathological_response = nullIf(row.neoadjuvant_treatment_outcome_pathological_response, ''),
    i.adjuvant_treatment_type = nullIf(row.adjuvant_treatment_type, ''),
    i.adjuvant_treatment_agents = nullIf(row.adjuvant_treatment_agents, ''),
    i.number_of_adjuvant_treatments = nullIf(row.number_of_adjuvant_treatments, ''),
    i.treatment_type_for_non_surgical_patients = nullIf(row.treatment_type_for_non_surgical_patients, ''),
    i.treatment_regimens_for_non_surgical_patients = nullIf(row.treatment_regimens_for_non_surgical_patients, ''),
    i.treatment_agents_for_non_surgical_patients = nullIf(row.treatment_agents_for_non_surgical_patients, ''),
    i.treatment_outcome_for_non_surgical_patients = nullIf(row.treatment_outcome_for_non_surgical_patients, ''),
    i.hsct = nullIf(row.hsct, ''),
    i.overall_survival_time = nullIf(row.overall_survival_time, ''),
    i.dfs_time = nullIf(row.dfs_time, ''),
    i.dfs_status = nullIf(row.dfs_status, ''),
    i.pfs_time = nullIf(row.pfs_time, ''),
    i.pfs_status = nullIf(row.pfs_status, ''),
    i.efs_time = nullIf(row.efs_time, ''),
    i.efs_status = nullIf(row.efs_status, ''),
    i.survival_information_category = nullIf(row.survival_information_category, ''),
    i.relapse = nullIf(row.relapse, ''),
    i.tmb_status = nullIf(row.tmb_status, ''),
    i.fraction_genome_altered = nullIf(row.fraction_genome_altered, ''),
    i.msi_status = nullIf(row.msi_status, ''),
    i.individual_tumor_desciptor = nullIf(row.individual_tumor_desciptor, ''),
    i.individual_specimen_types = nullIf(row.individual_specimen_types, ''),
    i.individual_biospecimen_anatomic_site = nullIf(row.individual_biospecimen_anatomic_site, ''),
    i.individual_tissue_type = nullIf(row.individual_tissue_type, ''),
    i.experimental_strategy = nullIf(row.experimental_strategy, ''),
    i.data_type = nullIf(row.data_type, ''),
    i.data_tier = nullIf(row.data_tier, ''),
    i.analysis_pipeline = nullIf(row.analysis_pipeline, ''),
    i.format = nullIf(row.format, ''),
    i.platform = nullIf(row.platform, ''),
    i.fab_classification = nullIf(row.fab_classification, ''),
    i.proportion_of_bone_marrow_blast_cells = nullIf(row.proportion_of_bone_marrow_blast_cells, ''),
    i.white_blood_cell_counts_109_l = nullIf(row.white_blood_cell_counts_109_l, ''),
    i.hgb_concentration_g_l = nullIf(row.hgb_concentration_g_l, ''),
    i.plt_counts_109_l = nullIf(row.plt_counts_109_l, ''),
    i.karyotype = nullIf(row.karyotype, ''),
    i.karyotype_subtype = nullIf(row.karyotype_subtype, ''),
    i.gene_fusions = nullIf(row.gene_fusions, ''),
    i.risk_stratification = nullIf(row.risk_stratification, ''),
    i.adjuvant_treatment_1_gap = nullIf(row.adjuvant_treatment_1_gap, ''),
    i.adjuvant_treatment_1_duration_d = nullIf(row.adjuvant_treatment_1_duration_d, ''),
    i.adjuvant_treatment_1_drugs = nullIf(row.adjuvant_treatment_1_drugs, ''),
    i.adjuvant_treatment_1_type = nullIf(row.adjuvant_treatment_1_type, ''),
    i.adjuvant_treatment_2_gap = nullIf(row.adjuvant_treatment_2_gap, ''),
    i.adjuvant_treatment_2_duration_d = nullIf(row.adjuvant_treatment_2_duration_d, ''),
    i.adjuvant_treatment_2_drugs = nullIf(row.adjuvant_treatment_2_drugs, ''),
    i.adjuvant_treatment_2_type = nullIf(row.adjuvant_treatment_2_type, ''),
    i.adjuvant_treatment_3_gap = nullIf(row.adjuvant_treatment_3_gap, ''),
    i.adjuvant_treatment_3_duration_d = nullIf(row.adjuvant_treatment_3_duration_d, ''),
    i.adjuvant_treatment_3_drugs = nullIf(row.adjuvant_treatment_3_drugs, ''),
    i.adjuvant_treatment_3_type = nullIf(row.adjuvant_treatment_3_type, ''),
    i.adjuvant_treatment_4_gap = nullIf(row.adjuvant_treatment_4_gap, ''),
    i.adjuvant_treatment_4_duration_d = nullIf(row.adjuvant_treatment_4_duration_d, ''),
    i.adjuvant_treatment_4_drugs = nullIf(row.adjuvant_treatment_4_drugs, ''),
    i.adjuvant_treatment_4_type = nullIf(row.adjuvant_treatment_4_type, ''),
    i.adjuvant_treatment_5_gap = nullIf(row.adjuvant_treatment_5_gap, ''),
    i.adjuvant_treatment_5_duration_d = nullIf(row.adjuvant_treatment_5_duration_d, ''),
    i.adjuvant_treatment_5_drugs = nullIf(row.adjuvant_treatment_5_drugs, ''),
    i.adjuvant_treatment_5_type = nullIf(row.adjuvant_treatment_5_type, ''),
    i.tumor_average_diameter_cm = nullIf(row.tumor_average_diameter_cm, ''),
    i.experiment_accession = nullIf(row.experiment_accession, ''),
    i.population_type = nullIf(row.population_type, '');

// --- 4. Sample ---
LOAD CSV WITH HEADERS FROM 'file:///entities/sample.csv' AS row
MERGE (s:sample {sample_accession: row.sample_accession})
SET s.project_accession = nullIf(row.project_accession, ''),
    s.individual_accession = nullIf(row.individual_accession, ''),
    s.study_accession = nullIf(row.study_accession, ''),
    s.individual_identifier = nullIf(row.individual_identifier, ''),
    s.gender = nullIf(row.gender, ''),
    s.sample_name = nullIf(row.sample_name, ''),
    s.run_title = nullIf(row.run_title, ''),
    s.platform = nullIf(row.platform, ''),
    s.strategy = nullIf(row.strategy, ''),
    s.sample_description = nullIf(row.sample_description, ''),
    s.run_accession = nullIf(row.run_accession, ''),
    s.experiment_accession = nullIf(row.experiment_accession, ''),
    s.tissue_type = nullIf(row.tissue_type, ''),
    s.specimen_type = nullIf(row.specimen_type, ''),
    s.biospecimen_anatomic_site = nullIf(row.biospecimen_anatomic_site, ''),
    s.tumor_descriptor = nullIf(row.tumor_descriptor, '');

// --- 5. T1 ---
/*======================================================
T1 修复版 (解决 BOM 和 NULL 问题)
======================================================*/
LOAD CSV WITH HEADERS FROM 'file:///entities/T1.csv' AS row
WITH row, coalesce(row.T1_id, row['﻿T1_id']) AS T1_id
WHERE T1_id IS NOT NULL
MERGE (t1:T1 {T1_id: T1_id})
SET
    t1.study_accession = nullIf(row.study_accession, ''),
    t1.individual_accession = nullIf(row.individual_accession, ''),
    t1.individual_name = nullIf(row.individual_name, ''),
    t1.sample_accession = nullIf(row.sample_accession, ''),
    t1.sample_name = nullIf(row.sample_name, ''),
    t1.experiment_accession = nullIf(row.experiment_accession, ''),
    t1.run_accession = nullIf(row.run_accession, ''),
    t1.file_name = nullIf(row.file_name, ''),
    t1.file_path = nullIf(row.file_path, ''),
    t1.file_format = nullIf(row.file_format, ''),
    t1.strategy = nullIf(row.strategy, ''),
    t1.semantic_format = nullIf(row.semantic_format, ''),
    t1.size = nullIf(row.size, ''),
    t1.platform = nullIf(row.platform, ''),
    t1.data_level = nullIf(row.data_level, '');

// --- 6. T2 ---
/*======================================================
T2 修复版 (解决 BOM 和 NULL 问题)
======================================================*/
LOAD CSV WITH HEADERS FROM 'file:///entities/T2.csv' AS row
WITH row, coalesce(row.T2_id, row['﻿T2_id']) AS T2_id
WHERE T2_id IS NOT NULL
MERGE (t2:T2 {T2_id: T2_id})
SET
    t2.study_accession = nullIf(row.study_accession, ''),
    t2.run_accession = nullIf(row.run_accession, ''),
    t2.file_name = nullIf(row.file_name, ''),
    t2.sub_file_name = nullIf(row.sub_file_name, ''),
    t2.file_path = nullIf(row.file_path, ''),
    t2.format = nullIf(row.format, ''),
    t2.semantic_format = nullIf(row.semantic_format, ''),
    t2.size = nullIf(row.size, ''),
    t2.strategy = nullIf(row.strategy, ''),
    t2.data_level = nullIf(row.data_level, '');

// --- 7. Tool ---
LOAD CSV WITH HEADERS FROM 'file:///entities/tool.csv' AS row
WITH row, coalesce(row.tool_id, row['﻿tool_id']) AS tool_id
WHERE tool_id IS NOT NULL
MERGE (t:tool {tool_id: tool_id})
SET t.tool_name = nullIf(row.tool_name, ''),
    t.function = nullIf(row.function, ''),
    t.semantic_input = nullIf(row.semantic_input, ''),
    t.input_format = nullIf(row['输入格式'], ''),
    t.semantic_output = nullIf(row.semantic_output, ''),
    t.output_format = nullIf(row['输出格式'], ''),
    t.next_tool = nullIf(row['下游工具'], ''),
    t.modal = nullIf(row['适用组学'], '');
