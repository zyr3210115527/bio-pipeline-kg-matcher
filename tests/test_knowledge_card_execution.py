import unittest

from knowledge_card_execution import KnowledgeCardExecutionRegistry


class KnowledgeCardExecutionTests(unittest.TestCase):
    def setUp(self):
        self.registry = KnowledgeCardExecutionRegistry()
        self.assets = [
            {
                "asset_id": "sample-r1",
                "sample_accession": "S1",
                "run_accession": "RUN1",
                "individual_accession": "I1",
                "sample_role": None,
                "mate": "r1",
            },
            {
                "asset_id": "sample-r2",
                "sample_accession": "S1",
                "run_accession": "RUN1",
                "individual_accession": "I1",
                "sample_role": None,
                "mate": "r2",
            },
        ]

    def test_all_atomic_tools_have_unique_knowledge_card_ids(self):
        self.assertEqual(len(self.registry.tools), 12)
        self.assertEqual(len(self.registry.by_execution_id), 12)
        self.assertEqual(
            self.registry.tools["star"]["execution_tool_id"],
            "star_rrna_and_genome_alignment",
        )
        self.assertEqual(
            self.registry.tools["samtools"]["execution_tool_id"],
            "samtools_alignment_processing",
        )
        self.assertEqual(
            self.registry.tools["featurecounts"]["execution_tool_id"],
            "featurecounts_gene_counting",
        )

    def test_rnaseq_chain_uses_knowledge_card_ids_and_io_names(self):
        internal = [
            {
                "step_id": "fastqc",
                "tool_id": "fastqc",
                "inputs": {"raw_fastq_read": {"asset_id": "sample-r1"}},
                "depends_on": [],
            },
            {
                "step_id": "trim_galore",
                "tool_id": "trim_galore",
                "inputs": {"raw_fastq_read": {"asset_id": "sample-r2"}},
                "depends_on": ["fastqc"],
            },
            {
                "step_id": "star",
                "tool_id": "star",
                "inputs": {
                    "clean_fastq_read": {
                        "from": {"step_id": "trim_galore", "output": "clean_fastq_read"}
                    }
                },
                "depends_on": ["trim_galore"],
            },
            {
                "step_id": "rsem",
                "tool_id": "rsem",
                "inputs": {
                    "transcriptome_bam": {
                        "from": {"step_id": "star", "output": "transcriptome_bam"}
                    }
                },
                "depends_on": ["star"],
            },
            {
                "step_id": "samtools",
                "tool_id": "samtools",
                "inputs": {
                    "aligned_bam": {
                        "from": {"step_id": "star", "output": "aligned_bam"}
                    }
                },
                "depends_on": ["star"],
            },
            {
                "step_id": "featurecounts",
                "tool_id": "featurecounts",
                "inputs": {
                    "sorted_dedup_bam": {
                        "from": {"step_id": "samtools", "output": "sorted_dedup_bam"}
                    }
                },
                "depends_on": ["samtools"],
            },
            {
                "step_id": "multiqc",
                "tool_id": "multiqc",
                "inputs": {},
                "depends_on": ["rsem", "featurecounts"],
            },
        ]
        external, errors = self.registry.externalize(internal, self.assets)
        self.assertEqual(errors, [])
        by_step = {step["step_id"]: step for step in external}
        self.assertEqual(
            by_step["star"]["tool_id"], "star_rrna_and_genome_alignment"
        )
        self.assertEqual(
            by_step["star"]["inputs"]["read1"]["from"]["output"],
            "trimmed_r1",
        )
        self.assertEqual(
            by_step["star"]["inputs"]["read2"]["from"]["output"],
            "trimmed_r2",
        )
        self.assertEqual(
            by_step["samtools"]["inputs"]["alignment"]["from"]["output"],
            "genome_bam",
        )
        self.assertEqual(
            by_step["featurecounts"]["inputs"]["bam"]["from"]["output"],
            "sorted_bam",
        )
        self.assertTrue(by_step["multiqc"]["inputs"]["qc_files"]["sources"])
        self.assertTrue(self.registry.validate(external, self.assets)["ok"])

    def test_gatk_to_bcftools_fails_closed_until_index_is_registered(self):
        internal = [
            {
                "step_id": "gatk",
                "tool_id": "gatk",
                "inputs": {},
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
        ]
        external, mapping_errors = self.registry.externalize(internal, [])
        self.assertEqual(mapping_errors, [])
        validation = self.registry.validate(external, [])
        self.assertFalse(validation["ok"])
        joined = " ".join(validation["errors"])
        self.assertIn("filtered_vcf_index", joined)
        self.assertIn("rejects Knowledge Card source", joined)


if __name__ == "__main__":
    unittest.main()
