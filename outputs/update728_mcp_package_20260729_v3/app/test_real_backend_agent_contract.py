import unittest
from types import SimpleNamespace

import server
from knowledge_card_execution import KnowledgeCardExecutionRegistry
from workflow_composer import WorkflowComposer


class PublicChainContractTests(unittest.TestCase):
    def setUp(self):
        registry = KnowledgeCardExecutionRegistry()
        methods = {}
        for internal_id, contract in registry.tools.items():
            methods[internal_id] = SimpleNamespace(
                inputs=[{"name": name} for name in (contract.get("input_map") or {})]
            )
        self.composer = SimpleNamespace(
            execution_registry=registry,
            registered_methods=SimpleNamespace(all_methods=methods),
            _role_for_input=lambda name: "data_file",
        )

    def test_shared_fastqc_id_uses_public_namespace_for_public_io(self):
        self.assertEqual(
            server._chain_id_mode(self.composer, [{
                "step_id": "qc",
                "tool_id": "fastqc",
                "inputs": {"fastqs": {"asset_id": "a"}},
            }]),
            "execution_contract",
        )

    def test_shared_fastqc_id_uses_internal_namespace_for_internal_io(self):
        self.assertEqual(
            server._chain_id_mode(self.composer, [{
                "step_id": "qc",
                "tool_id": "fastqc",
                "inputs": {"raw_fastq_read": {"asset_role": "fastq_file"}},
            }]),
            "neo4j_internal",
        )

    def test_public_and_internal_ids_cannot_be_mixed(self):
        self.assertEqual(
            server._chain_id_mode(self.composer, [
                {"step_id": "trim", "tool_id": "fastp_paired_end", "inputs": {}},
                {"step_id": "star", "tool_id": "star", "inputs": {}},
            ]),
            "mixed",
        )

    def test_unknown_id_is_rejected_by_classifier(self):
        self.assertEqual(
            server._chain_id_mode(self.composer, [{
                "step_id": "bad", "tool_id": "not_registered", "inputs": {},
            }]),
            "unknown",
        )

    def test_empty_public_fastqc_is_rejected_by_execution_contract(self):
        result = self.composer.execution_registry.validate([
            {"step_id": "qc", "tool_id": "fastqc", "inputs": {}}
        ], [])
        self.assertFalse(result["ok"])
        self.assertIn("fastqs", " ".join(result["errors"]))

    def test_deterministic_business_rule_does_not_promote_fastqc_only(self):
        self.assertFalse(WorkflowComposer._deterministic_pipeline_recommendation(
            "RNA-seq FastQC", {"omics_type": "bulk RNA-seq"}
        ))
        self.assertTrue(WorkflowComposer._deterministic_pipeline_recommendation(
            "双端 RNA-seq FASTQ 做表达定量", {"omics_type": "bulk RNA-seq"}
        ))


if __name__ == "__main__":
    unittest.main()
