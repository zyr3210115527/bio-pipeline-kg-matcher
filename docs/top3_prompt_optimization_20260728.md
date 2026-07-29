# Top-3 提示词异常结果复测与优化

## 测试基线

本轮忽略 7.28 新数据包，使用此前稳定的只读图：

```text
NEO4J_URI=bolt://127.0.0.1:7688
NEO4J_DATABASE=datagraph-staging
```

该图包含 24 个工具、28 条 NEXT 和 7 条 HAS_STEP，`fastp` 保留 `raw_fastq_read_r1/r2` 槽位。当前 `.env.local` 指向的 7687 只有 14 条 NEXT，且 `fastp` 只有旧的 `raw_fastq_read` 单槽，因此不能与此前稳定基线混用。

稳定图上共发现 89 项测试：86 passed，3 个真实集成测试按开关跳过；没有写入 7687 或 7688。

## 基线发现的异常

1. 双端 FASTQ 只做 FastQC 时，模型生成两个并行 FastQC 根步骤，随后被校验器拒绝。
2. “MAF 用 STAR 生成 count”没有生成原子链，但错误推荐了多个 MAF 分析流程。
3. 普通一对双端 FASTQ 被擅自解释为 tumor/normal，并推荐 `wes_somatic_pair`。
4. 明确的 bulk RNA-seq + BWA DNA 体细胞分析请求被错误推荐为 WES 配对流程。
5. 配对 WES 到注释 VCF 时，模型生成了当前 Knowledge Card 合同必然拒绝的 GATK/BCFtools/SnpEff 链。
6. TPM/FPKM 用例的 Top1 正确，但曾额外生成非法 `FastQC -> STAR` 备选。

## 提示词修改

- recommendations 必须同时匹配输入类型、样本布局、最终产物和显式排除条件；只覆盖部分目标的流程不能推荐。
- 将“只要、不要、不做、不能修改、已有、只有”定义为硬约束。
- 禁止从普通一对 FASTQ 推断 tumor/normal；必须有明确角色才能使用配对 WES。
- 增加 assay 冲突检查，例如 MAF 不能做 STAR，RNA-seq 不能用 DNA 体细胞流程兜底。
- 增加最终产物完整性门禁，不能用上游前缀链冒充完整目标。
- 增加当前执行合同的强制短路：GATK 后需要 BCFtools/SnpEff 时不生成原子候选。
- 明确 FastQC 双端槽位限制，禁止只取一个 mate 或生成非法双根。
- 明确 MultiQC 和 `depends_on` 必须遵守实际 NEXT。
- 显式禁止 `FastQC -> STAR`，FastQC 报告不能作为 STAR reads 输入。
- 没有原子候选时要求给出具体原因；后端额外保留 `atomic_candidate_unavailable_reason`。

后端 `_validate_custom_steps` 的严格性没有放宽，错误链仍然失败闭合。

## 最终严格复测

严格评分把任何 rejected candidate 都视为失败。

| 场景 | 最终结果 |
|---|---|
| 双端 FASTQ 只做 FastQC | `unsupported`，没有错误链或过宽流程推荐 |
| RNA-seq 只要 raw count | `fastp -> STAR -> SAMtools -> featureCounts -> MultiQC` |
| RNA-seq 只要 TPM/FPKM | `fastp -> STAR -> RSEM`，可选合法 MultiQC 版本 |
| 已有 count 做 WGCNA | 返回 `wgcna` 业务流程和数据 |
| 10x FASTQ 做 Cell Ranger | 返回 `cellranger_workflow` 业务流程和数据 |
| 配对 WES 到注释 VCF | 返回 `wes_somatic_pair` 信息，不生成合同必然失败的原子链 |
| MAF 做 STAR/count | `unsupported`，不再推荐无关 MAF 流程 |
| 双端 FASTQ 只做不修改 reads 的 QC | `unsupported`，明确 FastQC 双端槽位缺口 |
| 双端 FASTQ 到 uBAM | 返回 `paired_fastq_to_unmapped_bam` 流程和数据 |
| FASTQ 上游后继续 WGCNA | `unsupported`，不返回只覆盖前半段或后半段的流程 |
| 普通一对 FASTQ 到 MAF | `unsupported`，不脑补 tumor/normal |
| bulk RNA-seq 强行 BWA 体细胞分析 | `unsupported`，明确 assay 冲突 |

最终结果：12/12 通过；rejected candidate 总数为 0。配对 WES 强制短路另做 3 次重复测试，3/3 稳定通过。

## 仍需后端补齐的能力

以下内容不能靠提示词修复：

- FastQC 缺少 paired-end R1/R2 输入槽，因此“只做双端 FastQC”目前只能诚实返回不支持。
- GATK 到 BCFtools 的 VCF/index Knowledge Card 契约不闭合，因此过滤、标准化、SnpEff 注释链不能作为原子候选。
- 单样本 GATK 目录槽与外部 Knowledge Card 合同不一致。
- WGCNA、Cell Ranger、uBAM 等业务流程尚未全部拆成可校验的 atomic chain。
- 当前 7687 与稳定 7688 目录不一致；正式运行前必须明确以哪个图为准。

## 证据文件

- `docs/top3_prompt_quality_before.json`
- `docs/top3_prompt_quality_final_strict.json`
- `docs/top3_prompt_quality_paired_wes_after_hard_stop.json`
- `docs/top3_prompt_quality_abundance_after_fastqc_fix.json`
