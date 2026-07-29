// ======================================================
// 性能优化索引（仅针对非唯一属性）
// 注意：唯一约束已涵盖的属性（如 individual_accession）无需在此重复创建
// ======================================================

// --- 常用名称与描述性属性索引 ---
CREATE INDEX project_name_index IF NOT EXISTS 
FOR (n:Project) ON (n.project_name);

CREATE INDEX tool_name_index IF NOT EXISTS 
FOR (n:Tool) ON (n.tool_name);

// --- 肿瘤类型与部位索引（Individual & Study 中常搜） ---
CREATE INDEX individual_tumor_type_index IF NOT EXISTS 
FOR (n:Individual) ON (n.tumor_type);

CREATE INDEX individual_primary_site_index IF NOT EXISTS 
FOR (n:Individual) ON (n.primary_tumor_site);

CREATE INDEX study_tumor_type_index IF NOT EXISTS 
FOR (n:Study) ON (n.tumor_type);

// --- 策略与平台索引 (T1 & Sample) ---
CREATE INDEX T1_strategy_index IF NOT EXISTS 
FOR (n:T1) ON (n.strategy);

CREATE INDEX T1_platform_index IF NOT EXISTS 
FOR (n:T1) ON (n.platform);

CREATE INDEX sample_type_index IF NOT EXISTS 
FOR (n:Sample) ON (n.sample_type);

// --- T2 路径与策略 ---
CREATE INDEX T2_strategy_index IF NOT EXISTS 
FOR (n:T2) ON (n.strategy);

CREATE INDEX T2_file_path_index IF NOT EXISTS 
FOR (n:T2) ON (n.file_path);