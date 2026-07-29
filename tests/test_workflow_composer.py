import json
import os
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import _shape_case
from pipeline_router import PipelineRouter, render_pipeline_answer
from server import TOOL_CHAIN_OUTPUT_SCHEMA
from workflow_composer import WorkflowComposer, list_workflow_methods


def fastqc_steps():
    return [{
        "step_id": "fastqc",
        "tool_id": "fastqc",
        "inputs": {"raw_fastq_read": {"asset_role": "fastq_r1"}},
    }]


def rnaseq_steps():
    return [
        {
            "step_id": "fastp",
            "tool_id": "fastp",
            "inputs": {
                "raw_fastq_read_r1": {"asset_role": "fastq_r1"},
                "raw_fastq_read_r2": {"asset_role": "fastq_r2"},
            },
        },
        {
            "step_id": "star",
            "tool_id": "star",
            "inputs": {
                "clean_fastq_read": {
                    "from": {"step_id": "fastp", "output": "clean_fastq_read"}
                },
                "genome_annotation": {"asset_role": "reference_file"},
            },
        },
        {
            "step_id": "rsem",
            "tool_id": "rsem",
            "inputs": {
                "transcriptome_bam": {
                    "from": {"step_id": "star", "output": "transcriptome_bam"}
                },
                "genome_annotation": {"asset_role": "reference_file"},
            },
        },
        {
            "step_id": "samtools",
            "tool_id": "samtools",
            "inputs": {
                "aligned_bam": {
                    "from": {"step_id": "star", "output": "aligned_bam"}
                }
            },
        },
        {
            "step_id": "featurecounts",
            "tool_id": "featurecounts",
            "inputs": {
                "sorted_dedup_bam": {
                    "from": {
                        "step_id": "samtools",
                        "output": "sorted_dedup_bam",
                    }
                },
                "genome_annotation": {"asset_role": "reference_file"},
            },
        },
    ]


def paired_wes_steps():
    steps = []
    for role in ("tumor", "normal"):
        steps.extend([
            {
                "step_id": f"fastp_{role}",
                "tool_id": "fastp",
                "inputs": {
                    "raw_fastq_read_r1": {"asset_role": "fastq_r1"},
                    "raw_fastq_read_r2": {"asset_role": "fastq_r2"},
                },
            },
            {
                "step_id": f"bwa_{role}",
                "tool_id": "bwa",
                "inputs": {
                    "clean_fastq_read_r1": {
                        "from": {
                            "step_id": f"fastp_{role}",
                            "output": "clean_fastq_read_r1",
                        }
                    },
                    "clean_fastq_read_r2": {
                        "from": {
                            "step_id": f"fastp_{role}",
                            "output": "clean_fastq_read_r2",
                        }
                    },
                    "genome_annotation": {"asset_role": "reference_file"},
                },
            },
            {
                "step_id": f"samtools_{role}",
                "tool_id": "samtools",
                "inputs": {
                    "aligned_bam": {
                        "from": {
                            "step_id": f"bwa_{role}",
                            "output": "aligned_bam",
                        }
                    }
                },
            },
        ])
    steps.append({
        "step_id": "gatk",
        "tool_id": "gatk",
        "inputs": {
            "tumor_bam": {
                "from": {"step_id": "samtools_tumor", "output": "sorted_dedup_bam"}
            },
            "tumor_bai": {
                "from": {"step_id": "samtools_tumor", "output": "bai"}
            },
            "normal_bam": {
                "from": {"step_id": "samtools_normal", "output": "sorted_dedup_bam"}
            },
            "normal_bai": {
                "from": {"step_id": "samtools_normal", "output": "bai"}
            },
            "genome_annotation": {"asset_role": "reference_file"},
            "interval_list": {"asset_role": "reference_file"},
        },
    })
    return steps


def decision(*chains, unsupported_reason=None):
    return {
        "analysis": {"checks": "test"},
        "candidates": [
            {"rank": index, "match_note": f"candidate {index}", "steps": steps}
            for index, steps in enumerate(chains, 1)
        ],
        "unsupported_reason": unsupported_reason,
    }


class EmptyMatcher:
    @staticmethod
    def _empty():
        return {
            "data_schema": "test",
            "cohort_candidates": [],
            "file_candidates": [],
            "backup_file_candidates": [],
            "data_combinations": [],
            "query_constraints": {},
        }

    def match(self, intent, pipelines, limit=10):
        return self._empty()

    def match_custom_roles(self, intent, roles, limit=10):
        return self._empty()


class WorkflowComposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_force_rule = os.environ.get("FORCE_RULE")
        os.environ["FORCE_RULE"] = "1"
        cls.composer = WorkflowComposer()

    @classmethod
    def tearDownClass(cls):
        if cls.previous_force_rule is None:
            os.environ.pop("FORCE_RULE", None)
        else:
            os.environ["FORCE_RULE"] = cls.previous_force_rule

    def top3(self, payload, text="双端 RNA-seq FASTQ 做上游分析", top_k=3):
        return self.composer._top3_plan(
            text,
            payload,
            {"used": True, "status": "ok", "calls": 1, "model": "test"},
            top_k,
        )

    def test_01_normalized_kg_schema_is_primary(self):
        self.assertEqual(self.composer.router.matcher.data_schema, "normalized-v2")

    def test_02_runtime_router_requires_neo4j_catalog(self):
        with self.assertRaisesRegex(ValueError, "Neo4j-backed"):
            PipelineRouter(None)

    def test_03_atomic_catalog_has_twelve_tools(self):
        self.assertEqual(len(self.composer.registered_methods.methods), 12)

    def test_04_pipeline_nodes_are_not_in_atomic_menu(self):
        ids = {line.split(" | ", 1)[0][2:] for line in self.composer._method_menu_lines()}
        self.assertFalse(ids & set(self.composer.registered_methods.pipeline_methods))

    def test_05_method_menu_is_deterministic(self):
        self.assertEqual(
            self.composer._method_menu_lines(),
            self.composer._method_menu_lines(),
        )

    def test_06_plan_uses_one_top3_llm_decision(self):
        payload = decision(fastqc_steps())
        with patch.object(
            self.composer,
            "_top3_llm_decision",
            return_value=(payload, {"used": True, "status": "ok", "calls": 1}),
        ) as call:
            result = self.composer.plan("对 RNA-seq FASTQ 做 FastQC")
        call.assert_called_once()
        self.assertEqual(result["schema_version"], "tool-chain/v2")

    def test_07_llm_prompt_requests_one_to_five_candidates(self):
        os.environ["FORCE_RULE"] = "0"
        raw = {
            **decision(fastqc_steps()),
            "__llm_model": "test",
            "__llm_usage": {"total_tokens": 9},
        }
        try:
            with patch("workflow_composer._lazy_call_llm", return_value=raw) as call:
                value, metadata = self.composer._top3_llm_decision("FASTQ 做 FastQC")
        finally:
            os.environ["FORCE_RULE"] = "1"
        self.assertEqual(call.call_count, 1)
        prompt = call.call_args.args[0]
        self.assertIn("1 到 5 条", prompt)
        self.assertIn("Neo4j atomic 方法目录", prompt)
        self.assertIn("不得从“一对双端 FASTQ”推断 tumor/normal", prompt)
        self.assertIn("paired-end FASTQ 的 FastQC 当前只有单一泛化", prompt)
        self.assertIn("尚不能把 GATK 的 VCF 及 index", prompt)
        self.assertIn("candidates 生成前的强制短路条件", prompt)
        self.assertIn("`FastQC -> STAR` 没有 NEXT", prompt)
        self.assertIn("输入与方法冲突", prompt)
        self.assertNotIn("标准 pipeline 菜单", prompt)
        self.assertEqual(metadata["calls"], 1)
        self.assertEqual(value["candidates"][0]["rank"], 1)

    def test_08_llm_failure_has_no_rule_pipeline_fallback(self):
        value, metadata = self.composer._top3_llm_decision("FASTQ 做 FastQC")
        self.assertIsNone(value)
        self.assertEqual(metadata["status"], "force_rule")

    def test_09_ranked_candidates_are_sorted(self):
        values = [
            {"rank": 3, "steps": [{"tool_id": "c"}]},
            {"rank": 1, "steps": [{"tool_id": "a"}]},
            {"rank": 2, "steps": [{"tool_id": "b"}]},
        ]
        result = self.composer._normalize_ranked_candidates(values)
        self.assertEqual([item["rank"] for item in result], [1, 2, 3])

    def test_10_duplicate_chains_are_removed(self):
        values = [
            {"rank": 1, "steps": fastqc_steps()},
            {"rank": 2, "steps": deepcopy(fastqc_steps())},
        ]
        self.assertEqual(len(self.composer._normalize_ranked_candidates(values)), 1)

    def test_11_duplicate_ranks_are_made_unique(self):
        values = [
            {"rank": 1, "steps": fastqc_steps()},
            {"rank": 1, "steps": rnaseq_steps()},
        ]
        result = self.composer._normalize_ranked_candidates(values)
        self.assertEqual([item["rank"] for item in result], [1, 2])

    def test_12_candidate_generation_is_capped_at_five(self):
        values = [
            {"rank": i, "steps": [{"step_id": f"s{i}", "tool_id": "fastqc"}]}
            for i in range(1, 8)
        ]
        self.assertEqual(len(self.composer._normalize_ranked_candidates(values)), 5)

    def test_13_top_k_limits_returned_candidates(self):
        payload = decision(fastqc_steps(), rnaseq_steps())
        result = self.top3(payload, top_k=1)
        self.assertEqual(result["candidate_count"], 1)

    def test_14_top3_never_returns_more_than_three(self):
        payload = decision(
            fastqc_steps(),
            rnaseq_steps(),
            [{**fastqc_steps()[0], "step_id": "fastqc_alt"}],
            [{**fastqc_steps()[0], "step_id": "fastqc_four"}],
        )
        result = self.top3(payload, top_k=9)
        self.assertLessEqual(result["candidate_count"], 3)

    def test_15_unsupported_is_not_empty_success(self):
        result = self.top3(
            {"candidates": [], "unsupported_reason": "生存分析尚未原子化，暂不支持。"},
            "做生存分析",
        )
        self.assertEqual(result["selection_status"], "unsupported")
        self.assertEqual(result["candidates"], [])
        self.assertIn("尚未原子化", result["unsupported_reason"])
        self.assertIn(
            "尚未原子化",
            result["extensions"]["atomic_candidate_unavailable_reason"],
        )

    def test_16_empty_model_output_is_no_candidate(self):
        result = self.top3(None)
        self.assertEqual(result["selection_status"], "no_candidate")
        self.assertEqual(result["candidate_count"], 0)

    def test_17_unknown_tool_candidate_is_rejected(self):
        payload = decision([{
            "step_id": "invented",
            "tool_id": "invented_tool",
            "inputs": {},
        }])
        result = self.top3(payload)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["extensions"]["rejected_candidates"][0]["stage"], "validation")
        self.assertIn(
            "未通过 validation",
            result["extensions"]["atomic_candidate_unavailable_reason"],
        )

    def test_18_invalid_next_edge_is_rejected(self):
        steps = [
            {
                "step_id": "trim",
                "tool_id": "trim_galore",
                "inputs": {"raw_fastq_read": {"asset_role": "fastq_r1"}},
            },
            {
                "step_id": "report",
                "tool_id": "multiqc",
                "inputs": {},
                "depends_on": ["trim"],
            },
        ]
        _methods, validation = self.composer._validate_custom_steps(steps)
        self.assertFalse(validation["ok"])
        self.assertIn("NEXT 不允许", " ".join(validation["errors"]))

    def test_19_star_aligned_bam_connects_to_samtools(self):
        steps = [
            {
                "step_id": "star",
                "tool_id": "star",
                "inputs": {
                    "clean_fastq_read": {"asset_role": "fastq_r1"},
                    "genome_annotation": {"asset_role": "reference_file"},
                },
            },
            {
                "step_id": "samtools",
                "tool_id": "samtools",
                "inputs": {
                    "aligned_bam": {
                        "from": {"step_id": "star", "output": "aligned_bam"}
                    }
                },
            },
        ]
        _methods, validation = self.composer._validate_custom_steps(steps)
        self.assertTrue(validation["ok"], validation)

    def test_20_transcriptome_bam_cannot_feed_samtools(self):
        steps = [
            {
                "step_id": "star",
                "tool_id": "star",
                "inputs": {
                    "clean_fastq_read": {"asset_role": "fastq_r1"},
                    "genome_annotation": {"asset_role": "reference_file"},
                },
            },
            {
                "step_id": "samtools",
                "tool_id": "samtools",
                "inputs": {
                    "aligned_bam": {
                        "from": {"step_id": "star", "output": "transcriptome_bam"}
                    }
                },
            },
        ]
        _methods, validation = self.composer._validate_custom_steps(steps)
        self.assertFalse(validation["ok"])
        self.assertIn("NEXT data 边不匹配", " ".join(validation["errors"]))

    def test_21_complete_rnaseq_chain_validates(self):
        _methods, validation = self.composer._validate_custom_steps(rnaseq_steps())
        self.assertTrue(validation["ok"], validation)

    def test_22_numeric_step_ids_are_normalized(self):
        steps = [
            {
                "step_id": 1,
                "tool_id": "fastp",
                "inputs": {"raw_fastq_read": {"asset_role": "fastq_r1"}},
            },
            {
                "step_id": 2,
                "tool_id": "fastqc",
                "inputs": {
                    "clean_fastq_read": {
                        "from": {"step_id": 1, "output": "clean_fastq_read"}
                    }
                },
            },
        ]
        methods, validation = self.composer._validate_custom_steps(steps)
        self.assertTrue(validation["ok"], validation)
        self.assertEqual([item["step_id"] for item in methods], ["step_1", "step_2"])

    def test_23_string_asset_binding_is_normalized(self):
        methods, validation = self.composer._validate_custom_steps([{
            "step_id": "qc",
            "tool_id": "fastqc",
            "inputs": {"raw_fastq_read": "fastq_r1"},
        }])
        self.assertTrue(validation["ok"], validation)
        self.assertEqual(
            methods[0]["inputs"]["raw_fastq_read"],
            {"asset_role": "fastq_r1"},
        )

    def test_24_disconnected_asset_only_chain_is_rejected(self):
        steps = fastqc_steps() + [{
            "step_id": "second_qc",
            "tool_id": "fastqc",
            "inputs": {"raw_fastq_read": {"asset_role": "fastq_r1"}},
        }]
        _methods, validation = self.composer._validate_custom_steps(steps)
        self.assertFalse(validation["ok"])

    def test_25_paired_wes_shape_is_detected(self):
        methods, validation = self.composer._validate_custom_steps(paired_wes_steps())
        self.assertTrue(validation["ok"], validation)
        self.assertTrue(self.composer._is_paired_wes_candidate(methods))

    def test_26_paired_detection_requires_four_gatk_slots(self):
        steps = paired_wes_steps()
        del steps[-1]["inputs"]["normal_bai"]
        methods, _validation = self.composer._validate_custom_steps(steps)
        self.assertFalse(self.composer._is_paired_wes_candidate(methods))

    def test_27_paired_detection_requires_both_sample_suffixes(self):
        methods, _validation = self.composer._validate_custom_steps(rnaseq_steps())
        self.assertFalse(self.composer._is_paired_wes_candidate(methods))

    def test_28_paired_wes_uses_dedicated_matcher_and_four_assets(self):
        result = self.top3(
            decision(paired_wes_steps()),
            "肿瘤正常配对 WES FASTQ 做体细胞变异检测",
        )
        self.assertEqual(result["candidate_count"], 1)
        candidate = result["candidates"][0]
        self.assertTrue(candidate["extensions"]["paired_wes_matcher"])
        self.assertEqual(len(candidate["assets"]), 4)

    def test_29_paired_assets_preserve_role_and_mate(self):
        result = self.top3(
            decision(paired_wes_steps()),
            "肿瘤正常配对 WES FASTQ 做体细胞变异检测",
        )
        assets = result["candidates"][0]["assets"]
        self.assertEqual(
            {(a["sample_role"], a["mate"]) for a in assets},
            {("tumor", "r1"), ("tumor", "r2"), ("normal", "r1"), ("normal", "r2")},
        )

    def test_30_gatk_four_slots_bind_to_matching_sample_roles(self):
        result = self.top3(
            decision(paired_wes_steps()),
            "肿瘤正常配对 WES FASTQ 做体细胞变异检测",
        )
        gatk = result["candidates"][0]["tool_chain"][-1]
        self.assertEqual(set(gatk["inputs"]), {
            "tumor_bam", "tumor_bai", "normal_bam", "normal_bai"
        })
        self.assertIn("tumor", gatk["inputs"]["tumor_bam"]["from"]["step_id"])
        self.assertIn("normal", gatk["inputs"]["normal_bam"]["from"]["step_id"])

    def test_31_other_candidate_does_not_pollute_paired_bindings(self):
        result = self.top3(
            decision(fastqc_steps(), paired_wes_steps()),
            "肿瘤正常配对 WES FASTQ 做体细胞变异检测",
        )
        paired = next(
            item for item in result["candidates"]
            if item["extensions"]["paired_wes_matcher"]
        )
        assets = paired["assets"]
        self.assertEqual(len(assets), 4)
        self.assertEqual({a["individual_accession"] for a in assets}, {
            assets[0]["individual_accession"]
        })

    def test_32_rnaseq_candidate_is_ready_with_complete_data(self):
        result = self.top3(decision(rnaseq_steps()))
        self.assertEqual(result["selection_status"], "ready")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["candidates"][0]["feasibility_status"], "ready")

    def test_33_rnaseq_candidate_uses_knowledge_card_ids(self):
        result = self.top3(decision(rnaseq_steps()))
        tool_ids = [step["tool_id"] for step in result["candidates"][0]["tool_chain"]]
        self.assertEqual(tool_ids, [
            "fastp_paired_end",
            "star_rrna_and_genome_alignment",
            "rsem_quantification",
            "samtools_alignment_processing",
            "featurecounts_gene_counting",
        ])

    def test_34_reference_inputs_are_execution_managed(self):
        result = self.top3(decision(rnaseq_steps()))
        roles = {asset["role"] for asset in result["candidates"][0]["assets"]}
        self.assertNotIn("reference_file", roles)

    def test_35_no_data_candidate_is_removed(self):
        original = self.composer.router.matcher
        intent = self.composer.router._rule_intent(
            "对 HRA999999 的双端 RNA-seq FASTQ 做基因计数"
        )
        self.assertEqual(intent["study_accessions"], ["HRA999999"])
        matched = original.match_custom_roles(intent, ["fastq_r1", "fastq_r2"])
        self.assertEqual(matched["data_combinations"], [])
        self.composer.router.matcher = EmptyMatcher()
        try:
            result = self.top3(decision(fastqc_steps()))
        finally:
            self.composer.router.matcher = original
        self.assertEqual(result["selection_status"], "no_candidate")
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(
            result["extensions"]["rejected_candidates"][0]["stage"],
            "data_matching",
        )

    def test_36_candidate_required_roles_exclude_reference(self):
        methods, validation = self.composer._validate_custom_steps(rnaseq_steps())
        roles = self.composer._candidate_required_asset_roles(methods, validation)
        self.assertEqual(roles, ["fastq_r1", "fastq_r2"])

    def test_37_count_role_is_not_abundance_role(self):
        self.assertEqual(
            self.composer._canonical_asset_role("count_matrix", "expression_matrix"),
            "count_matrix",
        )

    def test_38_fastq_filename_overrides_wrong_legacy_read_pair(self):
        role = self.composer._contract_asset_role({
            "input_role": "fastq",
            "files": "sample_R1.fastq.gz",
            "read_pair": "R2",
        })
        self.assertEqual(role, "fastq_r1")

    def test_39_count_and_abundance_assets_do_not_cross_bind(self):
        assets = [
            {"asset_id": "counts", "role": "count_matrix"},
            {"asset_id": "tpm", "role": "expression_matrix"},
        ]
        selected = self.composer._select_asset(
            "count_matrix", assets, {}, step_id="cluster"
        )
        self.assertEqual(selected["asset_id"], "counts")

    def test_40_internal_contract_rejects_missing_asset_id(self):
        validation = self.composer._validate_internal_agent_contract({
            "assets": [],
            "tool_chain": [{
                "step_id": "qc",
                "tool_id": "fastqc",
                "inputs": {"raw_fastq_read": {"asset_id": "missing"}},
            }],
        })
        self.assertFalse(validation["ok"])

    def test_41_capability_query_is_v2_information(self):
        result = self.composer.plan("你们能做什么？")
        self.assertEqual(result["schema_version"], "tool-chain/v2")
        self.assertEqual(result["selection_status"], "information")
        self.assertEqual(result["candidate_count"], 0)

    def test_42_capability_query_lists_atomic_tools(self):
        result = self.composer.plan("有哪些原子工具")
        self.assertEqual(
            result["capability_answer"]["atomic_tool_count"],
            len(self.composer.registered_methods.methods),
        )

    def test_43_personalized_change_is_not_catalog_browse(self):
        self.assertIsNone(
            self.composer._capability_intent("有哪些流程能把 RSEM 换成 Salmon")
        )

    def test_44_mcp_schema_is_tool_chain_v2(self):
        self.assertEqual(
            TOOL_CHAIN_OUTPUT_SCHEMA["properties"]["schema_version"]["const"],
            "tool-chain/v2",
        )
        self.assertIn("candidates", TOOL_CHAIN_OUTPUT_SCHEMA["required"])
        self.assertIn("recommendations", TOOL_CHAIN_OUTPUT_SCHEMA["required"])
        self.assertNotIn("agent_input", TOOL_CHAIN_OUTPUT_SCHEMA["properties"])

    def test_45_mcp_schema_caps_candidates_at_three(self):
        candidates = TOOL_CHAIN_OUTPUT_SCHEMA["properties"]["candidates"]
        self.assertEqual(candidates["maxItems"], 3)
        self.assertEqual(
            TOOL_CHAIN_OUTPUT_SCHEMA["properties"]["candidate_count"]["maximum"],
            3,
        )
        self.assertEqual(
            TOOL_CHAIN_OUTPUT_SCHEMA["properties"]["recommendations"]["maxItems"],
            3,
        )

    def test_46_method_listing_separates_atomic_and_pipeline_nodes(self):
        methods = list_workflow_methods()
        atomic_ids = {item["tool_id"] for item in methods["atomic_tools"]}
        all_ids = {item["tool_id"] for item in methods["neo4j_tools"]}
        self.assertEqual(atomic_ids, set(self.composer.registered_methods.methods))
        self.assertGreater(len(all_ids), len(atomic_ids))

    def test_47_renderer_reads_v2_candidates(self):
        result = self.top3(decision(rnaseq_steps()))
        rendered = render_pipeline_answer(result)
        self.assertIn("候选", rendered)
        self.assertIn("fastp_paired_end", rendered)

    def test_48_demo_adapter_reads_v2_candidates(self):
        result = self.top3(decision(rnaseq_steps()))
        shaped = _shape_case("双端 RNA-seq FASTQ 做上游分析", result)
        self.assertEqual(shaped["candidate_count"], 1)
        self.assertEqual(len(shaped["pipelines"]), 1)
        self.assertTrue(shaped["orchestration_ready"])

    def test_49_mcp_stdout_is_json_for_no_candidate(self):
        request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "route_pipeline_request",
                "arguments": {"query": "未知流程", "data_matcher_mode": "neo4j"},
            },
        }, ensure_ascii=False)
        env = {
            **os.environ,
            "FORCE_RULE": "1",
            "NEO4J_URI": os.environ["NEO4J_URI"],
            "NEO4J_DATABASE": os.environ["NEO4J_DATABASE"],
            "NEO4J_PASSWORD": os.environ["NEO4J_PASSWORD"],
        }
        proc = subprocess.run(
            [sys.executable, str(ROOT / "server.py")],
            input=request + "\n",
            text=True,
            capture_output=True,
            env=env,
            cwd=ROOT,
            check=True,
        )
        response = json.loads(proc.stdout.strip())
        value = response["result"]["structuredContent"]
        self.assertEqual(value["schema_version"], "tool-chain/v2")
        self.assertEqual(value["candidate_count"], 0)

    def test_50_source_has_no_standard_route_switches(self):
        source = (ROOT / "workflow_composer.py").read_text(encoding="utf-8")
        self.assertNotIn("def _standard_", source)
        self.assertNotIn("force_custom", source)
        self.assertNotIn("expand_standard_steps", source)
        self.assertNotIn("tool-chain/v1", source)


if __name__ == "__main__":
    unittest.main()
