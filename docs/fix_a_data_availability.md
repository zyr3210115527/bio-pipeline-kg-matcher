# Fix A: Custom Tool-Chain Data Availability

## Outcome

`query_data_availability` now accepts exactly one of the existing `pipeline_ids` argument or a new `steps` argument. The existing registered-pipeline path and `data-availability/v1` field meanings are unchanged.

For `steps`, the MCP server first calls the existing `WorkflowComposer._validate_custom_steps`. A failed closed-set, slot, artifact, ordering, or NEXT check returns MCP invalid parameters (`-32602`) and does not query data. No validation rule was changed.

After validation, external `asset_role` bindings and unbound required File inputs are normalized with the composer's existing `_canonical_asset_role` / `_role_for_input` behavior. Execution-managed references are excluded. The resulting contract roles are mapped to the matcher's existing file-role vocabulary, and CSV/Neo4j/compare backends reuse the same `_role_of_file`, `_role_satisfies`, `_paired_fastq_groups`, cohort filtering, and file filtering logic.

New response fields for the custom path are:

- `request_mode: custom_steps`
- `required_asset_roles`
- `required_data_roles`

The registered path adds only `request_mode: pipeline_ids`.

## Verification

| Check | Result |
|---|---|
| Valid six-step WES chain | `available`; derived `fastq_file` / `fastq`; returned complete dataset combinations |
| Unregistered tool | MCP `-32602`, existing `未知 tool_id` validator evidence |
| Valid chain with no matching cohort | `not_available`, no dependency error |
| Existing `pipeline_ids` call | Existing schema and behavior retained |
| Full unit suite | 72 tests OK, including the original 68; 3 real integrations skipped under their existing gate |

Warm CSV calls for the six-step WES request, after one warm-up, were `164.7, 168.8, 174.7, 176.0, 170.3, 173.5, 167.8, 168.4, 168.8, 177.3` ms. Median was `169.55` ms, minimum `164.7` ms, maximum `177.3` ms.

The current pre-Stage-D catalog has one generic `fastp.raw_fastq_read` input, so the same chain currently derives `fastq_file`. Once Stage D publishes the authorized named R1/R2 slots atomically, this interface reports those more specific roles without a second role-inference implementation.
