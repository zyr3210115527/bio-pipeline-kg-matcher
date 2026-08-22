"""T2 资产的样本归属——在**连着图谱**的前提下验。

师兄 0821 提的问题：富集分析那批数据的样本信息是 null。他的原话是"图谱里是有
sample 样本的，这个文件他对应的是 study 数据，要输入 run 和 sample 编号就需要再
从 study 下面对应到 individual 对应到 sample-run"。据此实现了四级阶梯。

但那套阶梯此前**只在 CSV 模式下跑过**。0822 接上图谱当天，neo4j 模式（也就是
生产模式）凡是要返回 T2 资产的查询全部崩在
`AttributeError: 'Neo4jKGDataMatcher' object has no attribute '_attribution_index'`
——143 条单测炸了 114 条。根因是 `Neo4jKGDataMatcher.__init__` 从头重写、不调
`super().__init__()`，父类后来加的懒加载哨兵没被镜像过来；而且哨兵就算补上，
`_attribution_indexes()` 里两处 `_read_csv(self.relation_dir / ...)` 在 neo4j 模式
下要么继续崩、要么去读 0812 的旧 CSV，让血缘和资产悄悄来自两个数据源。

所以这里锁三件事，第三件最要紧：

1. 两张关系表在图里取得到，不是空的；
2. 没有任何 T2 资产的归属是 null；
3. **绝大多数走的是真血缘边，而不是 study 兜底。**

第 3 条才是这个文件存在的理由。前两条在 `_attribution_relation_rows` 悄悄返回 []
时**照样全绿**：血缘表一空，每个资产都会稳稳落到 study_cohort 兜底那一级，回包
字段完整、samples 非空、一个 null 都没有——看上去完全正常，实际上把"这个文件出自
HRS039792 这一个样本"换成了"它属于这个队列里的 878 个样本之一"。错得像对的。
"""

import os
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _matcher():
    """连不上就 skip，并说清跳过不等于通过。"""
    if os.environ.get("DATA_MATCHER_MODE", "").strip().lower() != "neo4j":
        raise unittest.SkipTest(
            "本套件专测 neo4j 后端的归属实现；当前不是 neo4j 模式。"
            "CSV 模式下这条路径是另一套代码，跳过**不等于**neo4j 侧通过。"
        )
    try:
        from data_matcher.neo4j_matcher import Neo4jKGDataMatcher

        return Neo4jKGDataMatcher()
    except Exception as exc:  # noqa: BLE001
        raise unittest.SkipTest(
            f"图谱不可达（{type(exc).__name__}: {exc}）；"
            f"地址 {os.environ.get('NEO4J_URI', '(未设)')}。"
            "跳过**不等于**通过，图谱恢复后必须重跑。"
        )


class AttributionOnGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = _matcher()
        cls.levels = Counter()
        cls.vias = Counter()
        cls.unresolved = []
        for row in cls.matcher.t2:
            resolved = cls.matcher._resolve_attribution(
                row, row.get("file_name") or row.get("t2_id")
            )
            level = (resolved or {}).get("level")
            cls.levels[str(level)] += 1
            cls.vias[str((resolved or {}).get("via"))] += 1
            if not level or not (resolved or {}).get("samples"):
                if len(cls.unresolved) < 5:
                    cls.unresolved.append((row.get("t2_id"), resolved))

    @classmethod
    def tearDownClass(cls):
        matcher = getattr(cls, "matcher", None)
        if matcher is not None:
            matcher.close()

    def test_both_relation_tables_come_back_non_empty(self):
        # 直接查这个接缝：它是 CSV/Neo4j 两个后端唯一的分岔点，也是最容易悄悄空掉的地方。
        for name in ("T1_in_sample", "T2_generated_from_T1"):
            with self.subTest(relation=name):
                rows = self.matcher._attribution_relation_rows(name)
                self.assertTrue(
                    rows,
                    f"{name} 在图里取到 0 行。归属会整体退化成 study 兜底而**不报错**，"
                    "回包看着依旧完整。检查这条边的类型名和标签大小写是否变了。",
                )

    def test_no_t2_asset_is_left_unattributed(self):
        # 师兄原始诉求：不许再出现 null。
        self.assertEqual(
            self.unresolved,
            [],
            f"仍有 T2 资产解析不出样本归属（样例见上）。四级阶梯共覆盖 {self.levels}",
        )

    def test_real_lineage_edge_carries_the_majority(self):
        """兜底可以有，但不能变成主路径。

        注意断言的是 `via` 而不是 `level`。第一版写成 `level == "sample"`，把关系表
        清空做变异测试时**这条没挂**——因为第 2 层"文件名里的 HRR 号"同样报
        level=sample，24,722 个文件从 lineage_edge 悄悄挪到 filename_run，分级统计
        纹丝不动。真正被换掉的是依据：图谱声明的血缘事实换成了文件命名约定的推断。
        """
        total = sum(self.vias.values())
        self.assertTrue(total, "图里一条 T2 都没有，前提就不成立")
        by_lineage = self.vias.get("lineage_edge", 0)
        # 0822 实测 24,725/35,572 ≈ 69.5% 走真血缘边。定在 50% 给数据变动留余量，
        # 同时能抓住"关系表空了"这个形状——那时 lineage_edge 会直接掉到 0。
        self.assertGreater(
            by_lineage / total,
            0.5,
            f"只有 {by_lineage}/{total} 走真血缘边（T2-generated_from->T1-in_sample->sample）。"
            f"各依据分布：{dict(self.vias)}。这通常意味着关系表没取到，而不是数据本身变了。",
        )

    def test_lineage_edge_and_filename_agree_where_both_apply(self):
        """血缘边和文件名推断在重叠案例上必须给同一个答案。

        `_resolve_attribution` 的注释写着两者"在 24,318 个重叠案例上零冲突"，但那是
        0821 在 CSV 上量的。0822 换成图谱后血缘来自 Cypher、文件名来自 T2 自身属性，
        两个来源第一次分开了——冲突率正是"我从图里取错了边"最直接的信号。

        顺带也是一条数据质量检查：真出现分歧，要么边接错，要么命名约定不再可信。
        """
        indexes = self.matcher._attribution_indexes()
        by_run = indexes["by_run"]
        compared = conflicts = 0
        examples = []
        for row in self.matcher.t2:
            lineage = indexes["lineage"].get(str(row.get("t2_id") or "").strip())
            if not lineage:
                continue
            run = str(row.get("run_accession") or "").strip()
            if not run or run not in by_run:
                continue
            from_name = str(by_run[run].get("sample_accession") or "").strip()
            if not from_name:
                continue
            compared += 1
            if from_name not in lineage:
                conflicts += 1
                if len(examples) < 5:
                    examples.append((row.get("t2_id"), run, from_name, lineage[:3]))
        self.assertTrue(compared, "没有任何案例同时具备血缘边和可用的 run 号，无从比对")
        self.assertEqual(
            conflicts,
            0,
            f"{conflicts}/{compared} 个案例上，血缘边指向的样本和 run 号指向的样本不一致。"
            f"样例 (t2_id, run, 文件名推断, 血缘边)：{examples}",
        )

    def test_sample_level_attribution_is_specific_not_a_whole_cohort(self):
        """真血缘那一级必须指向少数几个样本，不能是整队列。"""
        checked = 0
        for row in self.matcher.t2:
            resolved = self.matcher._resolve_attribution(
                row, row.get("file_name") or row.get("t2_id")
            )
            if (resolved or {}).get("level") != "sample":
                continue
            self.assertLessEqual(
                len(resolved["samples"]),
                8,
                f"标称 level=sample 却挂了 {len(resolved['samples'])} 个样本："
                f"{row.get('t2_id')}。这是把队列级结论贴上了样本级标签。",
            )
            checked += 1
            if checked >= 200:
                break
        self.assertTrue(checked, "没有任何 level=sample 的资产可供抽查")

    def test_attribution_does_not_silently_fall_back_to_csv_files(self):
        """neo4j 后端不许去读磁盘上的 CSV——那会让血缘和资产来自两个数据源。"""
        self.assertFalse(
            hasattr(self.matcher, "relation_dir"),
            "Neo4jKGDataMatcher 上出现了 relation_dir。如果是为了让 _attribution_indexes() "
            "不崩而加的，那等于用 0812 的旧 CSV 解释 0822 图谱里的资产，两边对不上还看不出来。",
        )


if __name__ == "__main__":
    unittest.main()
