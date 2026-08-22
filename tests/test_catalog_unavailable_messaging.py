"""图谱目录为空时，产品不许给出"听起来很合理"的错误解释。

0822 实测到两条这类回答，都不是崩溃，而是自信的胡说：

  1. 校验一条完全合法的原子链 → 「未知 tool_id: star」。
     真相是目录空了，一个工具都不认识，不是这条链写错了。
  2. 问「用 HRA001272 的 RNA-seq 做 GO/KEGG 富集」→
     「差异表达与 GO/KEGG 通路富集这类分析尚未原子化，当前原子目录中没有对应工具」。
     真相同样是目录空了，它根本不知道富集有没有原子化。这条比第 1 条更糟：用户会
     据此认定"产品不支持富集原子化"，而且完全不会想到去查图谱连接。

工具目录只从 Neo4j 来（见 RegisteredMethodCatalog），目录一空，任何"某工具不存在"
"某分析没原子化"的结论都失去前提。这套用例锁的就是这个：**空目录只能说目录空了**。

这里全部用假目录，不连图谱，所以图谱通不通都必须跑过——不加 graph_gate。
"""

import unittest

from workflow_composer import RegisteredMethodCatalog


class _FakeCatalog:
    """只保留 unavailable_state 需要的四个字段。"""

    def __init__(self, all_methods=None, methods=None, connected=False, error=None):
        self.all_methods = all_methods or {}
        self.methods = methods if methods is not None else dict(self.all_methods)
        self.connected = connected
        self.error = error

    unavailable_state = RegisteredMethodCatalog.unavailable_state


class UnavailableStateTests(unittest.TestCase):
    def test_disconnected_graph_names_the_connection(self):
        state = _FakeCatalog(connected=False, error="connection_timeout").unavailable_state()
        self.assertIsNotNone(state)
        self.assertIn("图谱未连接", state)
        self.assertIn("connection_timeout", state)

    def test_connected_but_empty_is_a_different_sentence(self):
        # 连上了却一个工具都没返回，是图谱侧的数据问题，不是网络问题。两者混为一谈
        # 会让人白查一遍 VPN。
        state = _FakeCatalog(connected=True, error=None).unavailable_state()
        self.assertIn("图谱已连接", state)
        self.assertNotIn("未连接", state)

    def test_healthy_catalog_returns_none(self):
        healthy = _FakeCatalog(all_methods={"fastp": object()}, connected=True)
        self.assertIsNone(healthy.unavailable_state())
        self.assertIsNone(healthy.unavailable_state(atomic_only=True))

    def test_atomic_only_distinguishes_empty_atomic_layer(self):
        # pipeline 节点在、原子层空：说"拆不成原子链"依然没有依据。
        catalog = _FakeCatalog(
            all_methods={"rnaseq_singletask": object()}, methods={}, connected=True
        )
        self.assertIsNone(catalog.unavailable_state())
        atomic = catalog.unavailable_state(atomic_only=True)
        self.assertIsNotNone(atomic)
        self.assertIn("原子", atomic)


class MessagesNeverBlameTheCallerTests(unittest.TestCase):
    """三个出口共用一句话，任何一处绕过 unavailable_state 都会在这里露出来。"""

    def setUp(self):
        self.empty = _FakeCatalog(connected=False, error="connection_timeout")

    def test_validate_custom_steps_says_catalog_not_unknown_tool(self):
        import workflow_composer

        composer = workflow_composer.WorkflowComposer.__new__(
            workflow_composer.WorkflowComposer
        )
        composer.registered_methods = self.empty
        methods, validation = composer._validate_custom_steps([
            {"step_id": "star", "tool_id": "star", "inputs": {}},
        ])
        self.assertEqual(methods, [])
        self.assertFalse(validation["ok"])
        self.assertTrue(validation["catalog_unavailable"])
        joined = " ".join(validation["errors"])
        self.assertIn("工具目录为空", joined)
        self.assertIn("图谱未连接", joined)
        # 这才是这条用例的重点：不能再把锅甩给调用方的 tool_id。
        self.assertNotIn("未知 tool_id", joined)

    def test_server_note_is_empty_when_catalog_is_healthy(self):
        import server

        healthy = _FakeCatalog(all_methods={"fastp": object()}, connected=True)
        composer = type("C", (), {"registered_methods": healthy})()
        # 目录正常时必须一个字都不加，否则每条正常报错后面都挂一句无关的图谱提示。
        self.assertEqual(server._catalog_unavailable_note(composer), "")

    def test_server_note_fires_when_catalog_is_empty(self):
        import server

        composer = type("C", (), {"registered_methods": self.empty})()
        note = server._catalog_unavailable_note(composer)
        self.assertIn("工具目录为空", note)
        self.assertIn("connection_timeout", note)


if __name__ == "__main__":
    unittest.main()
