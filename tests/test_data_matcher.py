import json
import tempfile
import unittest
from pathlib import Path

from data_matcher.comparison import compare_results, load_allowlist
from data_matcher.dual_read import DualReadDataMatcher


class StubMatcher:
    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error

    def match(self, _intent, _pipelines, limit=10):
        if self.error:
            raise self.error
        return self.result


class DataMatcherComparisonTests(unittest.TestCase):
    def test_normalizes_empty_values_and_legacy_size_suffix(self):
        csv = {
            "data_schema": "normalized-v2",
            "cohort_candidates": [],
            "file_candidates": [{"source": "T1", "study_accession": "S", "run_accession": "R", "read_pair": "R1", "files": "x.fq.gz (12 bytes)", "strategy": ""}],
            "backup_file_candidates": [],
            "data_combinations": [],
            "query_constraints": {},
        }
        neo = json.loads(json.dumps(csv))
        neo["file_candidates"][0]["files"] = "x.fq.gz"
        neo["file_candidates"][0]["strategy"] = None
        report = compare_results("case", {}, [], csv, neo)
        self.assertEqual(report["material_diff_count"], 0)

    def test_detects_rank_and_field_differences(self):
        def result(values):
            return {
                "data_schema": "normalized-v2",
                "cohort_candidates": values,
                "file_candidates": [],
                "backup_file_candidates": [],
                "data_combinations": [],
                "query_constraints": {},
            }

        csv = result([{"study_accession": "A", "title": "a"}, {"study_accession": "B", "title": "b"}])
        neo = result([{"study_accession": "B", "title": "changed"}, {"study_accession": "A", "title": "a"}])
        report = compare_results("case", {}, [], csv, neo)
        section = report["sections"]["cohort_candidates"]
        self.assertEqual(len(section["field_diffs"]), 1)
        self.assertEqual(len(section["rank_diffs"]), 2)
        self.assertEqual(report["material_diff_count"], 3)

    def test_allowlist_requires_reason_and_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allowlist.json"
            path.write_text(json.dumps({"rules": [{"id": "bad"}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_allowlist(path)

    def test_compare_mode_returns_csv_when_neo4j_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "diff.jsonl"
            csv_result = {"cohort_candidates": []}
            matcher = DualReadDataMatcher(
                StubMatcher(result=csv_result),
                StubMatcher(error=RuntimeError("offline")),
                output,
            )
            self.assertIs(matcher.match({}, []), csv_result)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["neo4j_error"]["type"], "RuntimeError")
            self.assertEqual(report["material_diff_count"], 1)


if __name__ == "__main__":
    unittest.main()
