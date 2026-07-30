"""Translate internal Neo4j tool contracts to Knowledge Card execution contracts."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_CONTRACT_PATH = (
    Path(__file__).resolve().parent
    / "config"
    / "knowledge_card_execution_contracts.json"
)


class KnowledgeCardExecutionRegistry:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or DEFAULT_CONTRACT_PATH
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.schema_version = str(payload.get("schema_version") or "")
        self.source_archive = str(payload.get("source_archive") or "")
        self.source_sha256 = str(payload.get("source_sha256") or "")
        self.tools: Dict[str, Dict[str, Any]] = {
            str(tool_id): dict(contract)
            for tool_id, contract in (payload.get("tools") or {}).items()
        }
        self.by_execution_id: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        for internal_id, contract in self.tools.items():
            execution_id = str(contract.get("execution_tool_id") or "")
            if not execution_id:
                raise ValueError(f"Knowledge Card execution id missing: {internal_id}")
            if execution_id in self.by_execution_id:
                raise ValueError(f"duplicate Knowledge Card execution id: {execution_id}")
            self.by_execution_id[execution_id] = (internal_id, contract)

    def externalize(
        self,
        chain: Sequence[Dict[str, Any]],
        assets: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        internal_tools = {
            str(step.get("step_id") or ""): str(step.get("tool_id") or "")
            for step in chain
        }
        external: List[Dict[str, Any]] = []
        errors: List[str] = []
        for raw_step in chain:
            step = deepcopy(raw_step)
            internal_id = str(step.get("tool_id") or "")
            contract = self.tools.get(internal_id)
            if not contract:
                external.append(step)
                continue
            translated: Dict[str, Dict[str, Any]] = {}
            for internal_input, binding in (step.get("inputs") or {}).items():
                external_input = (contract.get("input_map") or {}).get(internal_input)
                if not external_input:
                    errors.append(
                        f"{step.get('step_id')}.{internal_input} has no Knowledge Card input mapping"
                    )
                    continue
                translated_binding = self._translate_binding(
                    binding, internal_tools, str(step.get("step_id") or ""), errors
                )
                if translated_binding is None:
                    continue
                if external_input in translated:
                    translated[external_input] = self._merge_bindings(
                        translated[external_input], translated_binding
                    )
                else:
                    translated[external_input] = translated_binding
            step["tool_id"] = contract["execution_tool_id"]
            step["inputs"] = translated
            external.append(step)

        self._augment_paired_reads(external, assets)
        self._augment_literals(external, chain, assets)
        self._augment_multiqc(external)
        return external, errors

    def validate(
        self,
        chain: Sequence[Dict[str, Any]],
        assets: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        errors: List[str] = []
        asset_ids = {str(asset.get("asset_id") or "") for asset in assets}
        known_steps: Dict[str, Dict[str, Any]] = {}
        for step in chain:
            step_id = str(step.get("step_id") or "")
            execution_id = str(step.get("tool_id") or "")
            resolved = self.by_execution_id.get(execution_id)
            if not resolved:
                continue
            _internal_id, contract = resolved
            inputs = step.get("inputs") or {}
            declared_inputs = contract.get("inputs") or {}
            for input_name in inputs:
                if input_name not in declared_inputs:
                    errors.append(f"{step_id} uses undeclared Knowledge Card input {input_name}")
            for input_name, spec in declared_inputs.items():
                if (
                    spec.get("required")
                    and spec.get("managed_by") == "mcp"
                    and input_name not in inputs
                ):
                    errors.append(f"{step_id} missing required Knowledge Card input {input_name}")
            for input_name, binding in inputs.items():
                self._validate_binding(
                    step_id,
                    input_name,
                    binding,
                    declared_inputs.get(input_name) or {},
                    known_steps,
                    asset_ids,
                    errors,
                )
            known_steps[step_id] = contract
        return {"ok": not errors, "errors": errors}

    def _translate_binding(
        self,
        binding: Dict[str, Any],
        internal_tools: Dict[str, str],
        step_id: str,
        errors: List[str],
    ) -> Optional[Dict[str, Any]]:
        if binding.get("asset_id"):
            return {"asset_id": binding["asset_id"]}
        source = binding.get("from")
        if not isinstance(source, dict):
            errors.append(f"{step_id} has unsupported internal binding")
            return None
        source_step = str(source.get("step_id") or "")
        source_internal = internal_tools.get(source_step, "")
        source_contract = self.tools.get(source_internal)
        if not source_contract:
            return {"from": dict(source)}
        source_output = str(source.get("output") or "")
        external_output = (source_contract.get("output_map") or {}).get(source_output)
        if not external_output:
            errors.append(
                f"{step_id} references {source_step}.{source_output} without a Knowledge Card output mapping"
            )
            return None
        return {"from": {"step_id": source_step, "output": external_output}}

    @staticmethod
    def _merge_bindings(
        left: Dict[str, Any], right: Dict[str, Any]
    ) -> Dict[str, Any]:
        if left == right:
            return left
        sources: List[Dict[str, Any]] = []
        for binding in (left, right):
            values = binding.get("sources") if isinstance(binding, dict) else None
            candidates = values if isinstance(values, list) else [binding]
            for candidate in candidates:
                if candidate not in sources:
                    sources.append(candidate)
        return {"sources": sources, "flatten": True}

    def _augment_paired_reads(
        self,
        chain: List[Dict[str, Any]],
        assets: Sequence[Dict[str, Any]],
    ) -> None:
        assets_by_id = {
            str(asset.get("asset_id") or ""): asset for asset in assets
        }
        steps = {str(step.get("step_id") or ""): step for step in chain}
        for step in chain:
            execution_id = str(step.get("tool_id") or "")
            inputs = step.get("inputs") or {}
            if execution_id == "fastqc" and "fastqs" in inputs:
                inputs["fastqs"] = self._paired_binding(
                    inputs["fastqs"], assets, assets_by_id, steps
                )
            if execution_id in {
                "fastp_paired_end",
                "bwa_mem_paired",
                "trim_galore",
                "star_rrna_and_genome_alignment",
            }:
                self._fill_read_pair(inputs, assets, assets_by_id, steps)

    def _paired_binding(
        self,
        binding: Dict[str, Any],
        assets: Sequence[Dict[str, Any]],
        assets_by_id: Dict[str, Dict[str, Any]],
        steps: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        sources = self._binding_sources(binding)
        expanded: List[Dict[str, Any]] = []
        for source in sources:
            if source.get("asset_id"):
                pair = self._asset_pair(assets_by_id.get(source["asset_id"]), assets)
                if pair:
                    expanded.extend({"asset_id": item["asset_id"]} for item in pair)
                else:
                    expanded.append(source)
                continue
            origin = source.get("from") or {}
            origin_step = steps.get(str(origin.get("step_id") or "")) or {}
            origin_tool = str(origin_step.get("tool_id") or "")
            if origin_tool in {"fastp_paired_end", "trim_galore"}:
                expanded.extend([
                    {"from": {"step_id": origin["step_id"], "output": "trimmed_r1"}},
                    {"from": {"step_id": origin["step_id"], "output": "trimmed_r2"}},
                ])
            else:
                expanded.append(source)
        return {"sources": self._dedupe_bindings(expanded), "flatten": True}

    def _fill_read_pair(
        self,
        inputs: Dict[str, Dict[str, Any]],
        assets: Sequence[Dict[str, Any]],
        assets_by_id: Dict[str, Dict[str, Any]],
        steps: Dict[str, Dict[str, Any]],
    ) -> None:
        seed = inputs.get("read1") or inputs.get("read2")
        if not seed:
            return
        scalar_sources = self._binding_sources(seed)
        if len(scalar_sources) != 1:
            return
        source = scalar_sources[0]
        if source.get("asset_id"):
            pair = self._asset_pair(assets_by_id.get(source["asset_id"]), assets)
            if pair:
                by_mate = {item.get("mate"): item for item in pair}
                if by_mate.get("r1"):
                    inputs["read1"] = {"asset_id": by_mate["r1"]["asset_id"]}
                if by_mate.get("r2"):
                    inputs["read2"] = {"asset_id": by_mate["r2"]["asset_id"]}
            return
        origin = source.get("from") or {}
        origin_step = steps.get(str(origin.get("step_id") or "")) or {}
        if str(origin_step.get("tool_id") or "") in {"fastp_paired_end", "trim_galore"}:
            inputs["read1"] = {
                "from": {"step_id": origin["step_id"], "output": "trimmed_r1"}
            }
            inputs["read2"] = {
                "from": {"step_id": origin["step_id"], "output": "trimmed_r2"}
            }

    @staticmethod
    def _asset_pair(
        seed: Optional[Dict[str, Any]], assets: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not seed:
            return []
        keys = ("sample_id", "sample_accession", "run_accession", "individual_accession")
        identity = next((key for key in keys if seed.get(key)), None)
        if not identity:
            return []
        candidates = [
            asset
            for asset in assets
            if asset.get(identity) == seed.get(identity)
            and asset.get("sample_role") == seed.get("sample_role")
            and asset.get("mate") in {"r1", "r2"}
        ]
        by_mate = {asset.get("mate"): asset for asset in candidates}
        return [by_mate[mate] for mate in ("r1", "r2") if mate in by_mate]

    def _augment_literals(
        self,
        external: List[Dict[str, Any]],
        internal: Sequence[Dict[str, Any]],
        assets: Sequence[Dict[str, Any]],
    ) -> None:
        paired = any(asset.get("mate") == "r2" for asset in assets)
        assets_by_id = {
            str(asset.get("asset_id") or ""): asset for asset in assets
        }
        dedup_steps = {
            str((binding.get("from") or {}).get("step_id") or "")
            for step in internal
            for binding in (step.get("inputs") or {}).values()
            if (binding.get("from") or {}).get("output") == "sorted_dedup_bam"
        }
        # Real sample accession per step: fastp binds read assets directly, so its
        # sample number comes from the bound asset; downstream steps (bwa, samtools)
        # read from an upstream step and inherit that step's sample number.
        sample_by_step: Dict[str, str] = {}
        for step in external:
            step_id = str(step.get("step_id") or "")
            tool_id = str(step.get("tool_id") or "")
            inputs = step.get("inputs") or {}
            sample_accession = self._resolve_step_sample(
                inputs, assets_by_id, sample_by_step
            )
            if sample_accession:
                sample_by_step[step_id] = sample_accession
            if tool_id in {
                "fastp_paired_end",
                "bwa_mem_paired",
                "samtools_alignment_processing",
            }:
                # The required WDL sample_id must carry the real sample number
                # (e.g. HRS024297). Fall back to step_id only when the asset has
                # no resolvable sample, so a required input is never empty.
                inputs.setdefault(
                    "sample_id", {"value": sample_accession or step_id}
                )
            if tool_id == "samtools_alignment_processing" and step_id in dedup_steps:
                inputs["remove_duplicates"] = {"value": True}
            if tool_id in {"rsem_quantification", "featurecounts_gene_counting"}:
                inputs.setdefault("paired_end", {"value": paired})
            if tool_id == "multiqc":
                inputs.setdefault("report_id", {"value": step_id})

    @staticmethod
    def _resolve_step_sample(
        inputs: Dict[str, Any],
        assets_by_id: Dict[str, Dict[str, Any]],
        sample_by_step: Dict[str, str],
    ) -> Optional[str]:
        # Prefer a directly bound read asset's sample number.
        for binding in inputs.values():
            if not isinstance(binding, dict):
                continue
            asset_id = binding.get("asset_id")
            if asset_id:
                asset = assets_by_id.get(str(asset_id)) or {}
                accession = asset.get("sample_id") or asset.get("sample_accession")
                if accession:
                    return str(accession)
        # Otherwise inherit from the upstream step feeding this one.
        for binding in inputs.values():
            if not isinstance(binding, dict):
                continue
            source_step = str((binding.get("from") or {}).get("step_id") or "")
            if source_step in sample_by_step:
                return sample_by_step[source_step]
        return None

    def _augment_multiqc(self, chain: List[Dict[str, Any]]) -> None:
        reports: List[Dict[str, Any]] = []
        for step in chain:
            execution_id = str(step.get("tool_id") or "")
            resolved = self.by_execution_id.get(execution_id)
            if not resolved:
                continue
            _internal_id, contract = resolved
            if execution_id == "multiqc":
                if reports:
                    step.setdefault("inputs", {})["qc_files"] = {
                        "sources": self._dedupe_bindings(reports),
                        "flatten": True,
                    }
                continue
            for output in contract.get("report_outputs") or []:
                reports.append({
                    "from": {
                        "step_id": step.get("step_id"),
                        "output": output,
                    }
                })

    def _validate_binding(
        self,
        step_id: str,
        input_name: str,
        binding: Any,
        spec: Dict[str, Any],
        known_steps: Dict[str, Dict[str, Any]],
        asset_ids: set,
        errors: List[str],
    ) -> None:
        if not isinstance(binding, dict):
            errors.append(f"{step_id}.{input_name} binding must be an object")
            return
        if "sources" in binding:
            sources = binding.get("sources")
            if not spec.get("array"):
                errors.append(f"{step_id}.{input_name} is not an array input")
            if binding.get("flatten") is not True:
                errors.append(f"{step_id}.{input_name}.flatten must be true")
            if not isinstance(sources, list) or not sources:
                errors.append(f"{step_id}.{input_name}.sources must be non-empty")
                return
            for source in sources:
                self._validate_scalar_binding(
                    step_id, input_name, source, spec, known_steps, asset_ids, errors
                )
            return
        if spec.get("array"):
            errors.append(f"{step_id}.{input_name} must use sources for an array input")
        self._validate_scalar_binding(
            step_id, input_name, binding, spec, known_steps, asset_ids, errors
        )

    def _validate_scalar_binding(
        self,
        step_id: str,
        input_name: str,
        binding: Any,
        spec: Dict[str, Any],
        known_steps: Dict[str, Dict[str, Any]],
        asset_ids: set,
        errors: List[str],
    ) -> None:
        if not isinstance(binding, dict):
            errors.append(f"{step_id}.{input_name} scalar binding must be an object")
            return
        kinds = [key for key in ("asset_id", "from", "value") if key in binding]
        if len(kinds) != 1:
            errors.append(f"{step_id}.{input_name} must use exactly one binding kind")
            return
        if "asset_id" in binding:
            if str(binding.get("asset_id") or "") not in asset_ids:
                errors.append(f"{step_id}.{input_name} references unknown asset_id")
            return
        if "value" in binding:
            value = binding.get("value")
            expected = str(spec.get("type") or "")
            valid = (
                (expected.startswith("String") and isinstance(value, str))
                or (expected.startswith("Boolean") and isinstance(value, bool))
                or (
                    expected.startswith("Int")
                    and isinstance(value, int)
                    and not isinstance(value, bool)
                )
                or (not expected)
            )
            if not valid:
                errors.append(
                    f"{step_id}.{input_name} literal does not match Knowledge Card type {expected}"
                )
            return
        source = binding.get("from") or {}
        source_step = str(source.get("step_id") or "")
        source_output = str(source.get("output") or "")
        source_contract = known_steps.get(source_step)
        if not source_contract:
            errors.append(f"{step_id}.{input_name} references unknown upstream step")
            return
        if source_output not in (source_contract.get("outputs") or {}):
            errors.append(
                f"{step_id}.{input_name} references undeclared Knowledge Card output {source_output}"
            )
            return
        accepted = set(spec.get("accepted_sources") or [])
        if accepted:
            source_key = f"{source_contract['execution_tool_id']}.{source_output}"
            if source_key not in accepted:
                errors.append(
                    f"{step_id}.{input_name} rejects Knowledge Card source {source_key}"
                )

    @staticmethod
    def _binding_sources(binding: Dict[str, Any]) -> List[Dict[str, Any]]:
        sources = binding.get("sources") if isinstance(binding, dict) else None
        return list(sources) if isinstance(sources, list) else [binding]

    @staticmethod
    def _dedupe_bindings(bindings: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for binding in bindings:
            if binding not in result:
                result.append(binding)
        return result
