import inspect
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow_composer import WorkflowComposer
from tests.graph_gate import require_graph_catalog


class Top3ContractTests(unittest.TestCase):
    def setUp(self):
        self.previous_force_rule = os.environ.get("FORCE_RULE")
        os.environ["FORCE_RULE"] = "1"
        require_graph_catalog()
        self.composer = WorkflowComposer()

    def tearDown(self):
        if self.previous_force_rule is None:
            os.environ.pop("FORCE_RULE", None)
        else:
            os.environ["FORCE_RULE"] = self.previous_force_rule

    def test_plan_signature_has_no_standard_compatibility_switches(self):
        parameters = inspect.signature(self.composer.plan).parameters
        self.assertEqual(list(parameters), ["nl_text", "top_k"])
        self.assertNotIn("force_custom", parameters)
        self.assertNotIn("expand_standard_steps", parameters)

    def test_atomic_menu_excludes_multiqc_and_has_no_pipeline_nodes(self):
        # multiqc has zero NEXT edges in the live graph, so it can never be a
        # legal link in any atomic chain. PR #9 deliberately drops it from the
        # menu advertised to the LLM; the rest of the atomic methods stay.
        lines = self.composer._method_menu_lines()
        self.assertFalse(any(line.startswith("- multiqc ") for line in lines))
        ids = {line.split(" | ", 1)[0].removeprefix("- ") for line in lines}
        self.assertEqual(
            ids, set(self.composer.registered_methods.methods) - {"multiqc"}
        )
        self.assertFalse(ids & set(self.composer.registered_methods.pipeline_methods))

    def test_capability_query_uses_v2_information_contract(self):
        result = self.composer.plan("有哪些原子工具")
        self.assertEqual(result["schema_version"], "tool-chain/v2")
        self.assertEqual(result["selection_status"], "information")
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["candidates"], [])
        self.assertIsNone(result["unsupported_reason"])
        self.assertNotIn("agent_input", result)

    def test_unatomized_request_is_explicitly_unsupported(self):
        decision = {
            "analysis": {},
            "candidates": [],
            "unsupported_reason": "差异表达与 GO 富集尚未原子化，暂不支持。",
        }
        result = self.composer._top3_plan(
            "做差异表达和 GO 富集",
            decision,
            {"used": True, "status": "ok", "calls": 1, "model": "test"},
            3,
        )
        self.assertEqual(result["schema_version"], "tool-chain/v2")
        self.assertEqual(result["selection_status"], "unsupported")
        self.assertEqual(result["candidate_count"], 0)
        self.assertIn("尚未原子化", result["unsupported_reason"])


if __name__ == "__main__":
    unittest.main()
