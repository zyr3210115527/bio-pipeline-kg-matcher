# Demo Day Runbook

## 1. 启动前 5 分钟

### 1.1 切到仓库目录并激活环境
```bash
cd /Users/zhouyiran/Documents/可选/bio-pipeline-kg-matcher
source .venv/bin/activate
```

### 1.2 运行预检脚本
```bash
.venv/bin/python scripts/python/demo_preflight.py
```

期望输出：7 项全 ✅。任何 ❌ 按脚本提示修复。

### 1.3 确认 LLM 可用
```bash
curl -s https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $LLM_API_KEY" | head -c 200
```

如果网络不稳，建议直接切回放模式（见第 5 节）。

---

## 2. 启动服务

```bash
.venv/bin/python app.py
```

默认监听 `http://localhost:8000`。  
浏览器打开 `http://localhost:8000`。

---

## 3. 推荐演示顺序与讲稿

| 顺序 | 查询 | 预期模式 | 一句话讲解 |
|---|---|---|---|
| 1 | 有哪些流程可以处理 MAF 文件 | capability | “先看目录能力，系统能诚实列出支持 MAF 的流程。” |
| 2 | 我有双端 FASTQ 想做 RNA-seq 上游分析，需要表达矩阵和基因计数 | standard/ready | “标准预制菜：直接命中 Neo4j 锁定的 RNA-seq 上游 recipe。” |
| 3 | RNA-seq 上游流程里把 trim_galore 换成 fastp，其他不变 | custom/draft | “自助餐：在原子工具闭集中替换一步，其余步骤原样保留。” |
| 4 | 想同时做 GO 和 KEGG 富集 | standard/ready | “组合两个标准 pipeline，系统自动打包。” |
| 5 | 我有 TPM 矩阵想做无监督聚类 | standard/missing_assets | “需求明确，但库里没有符合 assay 的 TPM 矩阵，系统报 missing_assets 而不是硬凑。” |
| 6 | 我有一个样本的 WES FASTQ，想做变异检测和注释 | custom/draft | “单样本 WES 可以原子化组链到 snpeff。” |
| 7 | 我有肿瘤和正常配对的 WES FASTQ，想做体细胞变异检测并注释 | custom/blocked | “系统知道自己做不到：gatk 只有一个 BAM 槽，无法表达 tumor/normal 汇合。” |

### 重点展开
- **查询 7**：点开“无法组链的原因”，解释 `gatk` 只有一个 `sorted_dedup_bam` 输入槽，所以无法同时接收 tumor 和 normal。
- **查询 3**：展开“LLM 推理过程”，说明系统如何以参考流程为基线、只改用户要求的那一步。
- **任意 standard 查询**：展开“预制菜适配判断”，展示 input/functional/output 三项评估。

---

## 4. 强制 custom 模式开关

界面输入框下方有 checkbox：
- **勾选**：跳过 stage-one 标准流程选择，直接进入 custom 组链。
- **不勾**：正常两阶段。

演示时通常不勾选；只有想展示“从零组链”时才勾选。

---

## 5. 离线回放模式（现场保险丝）

如果 LLM 现场不可用或超时：

```bash
# 终止当前 app.py，然后
DEMO_REPLAY=1 LLM_API_KEY=invalid LLM_BASE_URL=https://invalid.local .venv/bin/python app.py
```

浏览器刷新后，7 条查询会命中 `demo/cassettes/` 里的磁带，不再发网络请求。

验证命令：
```bash
DEMO_REPLAY=1 LLM_API_KEY=invalid LLM_BASE_URL=https://invalid.local .venv/bin/python scripts/a4_verify_replay.py
```

---

## 6. 不要现场点的查询

见 `docs/demo_readiness_full.md` D10 节。核心：
- 不要点 hello / 你好 / “我有数据” / 超长输入。
- 不要点任何依赖 `HRA000071` 的 WES 查询（元数据自相矛盾）。
- 不要点 MAF/TMB/生存分析相关查询（T2 format 错标导致假阳性）。

---

## 7. 常见问题应对

**Q：为什么选了这个 study？**  
A：当前排序由 feasibility（数据角色 + assay 匹配）和文件数量决定。注意：演示前建议移除 `_preferred_study_bonus` 硬编码加分，否则无法解释。

**Q：为什么这条 blocked？**  
A：点开“无法组链的原因”面板，读 LLM 生成的 `decomposition_gaps`。

**Q：能不能换成 DESeq2 / CNV / 单细胞轨迹？**  
A：当前原子工具目录里没有这些工具，系统会返回明确的 gap。

**Q：LLM 状态为什么是红色警告？**  
A：说明 LLM 没成功调用，结果是规则兜底。切回放模式或检查 LLM 配置。

---

## 8. 故障排查速查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 页面空白 | Vue/Element Plus CDN 加载失败 | 检查网络，或本地缓存 CDN 资源 |
| 所有查询返回 no_match | Neo4j 未连接 | 运行预检脚本，检查 `.env.local` |
| custom 查询特别慢 | 两次 LLM 调用 | 正常 30-60s；超时则切回放 |
| 查询 7 没有 decomposition_gaps | cassette 旧或 LLM 未返回 | 用 `DEMO_REPLAY=1` 验证，必要时重录 |
| 文件卡片没有 sample_role | 该 study 未登记角色规则 | 正常现象；有规则时会显示 tumor/normal |

---

## 9. 回滚清单

如果改动导致异常：
- 离线回放：`DEMO_REPLAY=1` 启动即可。
- 排序加分：把 `pipeline_router.py:805-817` 改为 `return 0`。
- Neo4j 边集：CSV 未改，无需回滚。
