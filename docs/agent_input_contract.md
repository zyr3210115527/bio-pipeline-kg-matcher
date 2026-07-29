# MCP output and agent input contract

## What is fixed

Only `route_pipeline_request` returns `tool-chain/v1`. MCP wraps that value in both
`result.structuredContent` and a JSON string in `result.content[0].text`.

The v1 core is fixed and machine-checkable, but it is a discriminated union rather
than one identical object for every request:

| Request mode | `execution_kind` | `workflow_mode` | `assets` / `tool_chain` |
|---|---|---|---|
| Standard pipeline | `tool_chain` | `standard` | Populated when matched |
| Custom atomic chain | `tool_chain` | `custom` | Populated when matched and validated |
| Capability question | `information` | `capability` | Both arrays are empty |

`ready`, `missing_assets`, `draft`, and `no_match` are states of the same
`tool_chain` branch. They do not introduce a new JSON shape. A capability answer is
the second fixed branch and is intentionally non-executable.

Other MCP tools (`health_check`, catalog listing, validation, data availability, and
rendering) have their own result schemas and do not return `agent_input`.

## Files

- `agent_input.schema.json`: schema for the object handed to the execution agent.
- `tool_chain_output.schema.json`: schema for the complete
  `route_pipeline_request` structured result.
- `agent_input.examples.json`: sanitized standard, custom, and capability examples.

Both schemas use JSON Schema Draft 2020-12. Core fields are required. Objects allow
additional properties so compatible v1 extensions can be added without breaking
existing consumers. Consumers must branch on `execution_kind`, not on array length
or the presence of optional extension fields.

## Execution rule

An execution agent may run a result only when all of these are true:

1. `execution_kind == "tool_chain"`;
2. `orchestration_ready == true`;
3. `orchestration_status == "ready"`;
4. `feasibility.status == "ready"`;
5. `extensions.contract_validation.ok == true`.

Custom `draft` is structurally valid but still requires execution-side
materialization. `information`, `missing_data`, and `no_match` must not be executed.

For paired data, preserve `asset.sample_role`, `asset.mate`, and accession fields.
Bind inputs by the exact `asset_id` or `from.step_id`/`from.output`; never infer
tumor/normal or R1/R2 from array position.

Atomic `tool_id` values are Knowledge Card `meta.id` values. Input keys and
`from.output` are Knowledge Card names. Literal inputs use `{"value": ...}`;
array inputs use `{"sources": [...], "flatten": true}`.
