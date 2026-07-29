# Fix B: Standard Expansion and MultiQC

## Outcome

Standard requests now default to atomic expansion when the selected pipeline has a registered `HAS_STEP` recipe. `rnaseq_singletask` returns `fastqc, trim_galore, star, rsem, samtools, featurecounts, multiqc`; bindings are built from registered data edges, ordering comes from the locked recipe, and the generated method form passes the unchanged `_validate_custom_steps` rules.

`expand_standard_steps=false` preserves the legacy single pipeline-node tool chain. The 11 pipelines without `HAS_STEP` remain single nodes and now carry `decomposition_status=pipeline_level_unexpanded` and `expandable=false`. No internal steps were invented.

The eight restored CSV relationships are order-only edges from `fastp`, `fastqc`, `samtools`, `gatk`, `snpeff`, `star`, `rsem`, and `featurecounts` to `multiqc`. Staging now has 22 NEXT relationships, up from 14.

## Stage-Two Prompt Change

The obsolete first block was removed verbatim:

```text
### MultiQC 与参考流程

MultiQC 由执行端在流程结束时无条件运行,不需要编排。
**不要在 steps 里生成 multiqc 步骤**,也不要为它建立任何 from 或 depends_on。
如果参考流程的步骤列表里出现 multiqc,直接跳过它,这不算"改动了其他步骤"。
最终产物中的 MultiQC 报告由执行端自动产出,你只需组出到目标产物的主链。
```

The redundant final exclusion block was also removed verbatim:

```text
## MultiQC 说明

MultiQC 不在上方原子工具菜单中。它是执行端在流程结束时**无条件运行**的汇总步骤,
只聚合日志和报告,不接收主数据流(BAM/VCF/表达矩阵)。因此:

- 你**不需要**在 steps 里包含 multiqc;
- 不要把任何主数据输出当作 multiqc 的输入;
- 下游汇总报告由执行端自动产出,你只需组出到目标产物的主链。
```

After deletion, the prompt moves directly from the reference-recipe retention rules to `常见错误`, and from the ten-item submission check to `Neo4j atomic 方法目录`. MultiQC is present in that menu, and reference recipes are no longer filtered. The existing safety rule remains: MultiQC is connected by `depends_on` and must not consume BAM, VCF, expression matrices, or other main data artifacts.

## Verification

| Gate | Result |
|---|---|
| CSV validation | Passed |
| Staging NEXT | 22 total, 8 incoming to MultiQC, all restored rows are `kind=order` |
| RNA-seq expansion | 7 steps; registered inputs/from/depends_on; recipe validation OK |
| Asset equivalence | Expanded and legacy forms reference the same two matched FASTQ asset IDs |
| Undecomposed pipelines | 11 single-node results with explicit marker; no invented steps |
| Legacy switch | Exact former pipeline-node shape |
| Full suite | 76 tests OK, including all original 68; 3 existing real integrations skipped |

The behavior change is intentional: stage two can now select MultiQC and a standard RNA-seq chain explicitly includes it. It still cannot attach arbitrary main-data `from` bindings because the restored relationships are order edges and the unchanged validator requires a registered data four-tuple for `from`.
