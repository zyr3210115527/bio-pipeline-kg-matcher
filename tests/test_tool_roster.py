"""51 个工具「都接入了吧」——这题的确定性回归。

师兄 0821 问「目前图谱里面 51 个工具都接入了吧」。当时是手工查一遍答的，换一次
图谱就得重查一遍，而且"接入"分好几层、层层数字不一样（目录 51 / 可编排 11 /
有执行合同 12），口头答容易串层。这里把每一层各写成一条断言。

分两段：
- 离线段（不需要图谱）：目录自身一致性、next_tool 本地绑定、执行合同覆盖。
  任何时候都跑，坏了就是仓库里的 CSV/JSON 被改坏了。
- 图谱段（需要 NEO4J_PASSWORD + 可达的图）：目录 ↔ 图谱双向差集、每个工具的四类
  边。图谱不可达时 **skip 并说明原因**，不能静默当通过——0821 就遇到过图谱掉线，
  静默跳过等于把"没验过"记成"验过了"。

用法：
    NEO4J_PASSWORD=... NEO4J_HTTP=http://<host>:<port>/db/neo4j/tx/commit \
        python3 -m unittest tests.test_tool_roster -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tool_catalog_source as tcs  # noqa: E402
import neo4j_observability as obs  # noqa: E402

# 0821 交付口径。改这三个数之前先确认是目录真的变了，而不是 CSV 被改坏了。
EXPECTED_TOTAL = 51
EXPECTED_KINDS = {"atomic": 12, "pipeline": 38, "task_pipeline": 1}

# 图里没有 input 边的工具。multiqc 是收尾 QC 汇聚器，本就不消费分析产物；另外两个
# 是上游导出时漏了 input 边——它们的后果是 `find_tools_by_input_format` 这条模板
# 永远匹配不到它们，只能靠功能名/模态命中。列在这里是为了"已知且被记录"，不是
# "可以接受"：一旦有**新**工具掉进这个集合，断言会失败，不会跟着一起被默许。
KNOWN_TOOLS_WITHOUT_INPUT_EDGE = {"multiqc", "bootstrap_stability", "hvg_pca_gmm"}

NEO4J_HTTP = os.environ.get(
    "NEO4J_HTTP", os.environ.get("NEO4J_URL", "http://127.0.0.1:7474/db/neo4j/tx/commit"))
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
NEO4J_TIMEOUT = os.environ.get("NEO4J_TIMEOUT", "30")


def _http_query(statements):
    """走 HTTP tx/commit，只依赖 curl。

    这里刻意不用 neo4j_observability.Neo4jClient：那条路要 bolt 驱动和 bolt 端口，
    而 0821 现网 bolt 和 HTTP 是两个端口、运维只开了 HTTP 的那次就查不了。回归脚本
    的依赖越少越好。
    """
    payload = json.dumps({"statements": [{"statement": s} for s in statements]})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        handle.write(payload)
        tmp = handle.name
    try:
        proc = subprocess.run(
            ["curl", "-s", "--max-time", NEO4J_TIMEOUT,
             "-u", f"{NEO4J_USER}:{NEO4J_PASSWORD}", "-X", "POST",
             "-H", "Content-Type: application/json", "-d", "@" + tmp, NEO4J_HTTP],
            capture_output=True, text=True)
        if proc.returncode != 0 or not proc.stdout.strip():
            raise ConnectionError(
                f"图谱不可达（curl 退出码 {proc.returncode}，上限 {NEO4J_TIMEOUT}s，"
                f"地址 {NEO4J_HTTP}）")
        body = json.loads(proc.stdout)
        if body.get("errors"):
            raise RuntimeError("; ".join(e.get("message", "") for e in body["errors"])[:400])
        return [[row["row"] for row in res.get("data", [])] for res in body.get("results", [])]
    finally:
        os.unlink(tmp)


def _rows(query, columns):
    return [dict(zip(columns, row)) for row in _http_query([query])[0]]


class ToolRosterOfflineTest(unittest.TestCase):
    """不碰图谱的那一半：仓库自身是否自洽。"""

    @classmethod
    def setUpClass(cls):
        cls.local = tcs.load_local_catalog()
        cls.tools = list(cls.local["tools_by_catalog_id"].values())
        cls.contracts = json.loads(
            (ROOT / "config" / "knowledge_card_execution_contracts.json")
            .read_text(encoding="utf-8"))["tools"]

    def test_catalog_size_and_kinds(self):
        self.assertEqual(len(self.tools), EXPECTED_TOTAL)
        self.assertEqual(dict(Counter(t["tool_kind"] for t in self.tools)), EXPECTED_KINDS)

    def test_tool_ids_and_catalog_ids_are_unique_and_present(self):
        # catalog_id（T001…）是目录与图谱之间唯一的连接键：图里存在 tool.tool_id
        # 上。空值或重复会让 merge_with_graph 把工具静默丢掉或张冠李戴，而不报错。
        tool_ids = [t["tool_id"] for t in self.tools]
        catalog_ids = [t.get("catalog_id") or "" for t in self.tools]
        self.assertEqual(len(set(tool_ids)), EXPECTED_TOTAL, "tool_id 有重复")
        self.assertNotIn("", catalog_ids, "有工具缺 catalog_id")
        self.assertEqual(len(set(catalog_ids)), EXPECTED_TOTAL, "catalog_id 有重复")

    def test_next_bindings_reference_known_tools(self):
        # next_bindings 的键是 (source_catalog_id, target_catalog_id) 二元组。
        known = set(self.local["tools_by_catalog_id"])
        dangling = sorted({cid for pair in self.local["next_bindings"] for cid in pair
                           if cid not in known})
        self.assertEqual(dangling, [],
                         f"tool_relationship.csv 引用了目录里没有的 catalog_id：{dangling}")

    def test_next_topology_covers_only_atomic_layer(self):
        # 这条是防"以为 51 个工具都能沿 next_tool 串链"。业务 pipeline 在 next_tool
        # 上是孤立节点，属设计如此；断言写死是为了它哪天变了能被看见。
        by_cat = self.local["tools_by_catalog_id"]
        involved = {cid for pair in self.local["next_bindings"] for cid in pair}
        self.assertEqual({by_cat[cid]["tool_kind"] for cid in involved}, {"atomic"},
                         "next_tool 上出现了非 atomic 工具")
        names = {by_cat[cid]["tool_id"] for cid in involved}
        self.assertEqual(len(names), 11, f"可编排 atomic 应为 11 个，实为 {len(names)}：{sorted(names)}")
        self.assertEqual(names & tcs.EXCLUDED_TOOL_IDS, set(),
                         "被 EXCLUDED_TOOL_IDS 排除的工具不应出现在编排层")

    def test_execution_contracts_cover_every_atomic_tool(self):
        # 「51 个都能提交执行了吧」的答案在这里：只有 atomic 有卡，39 个 pipeline
        # 级工具无卡，validate_execution_chain 的契约校验阶段对它们直接跳过并告警。
        atomic = {t["tool_id"] for t in self.tools if t["tool_kind"] == "atomic"}
        self.assertEqual(set(self.contracts), atomic,
                         "执行合同应当恰好覆盖 12 个 atomic 工具，不多不少")
        self.assertEqual(len(self.contracts), EXPECTED_KINDS["atomic"])


class ToolRosterGraphTest(unittest.TestCase):
    """需要图谱的那一半。图谱不可达 → skip 并说明，绝不静默当通过。"""

    @classmethod
    def setUpClass(cls):
        if not NEO4J_PASSWORD:
            raise unittest.SkipTest("未设 NEO4J_PASSWORD，跳过图谱侧断言（不等于通过）")
        try:
            _http_query(["RETURN 1"])
        except ConnectionError as exc:
            raise unittest.SkipTest(f"{exc}，跳过图谱侧断言（不等于通过）")
        cls.local = tcs.load_local_catalog()
        cls.graph_tools = _rows(
            obs.TOOL_ROSTER_QUERY,
            ["catalog_id", "tool_name", "semantic_inputs", "semantic_outputs", "modals"])
        cls.graph_next = _rows(
            obs.TOOL_NEXT_QUERY, ["source_catalog_id", "target_catalog_id", "kind"])
        cls.merged = tcs.merge_with_graph(cls.local, cls.graph_tools, cls.graph_next)

    def test_graph_and_catalog_agree_both_ways(self):
        # 「51 个都接入了吧」→ 就是这条。只比数量会被"凑巧相等"骗过去，必须双向差集。
        graph_ids = {t["catalog_id"] for t in self.graph_tools}
        catalog_ids = set(self.local["tools_by_catalog_id"])
        self.assertEqual(len(graph_ids), EXPECTED_TOTAL, "图内 tool 节点数不是 51")
        self.assertEqual(sorted(catalog_ids - graph_ids), [], "目录里有、图里没有的工具")
        self.assertEqual(sorted(graph_ids - catalog_ids), [], "图里有、目录里没有的工具")

    def test_no_divergence_between_graph_and_local_model(self):
        div = self.merged["divergence"]
        for key in ("tools_missing_from_graph", "tools_missing_local_model",
                    "next_missing_local_binding", "next_missing_from_graph"):
            self.assertEqual(div[key], [], f"divergence.{key} 非空：{div[key]}")

    def test_every_tool_has_output_and_modal_edges(self):
        by_id = {t["catalog_id"]: t for t in self.graph_tools}
        cat2id = {cid: t["tool_id"] for cid, t in self.local["tools_by_catalog_id"].items()}
        no_output = sorted(cat2id[c] for c, t in by_id.items()
                           if c in cat2id and not [x for x in t["semantic_outputs"] if x])
        no_modal = sorted(cat2id[c] for c, t in by_id.items()
                          if c in cat2id and not [x for x in t["modals"] if x])
        self.assertEqual(no_output, [], f"这些工具在图里没有 output 边：{no_output}")
        self.assertEqual(no_modal, [], f"这些工具在图里没有 suitable_for 边：{no_modal}")

    def test_tools_without_input_edge_stay_within_known_set(self):
        # 缺 input 边不会报错，只会让「按输入格式找工具」静默漏掉它们。已知的 3 个
        # 记在 KNOWN_TOOLS_WITHOUT_INPUT_EDGE，新增的会让这条失败。
        by_id = {t["catalog_id"]: t for t in self.graph_tools}
        cat2id = {cid: t["tool_id"] for cid, t in self.local["tools_by_catalog_id"].items()}
        missing = {cat2id[c] for c, t in by_id.items()
                   if c in cat2id and not [x for x in t["semantic_inputs"] if x]}
        new = sorted(missing - KNOWN_TOOLS_WITHOUT_INPUT_EDGE)
        fixed = sorted(KNOWN_TOOLS_WITHOUT_INPUT_EDGE - missing)
        self.assertEqual(new, [], f"新出现的缺 input 边工具：{new}")
        self.assertEqual(fixed, [],
                         f"这些工具的 input 边已补上，请从 KNOWN_TOOLS_WITHOUT_INPUT_EDGE 移除：{fixed}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
