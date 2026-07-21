---
tags:
  - '#exec'
  - '#mcp-protocol-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-07-08-mcp-protocol-hardening-plan]]"
---

# Update the affected per-verb output schemas in lock-step with the thinned payload shapes

## Scope

- `src/aeat/entrypoints/mcp/_tools.py`

## Description

- Route `_output_schema_for` in `_tools.py` through `thin_output_schema(command_key, schema)` so a thinned verb's declared output schema drops the moved bulk-array property and declares the two summary markers (`{key}_resource` string, `{key}_count` integer) in lock-step with `thin_envelope`.
- Strip the moved property from the schema's `required` list and prune any `$defs` entry orphaned by the removed property (iterated to a fixpoint over `$ref` reachability, so a shared definition is always kept).

## Outcome

- The advertised output schema now matches the emitted thinned `structuredContent`, and the reduction is real (not just a marker swap): `modelo.work.calculate` 8843→7169, `modelo.work.observations` 3133→1338, `ledger.evidence.list` 2219→533 chars, with the orphaned `ObservationPayload` `$def` pruned.
- The static size-budget gate (`test_result_size_budget.py`, P04.S17) measures the thinned shape and stays green; `test_thin_output_schema_strictly_shrinks_the_schema` is the anti-tautology proof that thinning reduces every thinned verb's schema.

## Notes

- The output schema describes the result model while `structuredContent` is the full envelope (a pre-existing shape the campaign did not introduce); thinning keeps the result and its schema in lock-step, which is the S16 contract, and does not touch that pre-existing envelope-vs-result framing.
