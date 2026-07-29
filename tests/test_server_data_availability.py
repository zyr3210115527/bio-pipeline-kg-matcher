import unittest

import server


WES_SIX_STEPS = [
    {
        "step_id": "fastp",
        "tool_id": "fastp",
        "inputs": {"raw_fastq_read": {"asset_role": "fastq_file"}},
    },
    {
        "step_id": "bwa",
        "tool_id": "bwa",
        "inputs": {
            "clean_fastq_read": {
                "from": {"step_id": "fastp", "output": "clean_fastq_read"}
            },
            "genome_annotation": {"asset_role": "reference_file"},
        },
    },
    {
        "step_id": "samtools",
        "tool_id": "samtools",
        "inputs": {
            "aligned_bam": {"from": {"step_id": "bwa", "output": "aligned_bam"}}
        },
    },
    {
        "step_id": "gatk",
        "tool_id": "gatk",
        "inputs": {
            "sorted_dedup_bam": {
                "from": {"step_id": "samtools", "output": "sorted_dedup_bam"}
            },
            "genome_annotation": {"asset_role": "reference_file"},
        },
    },
    {
        "step_id": "bcftools",
        "tool_id": "bcftools",
        "inputs": {
            "unfiltered_vcf": {
                "from": {"step_id": "gatk", "output": "unfiltered_vcf"}
            }
        },
    },
    {
        "step_id": "snpeff",
        "tool_id": "snpeff",
        "inputs": {
            "filtered_vcf": {
                "from": {"step_id": "bcftools", "output": "filtered_vcf"}
            },
            "genome_annotation": {"asset_role": "reference_file"},
        },
    },
]


def call_availability(arguments):
    response = server.handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "query_data_availability", "arguments": arguments},
    })
    return response


class CustomDataAvailabilityTests(unittest.TestCase):
    def test_valid_wes_chain_derives_fastq_and_finds_datasets(self):
        response = call_availability({
            "intent": {
                "query_text": "WES FASTQ 做体细胞变异检测并注释",
                "omics_type": "WES/MAF",
                "input_hint": "fq.gz",
            },
            "steps": WES_SIX_STEPS,
            "data_matcher_mode": "csv",
        })
        value = response["result"]["structuredContent"]
        self.assertEqual(value["schema_version"], "data-availability/v1")
        self.assertEqual(value["request_mode"], "custom_steps")
        self.assertEqual(value["required_asset_roles"], ["fastq_file"])
        self.assertEqual(value["required_data_roles"], ["fastq"])
        self.assertEqual(value["status"], "available")
        self.assertTrue(value["matched_data"]["data_combinations"])

    def test_unknown_tool_is_an_invalid_parameter_error(self):
        response = call_availability({
            "intent": {"query_text": "invalid"},
            "steps": [{
                "step_id": "unknown",
                "tool_id": "not_registered",
                "inputs": {},
            }],
            "data_matcher_mode": "csv",
        })
        self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(response["error"]["data"]["category"], "invalid_parameters")
        self.assertIn("未知 tool_id", response["error"]["message"])

    def test_valid_chain_without_matching_data_is_not_available(self):
        response = call_availability({
            "intent": {
                "query_text": "no matching cohort",
                "study_accessions": ["HRA999999"],
                "omics_type": "WES/MAF",
                "input_hint": "fq.gz",
            },
            "steps": [WES_SIX_STEPS[0]],
            "data_matcher_mode": "csv",
        })
        value = response["result"]["structuredContent"]
        self.assertEqual(value["status"], "not_available")
        self.assertFalse(value["feasibility"]["ok"])

    def test_registered_pipeline_path_remains_compatible(self):
        response = call_availability({
            "intent": {
                "query_text": "paired RNA-seq FASTQ",
                "omics_type": "bulk RNA-seq",
                "input_hint": "fq.gz",
            },
            "pipeline_ids": ["rnaseq_singletask"],
            "data_matcher_mode": "csv",
        })
        value = response["result"]["structuredContent"]
        self.assertEqual(value["schema_version"], "data-availability/v1")
        self.assertEqual(value["request_mode"], "pipeline_ids")
        self.assertNotIn("required_asset_roles", value)


if __name__ == "__main__":
    unittest.main()
