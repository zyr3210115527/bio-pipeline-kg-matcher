import copy
import itertools
import os
import unittest

from workflow_composer import WorkflowComposer


def paired_steps():
    steps = []
    for role in ("tumor", "normal"):
        steps.extend([
            {
                "step_id": f"{role}_fastp",
                "tool_id": "fastp",
                "inputs": {
                    "raw_fastq_read_r1": {"asset_role": "fastq_r1"},
                    "raw_fastq_read_r2": {"asset_role": "fastq_r2"},
                },
            },
            {
                "step_id": f"{role}_bwa",
                "tool_id": "bwa",
                "inputs": {
                    "clean_fastq_read_r1": {
                        "from": {"step_id": f"{role}_fastp", "output": "clean_fastq_read_r1"}
                    },
                    "clean_fastq_read_r2": {
                        "from": {"step_id": f"{role}_fastp", "output": "clean_fastq_read_r2"}
                    },
                    "genome_annotation": {"asset_role": "reference_file"},
                },
            },
            {
                "step_id": f"{role}_samtools",
                "tool_id": "samtools",
                "inputs": {
                    "aligned_bam": {
                        "from": {"step_id": f"{role}_bwa", "output": "aligned_bam"}
                    }
                },
            },
        ])
    steps.extend([
        {
            "step_id": "gatk",
            "tool_id": "gatk",
            "inputs": {
                "tumor_bam": {
                    "from": {"step_id": "tumor_samtools", "output": "sorted_dedup_bam"}
                },
                "tumor_bai": {"from": {"step_id": "tumor_samtools", "output": "bai"}},
                "normal_bam": {
                    "from": {"step_id": "normal_samtools", "output": "sorted_dedup_bam"}
                },
                "normal_bai": {"from": {"step_id": "normal_samtools", "output": "bai"}},
                "interval_list": {"asset_role": "reference_file"},
            },
        },
        {
            "step_id": "bcftools",
            "tool_id": "bcftools",
            "inputs": {
                "unfiltered_vcf": {"from": {"step_id": "gatk", "output": "unfiltered_vcf"}}
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
    ])
    return steps


def paired_file_details():
    return [
        {
            "path": "/data/IND1_tumor_R1.fq.gz",
            "files": "IND1_tumor_R1.fq.gz",
            "input_role": "fastq",
            "read_pair": "r1",
            "study_accession": "STUDY1",
            "sample_accession": "T1",
            "run_accession": "TRUN",
            "individual_accession": "IND1",
            "sample_role": "tumor",
        },
        {
            "path": "/data/IND1_tumor_R2.fq.gz",
            "files": "IND1_tumor_R2.fq.gz",
            "input_role": "fastq",
            "read_pair": "r2",
            "study_accession": "STUDY1",
            "sample_accession": "T1",
            "run_accession": "TRUN",
            "individual_accession": "IND1",
            "sample_role": "tumor",
        },
        {
            "path": "/data/IND1_normal_R1.fq.gz",
            "files": "IND1_normal_R1.fq.gz",
            "input_role": "fastq",
            "read_pair": "r1",
            "study_accession": "STUDY1",
            "sample_accession": "N1",
            "run_accession": "NRUN",
            "individual_accession": "IND1",
            "sample_role": "normal",
        },
        {
            "path": "/data/IND1_normal_R2.fq.gz",
            "files": "IND1_normal_R2.fq.gz",
            "input_role": "fastq",
            "read_pair": "r2",
            "study_accession": "STUDY1",
            "sample_accession": "N1",
            "run_accession": "NRUN",
            "individual_accession": "IND1",
            "sample_role": "normal",
        },
    ]


class SlotModelTests(unittest.TestCase):
    def setUp(self):
        self.previous_force_rule = os.environ.get("FORCE_RULE")
        os.environ["FORCE_RULE"] = "1"
        self.composer = WorkflowComposer()

    def tearDown(self):
        if self.previous_force_rule is None:
            os.environ.pop("FORCE_RULE", None)
        else:
            os.environ["FORCE_RULE"] = self.previous_force_rule

    def _build_paired_contract(self, details):
        methods, validation = self.composer._validate_custom_steps(paired_steps())
        self.assertTrue(validation["ok"], validation)
        assets = self.composer._build_assets({"debug": {"file_details": details}})
        chain, missing, _parameters = self.composer._custom_tool_chain(
            {"methods": methods, "validation": validation}, assets
        )
        contract = {"assets": assets, "tool_chain": chain}
        return contract, missing, self.composer._validate_internal_agent_contract(contract)

    def test_paired_wes_binds_by_role_and_mate_for_five_permutations(self):
        details = paired_file_details()
        permutations = list(itertools.islice(itertools.permutations(details), 5))
        observed = []
        for permutation in permutations:
            contract, missing, validation = self._build_paired_contract(list(permutation))
            self.assertEqual(missing, [])
            self.assertTrue(validation["ok"], validation)
            assets = {asset["asset_id"]: asset for asset in contract["assets"]}
            fastp_steps = {
                step["step_id"]: step for step in contract["tool_chain"] if step["tool_id"] == "fastp"
            }
            assignment = []
            for role in ("tumor", "normal"):
                for mate in ("r1", "r2"):
                    asset_id = fastp_steps[f"{role}_fastp"]["inputs"][f"raw_fastq_read_{mate}"]["asset_id"]
                    asset = assets[asset_id]
                    self.assertEqual(asset["sample_role"], role)
                    self.assertEqual(asset["mate"], mate)
                    self.assertEqual(asset["individual_accession"], "IND1")
                    assignment.append(asset["path"])
            observed.append(assignment)
        self.assertTrue(all(item == observed[0] for item in observed[1:]))

    def test_swapped_sample_role_and_mate_fail_contract_validation(self):
        contract, missing, validation = self._build_paired_contract(paired_file_details())
        self.assertEqual(missing, [])
        self.assertTrue(validation["ok"])

        swapped_roles = copy.deepcopy(contract)
        for asset in swapped_roles["assets"]:
            asset["sample_role"] = "normal" if asset["sample_role"] == "tumor" else "tumor"
        role_validation = self.composer._validate_internal_agent_contract(swapped_roles)
        self.assertFalse(role_validation["ok"])
        self.assertIn("sample_role", " ".join(role_validation["errors"]))

        swapped_mates = copy.deepcopy(contract)
        for asset in swapped_mates["assets"]:
            asset["mate"] = "r2" if asset["mate"] == "r1" else "r1"
        mate_validation = self.composer._validate_internal_agent_contract(swapped_mates)
        self.assertFalse(mate_validation["ok"])
        self.assertIn("mate", " ".join(mate_validation["errors"]))

    def test_fastp_variant_boundaries(self):
        cases = [
            ({"raw_fastq_read": {"asset_role": "fastq_file"}}, True),
            ({"raw_fastq_read_r1": {"asset_role": "fastq_r1"}}, True),
            ({
                "raw_fastq_read_r1": {"asset_role": "fastq_r1"},
                "raw_fastq_read_r2": {"asset_role": "fastq_r2"},
            }, True),
        ]
        for inputs, expected in cases:
            _methods, validation = self.composer._validate_custom_steps([
                {"step_id": "fastp", "tool_id": "fastp", "inputs": inputs}
            ])
            self.assertEqual(validation["ok"], expected, validation)

        _methods, missing_r2 = self.composer._validate_custom_steps([
            {
                "step_id": "tumor_fastp",
                "tool_id": "fastp",
                "inputs": {"raw_fastq_read_r1": {"asset_role": "fastq_r1"}},
            }
        ])
        self.assertFalse(missing_r2["ok"])

    def test_gatk_variant_boundaries(self):
        single = [{
            "step_id": "gatk",
            "tool_id": "gatk",
            "inputs": {"sorted_dedup_bam": {"asset_role": "bam_file"}},
        }]
        _methods, validation = self.composer._validate_custom_steps(single)
        self.assertTrue(validation["ok"], validation)

        incomplete = copy.deepcopy(paired_steps()[:-2])
        incomplete[-1]["inputs"].pop("normal_bai")
        _methods, validation = self.composer._validate_custom_steps(incomplete)
        self.assertFalse(validation["ok"])

        mixed = copy.deepcopy(paired_steps()[:-2])
        mixed[-1]["inputs"]["sorted_dedup_bam"] = {
            "from": {"step_id": "tumor_samtools", "output": "sorted_dedup_bam"}
        }
        _methods, validation = self.composer._validate_custom_steps(mixed)
        self.assertFalse(validation["ok"])

    def test_single_sample_wes_keeps_legacy_gatk_slot(self):
        steps = paired_steps()[:3]
        for step in steps:
            step["step_id"] = step["step_id"].replace("tumor_", "")
            for binding in step.get("inputs", {}).values():
                source = binding.get("from")
                if source:
                    source["step_id"] = source["step_id"].replace("tumor_", "")
        steps.append({
            "step_id": "gatk",
            "tool_id": "gatk",
            "inputs": {
                "sorted_dedup_bam": {
                    "from": {"step_id": "samtools", "output": "sorted_dedup_bam"}
                },
                "interval_list": {"asset_role": "reference_file"},
            },
        })
        methods, validation = self.composer._validate_custom_steps(steps)
        self.assertTrue(validation["ok"], validation)
        self.assertEqual(methods[-1]["input_variant"], "single")


if __name__ == "__main__":
    unittest.main()
