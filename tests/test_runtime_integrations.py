import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT))

from data_matcher.expectations import load_expectations  # noqa: E402
from neo4j_observability import Neo4jClient  # noqa: E402
from runtime_config import get_llm_health, initialize_runtime  # noqa: E402


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def single(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class FakeSession:
    def __init__(self, evidence_rows=None):
        self.evidence_rows = evidence_rows or []
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def run(self, query, **parameters):
        text = str(query)
        self.queries.append((text, parameters))
        if "dbms.components" in text:
            return FakeResult([{"version": "2026.06.0"}])
        if "count(n) AS node_count" in text:
            return FakeResult([{"node_count": 42}])
        if "relationship_count" in text:
            return FakeResult([{"relationship_count": 84}])
        if "UNWIND labels(n)" in text:
            return FakeResult([{"label": "Tool", "count": 11}, {"label": "InputSlot", "count": 31}])
        if "UNWIND $tool_ids" in text:
            return FakeResult(self.evidence_rows)
        raise AssertionError(f"Unexpected query: {text}")


class FakeDriver:
    def __init__(self, session, connectivity_error=None):
        self.fake_session = session
        self.connectivity_error = connectivity_error
        self.verify_calls = 0
        self.session_calls = []
        self.closed = False

    def verify_connectivity(self):
        self.verify_calls += 1
        if self.connectivity_error:
            raise self.connectivity_error

    def session(self, **kwargs):
        self.session_calls.append(kwargs)
        return self.fake_session

    def close(self):
        self.closed = True


class RuntimeConfigTests(unittest.TestCase):
    def test_explicit_environment_wins_over_dotenv_and_defaults_fill_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env.local"
            env_file.write_text(
                "LLM_MODEL=from-file\nLLM_API_KEY='local-secret'\n",
                encoding="utf-8",
            )
            env = {"LLM_MODEL": "explicit-model"}
            initialize_runtime(path=env_file, environ=env)
        self.assertEqual(env["LLM_MODEL"], "explicit-model")
        self.assertEqual(env["LLM_API_KEY"], "local-secret")
        self.assertEqual(env["LLM_BASE_URL"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(env["LLM_MODEL"], "explicit-model")
        self.assertEqual(env["LLM_THINKING"], "enabled")

    def test_health_exposes_host_and_configuration_state_not_secret(self):
        env = {
            "LLM_API_KEY": "do-not-return-this",
            "LLM_BASE_URL": "https://llm-center.modelbest.cn/llm/v1/chat/completions",
            "LLM_MODEL": "gpt-5.6-sol",
            "FORCE_RULE": "0",
        }
        health = get_llm_health(env)
        self.assertEqual(health["endpoint_host"], "llm-center.modelbest.cn")
        self.assertTrue(health["configured"])
        self.assertNotIn("do-not-return-this", json.dumps(health))

    def test_llm_logs_never_include_key_or_endpoint_path(self):
        from intent import _call_llm

        class Response:
            status_code = 401

        secret = "local-test-secret-that-must-not-be-logged"
        env = {
            "LLM_MODE": "api",
            "LLM_API_KEY": secret,
            "LLM_BASE_URL": "https://llm-center.modelbest.cn/llm/v1/chat/completions",
            "LLM_MODEL": "gpt-5.6-sol",
            "LLM_TIMEOUT": "60",
        }
        stream = io.StringIO()
        with patch.dict(os.environ, env, clear=True), patch(
            "intent.requests.post", return_value=Response()
        ), redirect_stderr(stream):
            self.assertIsNone(_call_llm("system", "user"))
        logs = stream.getvalue()
        self.assertIn("llm-center.modelbest.cn", logs)
        self.assertNotIn(secret, logs)
        self.assertNotIn("/llm/v1/chat/completions", logs)

    def test_llm_model_metadata_is_present_without_usage_block(self):
        from intent import _call_llm

        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "model": "gpt-5.6-sol",
                    "choices": [{"message": {"content": '{"mode":"standard"}'}}],
                }

        env = {
            "LLM_MODE": "api",
            "LLM_API_KEY": "local-test-value",
            "LLM_BASE_URL": "https://llm-center.modelbest.cn/llm/v1/chat/completions",
            "LLM_MODEL": "gpt-5.6-sol",
            "LLM_TIMEOUT": "60",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "intent.requests.post", return_value=Response()
        ), redirect_stderr(io.StringIO()):
            result = _call_llm("system", "user")
        self.assertEqual(result["__llm_model"], "gpt-5.6-sol")
        self.assertEqual(result["__llm_usage"], {})

    def test_deepseek_request_enables_reasoning_without_temperature(self):
        from intent import _call_llm

        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "model": "deepseek-v4-pro",
                    "choices": [{"message": {"content": '{"mode":"custom"}'}}],
                }

        captured = {}

        def fake_post(_url, **kwargs):
            captured.update(kwargs["json"])
            return Response()

        env = {
            "LLM_MODE": "api",
            "LLM_API_KEY": "local-test-value",
            "LLM_BASE_URL": "https://api.deepseek.com/chat/completions",
            "LLM_MODEL": "deepseek-v4-pro",
            "LLM_TIMEOUT": "60",
            "LLM_THINKING": "enabled",
            "LLM_REASONING_EFFORT": "high",
            "LLM_MAX_TOKENS": "4000",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "intent.requests.post", side_effect=fake_post
        ), redirect_stderr(io.StringIO()):
            result = _call_llm("system", "user")
        self.assertEqual(result["mode"], "custom")
        self.assertEqual(captured["thinking"], {"type": "enabled"})
        self.assertEqual(captured["reasoning_effort"], "high")
        self.assertNotIn("temperature", captured)

    def test_llm_retries_one_transient_connection_error(self):
        from intent import _call_llm

        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "model": "deepseek-v4-pro",
                    "choices": [{"message": {"content": '{"mode":"standard"}'}}],
                }

        env = {
            "LLM_MODE": "api",
            "LLM_API_KEY": "local-test-value",
            "LLM_BASE_URL": "https://api.deepseek.com/chat/completions",
            "LLM_MODEL": "deepseek-v4-pro",
            "LLM_TIMEOUT": "60",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "intent.requests.post",
            side_effect=[__import__("requests").ConnectionError("transient"), Response()],
        ) as post, redirect_stderr(io.StringIO()) as logs:
            result = _call_llm("system", "user")
        self.assertEqual(result["mode"], "standard")
        self.assertEqual(post.call_count, 2)
        self.assertIn("transient_request_error", logs.getvalue())


class Neo4jClientTests(unittest.TestCase):
    def _client(self, driver, **kwargs):
        return Neo4jClient(
            password="test-password",
            driver_factory=lambda *_args, **_kwargs: driver,
            **kwargs,
        )

    def test_health_success_and_cache(self):
        now = [100.0]
        driver = FakeDriver(FakeSession())
        client = self._client(driver, clock=lambda: now[0], cache_ttl=30)
        first = client.health()
        second = client.health()
        self.assertEqual(first, second)
        self.assertTrue(first["connected"])
        self.assertEqual(first["version"], "2026.06.0")
        self.assertEqual(first["node_count"], 42)
        self.assertEqual(first["relationship_count"], 84)
        self.assertEqual(first["label_counts"]["Tool"], 11)
        self.assertEqual(driver.verify_calls, 1)
        now[0] += 31
        client.health()
        self.assertEqual(driver.verify_calls, 2)
        self.assertTrue(all(call["default_access_mode"] == "READ" for call in driver.session_calls))

    def test_authentication_failure_is_sanitized(self):
        class AuthError(Exception):
            pass

        driver = FakeDriver(FakeSession(), AuthError("secret server details"))
        health = self._client(driver).health()
        self.assertFalse(health["connected"])
        self.assertEqual(health["error"], "authentication_failed")
        self.assertNotIn("secret", json.dumps(health))

    def test_timeout_is_sanitized(self):
        class ConnectionTimeout(Exception):
            pass

        driver = FakeDriver(FakeSession(), ConnectionTimeout("bolt://hidden:7687"))
        health = self._client(driver).health()
        self.assertEqual(health["error"], "connection_timeout")
        self.assertNotIn("bolt", json.dumps(health))

    def test_evidence_maps_matches_missing_tools_and_slots(self):
        rows = [
            {
                "tool_id": "rnaseq_unsupervised_cluster",
                "matched": True,
                "relationship_type": "HAS_INPUT_SLOT",
                "direction": "outgoing",
                "neighbor_labels": ["InputSlot"],
                "neighbor_properties": {"slot_id": "count_tsv", "required": True},
            },
            {
                "tool_id": "missing_pipeline",
                "matched": False,
                "relationship_type": None,
                "direction": None,
                "neighbor_labels": [],
                "neighbor_properties": None,
            },
        ]
        client = self._client(FakeDriver(FakeSession(rows)))
        evidence = client.evidence(["rnaseq_unsupervised_cluster", "missing_pipeline"])
        self.assertTrue(evidence["connected"])
        self.assertEqual(evidence["source"], "neo4j-runtime")
        self.assertEqual(evidence["matched_tool_ids"], ["rnaseq_unsupervised_cluster"])
        self.assertEqual(evidence["missing_tool_ids"], ["missing_pipeline"])
        self.assertEqual(evidence["slot_evidence"][0]["neighbor"]["slot_id"], "count_tsv")

    def test_missing_password_degrades_without_loading_driver(self):
        client = Neo4jClient(password="")
        health = client.health()
        self.assertFalse(health["connected"])
        self.assertEqual(health["error"], "not_configured")


@unittest.skipUnless(
    os.environ.get("RUN_REAL_INTEGRATION") == "1" and os.environ.get("NEO4J_PASSWORD"),
    "set RUN_REAL_INTEGRATION=1 and NEO4J_PASSWORD to use the local Neo4j instance",
)
class RealNeo4jIntegrationTests(unittest.TestCase):
    def test_local_instance_and_known_pipeline(self):
        client = Neo4jClient()
        health = client.health(force=True)
        self.assertTrue(health["connected"], health)
        self.assertEqual(health["version"], "2026.06.0")
        self.assertGreater(health["node_count"], 0)
        self.assertGreater(health["relationship_count"], 0)
        evidence = client.evidence(["rnaseq_unsupervised_cluster"])
        self.assertIn("rnaseq_unsupervised_cluster", evidence["matched_tool_ids"])
        catalog = client.tool_catalog()
        self.assertTrue(catalog["connected"], catalog)
        # Read the sizes from the contract rather than hard-coding them, so the
        # catalog can grow without the integration test going stale. These are
        # the runtime numbers, which are not the graph's: `tool_catalog.tools`
        # counts `:tool` nodes, while `tool_catalog()` returns what the composer
        # can actually use, and that excludes multiqc.
        expected_catalog = load_expectations()["raw"]["tool_catalog"]["runtime_catalog"]
        self.assertEqual(len(catalog["tools"]), expected_catalog["tools"])
        self.assertEqual(len(catalog["next_edges"]), expected_catalog["next_edges"])
        rnaseq_steps = [
            step for step in catalog["pipeline_steps"]
            if step["pipeline_id"] == "rnaseq_singletask"
        ]
        # 7 步是 multiqc 被排除之前的数字，同样从契约里读。
        self.assertEqual(len(rnaseq_steps), expected_catalog["pipeline_steps"])
        self.assertNotIn("multiqc", {step["tool_id"] for step in rnaseq_steps})
        self.assertTrue(all(step["source"] == "sister-task-pipeline" for step in rnaseq_steps))
        client.close()

    def test_every_benchmark_asset_name_exists_in_the_graph(self):
        """A reference file the graph does not have degrades silently.

        The 96-case benchmark names the exact files each case should resolve
        to. When a name drifts from the delivery -- five of them said `.xls`
        while every clinical table in the graph is `.xlsx` -- the recommendation
        still comes back, just with that input reported missing, so the caller
        gets an unsubmittable plan and no error anywhere. Fail loudly instead.
        """
        import re

        from neo4j import GraphDatabase

        benchmark = (ROOT / "config" / "question_tool_data_benchmark.json").read_text(
            encoding="utf-8"
        )
        referenced = set(
            re.findall(r'"([A-Za-z0-9_.\-]+\.(?:xls|xlsx|tsv|csv|maf|txt))"', benchmark)
        )
        self.assertTrue(referenced, "benchmark should reference data files")

        driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        )
        try:
            with driver.session(database=os.environ.get("NEO4J_DATABASE") or "neo4j") as session:
                in_graph = {
                    record["file_name"]
                    for record in session.run(
                        "MATCH (n) WHERE n:T1 OR n:T2 "
                        "RETURN DISTINCT n.file_name AS file_name"
                    )
                    if record["file_name"]
                }
        finally:
            driver.close()

        missing = sorted(referenced - in_graph)
        self.assertEqual(missing, [], f"benchmark references files the graph lacks: {missing}")


@unittest.skipUnless(
    os.environ.get("RUN_REAL_INTEGRATION") == "1" and os.environ.get("LLM_API_KEY"),
    "set RUN_REAL_INTEGRATION=1 and a rotated LLM_API_KEY to call the real LLM",
)
class RealLlmIntegrationTests(unittest.TestCase):
    def test_fastq_prompt_regression_is_four_for_four(self):
        from workflow_composer import WorkflowComposer

        cases = [
            (
                "如何从 RNA-seq paired-end FASTQ 出发，依次完成 FastQC、Trim Galore、rRNA 去除、"
                "STAR 比对、RSEM 定量、FeatureCounts 计数和 MultiQC 汇总？",
                "ready",
            ),
            (
                "查找双端 RNA-seq 测序数据，想完成质控、接头剪切、比对和基因表达计数。",
                "ready",
            ),
            ("RNA-seq FASTQ 原始数据怎么做完整上游分析？", "ready"),
            # uBAM has no atomic tool. Whether that surfaces as `unsupported` or
            # as `information` depends on whether the model also names the
            # matching business pipeline, so assert the invariant that actually
            # matters: no candidate, and a stated reason.
            (
                "把原始测序 FASTQ 整理成 GATK 后续分析可用的 uBAM 文件。",
                "no_atomic_chain",
            ),
        ]
        composer = WorkflowComposer()
        for query, expected_status in cases:
            with self.subTest(query=query):
                result = composer.plan(query)
                metadata = result["planner_metadata"]
                self.assertTrue(metadata["used"], metadata)
                self.assertEqual(metadata["model"], os.environ["LLM_MODEL"])
                self.assertEqual(metadata["status"], "ok")
                self.assertEqual(metadata["calls"], 1)
                self.assertEqual(result["schema_version"], "tool-chain/v2")
                if expected_status == "ready":
                    self.assertEqual(result["selection_status"], "ready")
                    self.assertGreater(result["candidate_count"], 0)
                    self.assertLessEqual(result["candidate_count"], 3)
                    self.assertTrue(all(
                        candidate["validation_ok"]
                        and candidate["feasibility_status"] == "ready"
                        for candidate in result["candidates"]
                    ))
                else:
                    self.assertIn(
                        result["selection_status"],
                        {"unsupported", "information", "no_candidate"},
                    )
                    self.assertEqual(result["candidates"], [])
                    self.assertTrue(
                        result["unsupported_reason"]
                        or result["extensions"]["atomic_candidate_unavailable_reason"]
                    )
                serialized = json.dumps(result, ensure_ascii=False)
                self.assertNotIn("RNASeqAnalysis", serialized)
                self.assertNotIn("wdl_path", serialized)

    def test_atomic_unsupported_and_capability_routing(self):
        from workflow_composer import WorkflowComposer

        composer = WorkflowComposer()

        # Not atomized. `unsupported` when the model returns nothing usable,
        # `information` when it still surfaces the matching business pipeline;
        # either way there must be no atomic candidate and a stated reason.
        unsupported = composer.plan("我有肝癌 MAF，先做突变景观，再做 TMB 生存分析")
        self.assertIn(
            unsupported["selection_status"], {"unsupported", "information", "no_candidate"}
        )
        self.assertEqual(unsupported["candidates"], [])
        self.assertTrue(
            unsupported["unsupported_reason"]
            or unsupported["extensions"]["atomic_candidate_unavailable_reason"]
        )
        self.assertTrue(unsupported["planner_metadata"]["used"])

        custom = composer.plan(
            "修改完整双端 RNA-seq 上游流程：去掉 RSEM，只保留 featureCounts 计数，"
            "其余 FastQC、Trim Galore、STAR、SAMtools 和 MultiQC 保持。"
        )
        self.assertEqual(custom["schema_version"], "tool-chain/v2")
        self.assertEqual(custom["selection_status"], "ready")
        self.assertTrue(custom["planner_metadata"]["used"])
        internal_ids = custom["candidates"][0]["extensions"]["internal_tool_ids"]
        self.assertIn("featurecounts", internal_ids)
        self.assertNotIn("rsem", internal_ids)

        blocked = composer.plan("把 RNA-seq 标准流程中的 RSEM 换成 Salmon")
        self.assertIn(blocked["selection_status"], {"unsupported", "no_candidate"})
        self.assertEqual(blocked["candidates"], [])
        self.assertTrue(blocked["unsupported_reason"])

        capability = composer.plan("有哪些流程可以处理 MAF 文件")
        self.assertEqual(capability["selection_status"], "information")
        self.assertEqual(capability["candidate_count"], 0)
        self.assertFalse(capability["planner_metadata"]["used"])


if __name__ == "__main__":
    unittest.main()
