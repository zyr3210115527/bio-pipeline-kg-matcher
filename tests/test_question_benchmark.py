import os
import unittest

from question_benchmark import load_question_benchmark
from workflow_composer import WorkflowComposer
from tests.graph_gate import require_graph_catalog


class QuestionBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_force_rule = os.environ.get("FORCE_RULE")
        os.environ["FORCE_RULE"] = "1"
        require_graph_catalog()
        cls.composer = WorkflowComposer()

    @classmethod
    def tearDownClass(cls):
        if cls.previous_force_rule is None:
            os.environ.pop("FORCE_RULE", None)
        else:
            os.environ["FORCE_RULE"] = cls.previous_force_rule

    def test_all_96_questions_return_reviewed_pipeline_and_data_names(self):
        cases = load_question_benchmark()["cases"]
        self.assertEqual(len(cases), 96)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                result = self.composer.plan(case["query"])
                self.assertEqual(result["recommendation_count"], 1)
                recommendation = result["recommendations"][0]
                self.assertEqual(
                    recommendation["pipeline_id"], case["expected_pipeline_id"]
                )
                self.assertEqual(
                    [item["name"] for item in recommendation["data"]["assets"]],
                    case["expected_data"],
                )

    def test_every_benchmark_pipeline_is_registered_in_neo4j(self):
        # cellranger_workflow (T003) and wes_somatic_pair (T064) were the last two
        # gaps; the 0811 tool table registers both, so no benchmark case may fall
        # back to missing_from_neo4j any more.
        for case in load_question_benchmark()["cases"]:
            result = self.composer.plan(case["query"])
            recommendation = result["recommendations"][0]
            self.assertEqual(
                recommendation["tool"]["catalog_status"], "registered", case["case_id"]
            )

    def test_available_assets_never_mix_studies(self):
        for case in load_question_benchmark()["cases"]:
            data = self.composer.plan(case["query"])["recommendations"][0]["data"]
            available = [
                item for item in data["assets"]
                if item["graph_status"] == "available"
            ]
            studies = {item.get("study_accession") for item in available}
            studies.discard(None)
            self.assertLessEqual(len(studies), 1, case["case_id"])

    def test_missing_graph_assets_have_no_fake_path(self):
        for case in load_question_benchmark()["cases"]:
            data = self.composer.plan(case["query"])["recommendations"][0]["data"]
            for asset in data["assets"]:
                if asset["graph_status"] == "missing_from_graph":
                    self.assertNotIn("file_path", asset)

    def test_hra001272_pairing_uses_four_reviewed_fastqs(self):
        case = next(
            item for item in load_question_benchmark()["cases"]
            if item["expected_pipeline_id"] == "wes_somatic_pair"
        )
        data = self.composer.plan(case["query"])["recommendations"][0]["data"]
        self.assertEqual(data["status"], "available")
        self.assertEqual(data["matched_count"], 4)
        self.assertEqual(data["study_accessions"], ["HRA001272"])


if __name__ == "__main__":
    unittest.main()
