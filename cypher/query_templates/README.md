# Query Templates

## 1. Purpose

This directory contains reusable Cypher query templates for the current biomedical data-tool knowledge graph prototype.

The templates are designed to support:

- tool retrieval
- workflow retrieval
- data lineage tracing
- downstream tool recommendation
- combined filtering queries
- workflow path exploration

These templates are intended as the first query layer for future agent-oriented access.

---

## 2. Query Categories

### 2.1 Basic retrieval
Basic retrieval templates answer direct lookup questions such as:
- which tools accept a given input format
- which tools produce a given output format
- which workflows exist
- which tools are used by a workflow

### 2.2 Recommendation-oriented queries
Recommendation queries support:
- next possible tools for a current format
- candidate workflows from a current format
- possible downstream outputs from a current state

### 2.3 Combined filtering queries
Combined queries allow filtering by multiple conditions, such as:
- function + format
- multiomics + platform
- workflow + output format
- cohort + format + stage

### 2.4 Workflow path queries
Workflow path queries support:
- tracing ordered tool chains
- inspecting next-tool relations
- finding start or end tools in workflow-like chains

---

## 3. Current Graph Assumptions

The current templates are based on the following graph implementation rules:

- Workflow is represented as a `Tool`
- Workflow type is indicated by:
  - `(Tool)-[:IS_TOOL_TYPE]->(ToolType {name:'workflow'})`
- `INPUT` and `OUTPUT` point to shared `Format` nodes
- `NEXT_TOOL` is currently represented globally between Tool nodes
- `USES_TOOL` represents workflow membership
- `DERIVED_FROM` represents data lineage
- `SUBCLASS_OF` is used for cohort hierarchy

---

## 4. Template Index

| File | Category | Main Question |
|------|----------|---------------|
| `find_tools_by_input_format.cypher` | Basic | Which tools accept a given input format? |
| `find_tools_by_output_format.cypher` | Basic | Which tools produce a given output format? |
| `list_workflows.cypher` | Basic | What workflows exist in the graph? |
| `find_workflows_by_input_format.cypher` | Basic | Which workflows accept a given input format? |
| `find_tools_used_by_workflow.cypher` | Basic | Which tools are used by a given workflow? |
| `trace_next_tool_chain.cypher` | Workflow | What tool order relations exist? |
| `find_tool_input_output.cypher` | Basic | What are the input and output formats of a tool? |
| `recommend_tools_by_current_format.cypher` | Recommendation | What tools can be used next for a given format? |
| `find_data_format_stage.cypher` | Basic | What is the format and stage of a data instance? |
| `trace_data_lineage.cypher` | Basic | What is the upstream lineage of a data instance? |
| `find_data_by_cohort.cypher` | Basic | What data belong to a given cohort? |
| `trace_cohort_hierarchy.cypher` | Basic | What is the hierarchy of a cohort? |
| `find_tools_by_function.cypher` | Basic | Which tools support a given function? |
| `find_tools_by_multiomics.cypher` | Basic | Which tools apply to a given multiomics domain? |
| `find_tools_by_platform.cypher` | Basic | Which tools support a given platform? |

### Second batch
| File | Category | Main Question |
|------|----------|---------------|
| `recommend_workflows_by_current_format.cypher` | Recommendation | Which workflows are candidates for a current format? |
| `recommend_next_tools_via_output_match.cypher` | Recommendation | Which tools can follow a tool based on output-input format match? |
| `find_tools_by_function_and_input.cypher` | Combined | Which tools satisfy both function and input format? |
| `find_tools_by_multiomics_and_platform.cypher` | Combined | Which tools satisfy both multiomics and platform? |
| `find_workflows_by_input_and_output.cypher` | Combined | Which workflows match a required input and output format? |
| `find_data_by_cohort_format_stage.cypher` | Combined | Which data match a cohort, format, and processing stage? |
| `find_workflow_start_tools.cypher` | Workflow | Which tools are likely workflow starts? |
| `find_workflow_end_tools.cypher` | Workflow | Which tools are likely workflow ends? |
| `trace_paths_from_input_format_to_output_format.cypher` | Workflow | What tool paths connect one format to another? |

---

## 5. Usage Notes

### 5.1 Replace hard-coded values
Most templates use hard-coded example values such as:
- `FASTQ`
- `BAM`
- `RNASeq_DE_Analysis_Workflow`
- `variant_analysis`

These should be replaced dynamically when used by applications or agents.

### 5.2 Current prototype limitation
Since `NEXT_TOOL` is currently global and not workflow-scoped:
- path-related queries reflect current known tool order relations in the graph
- they do not yet guarantee workflow-local ordering semantics

### 5.3 Recommendation usage
Recommendation templates should currently be interpreted as:
- graph-based candidate suggestion
- not strict execution planning
- not yet full provenance-aware workflow composition

---

## 6. Suggested Next Layer

These templates can later be wrapped into:

- Python query functions
- API endpoints
- NL2Cypher prompt templates
- GraphRAG retrieval units
- agent tool functions