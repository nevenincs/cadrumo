---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:2aff85f840970f9bc4efa4d3c366a22284771dcc4c0fc10c60498e03804dbc66'
step_id: 'S115'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Enrol the campaign's two new gates in the aggregate suite, delete a never-taken cache door, and classify the registry cache-invalidation seams

## Scope

- `dev/quality/unused_symbol_ratchet.toml`

## Changes

- `M` `dev/quality/suite.py`
- `M` `src/cadrumo/application/provisioning.py`
- `M` `dev/audit/reachability_classification.toml`
- `M` `dev/quality/unused_symbol_ratchet.toml`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests dev/quality/tests/test_orphan_test_records_agree.py -n0` -> `pass`
- `verify:` `uv run --no-sync python -m pytest dev/quality/tests/test_suite_gate_table.py -n0` -> `fail`
- `verify:` `uv run --no-sync python -m dev.quality.docstring_reference_ratchet` -> `pass`

## Notes

Both gates this campaign added carried a justfile recipe and no row in
`dev.quality.suite.GATES`, so `just check-all` never invoked either. Their own
test suites were green throughout, which is exactly how the defect stays
invisible: an unaggregated gate is not a weaker gate, it is an unrun one. The
table already carried a comment recording a previous instance of the same
defect, and this repeated it twice.

`test_every_static_check_recipe_is_either_aggregated_or_declared_exempt` still
fails on `check-modelo-action-denominator`, which belongs to a concurrent
migration, and `test_doc_privacy` fails on hostnames in
`.github/ci-control-plane.md`. Neither is this campaign's, and both are left
for their owners.

`clear_ollama_vision_probe_cache` was deleted rather than classified. Its own
docstring offered it "where a test needs the next call to reach the endpoint
again" and no test ever took it, while the same docstring explains that keying
the cache on the endpoint is what isolates a suite standing up its own reader,
with a TTL behind that. The affordance it named was already provided twice over.
