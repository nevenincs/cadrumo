---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3fcdbe343a5cc9e93d1d83a681a11e7afc45b14dde51cdf7032de2142e2e0a31'
step_id: 'S75'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Relocate the diagnostics-discarding calculate wrapper to the shared test-support home, since its twenty-five call sites across ten modules are all tests while the operator-facing CLI uses the diagnostics variant, and a production entry point that drops non-blocking source advisories is the hazard rather than its disuse; the move carries roughly twenty-five type imports and touches peer-visible test modules, so it needs a machine that can run those suites.

## Scope

- `src/cadrumo/application/modelo/calculation_actions.py`
- `src/cadrumo/tests`

## Changes

- `A` `src/cadrumo/tests/bucket_aggregation_calculate.py`
- `M` `src/cadrumo/application/modelo/calculation_actions.py`
- `M` `src/cadrumo/application/modelo/_calculation_source_staging.py`
- `M` nine test modules under `application/{modelo,aggregation,calculations}/tests`
- `M` `dev/ci/tests/test_ledger_scale_benchmark.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1041 -> 1040,
  exact 413 -> 412; the wrapper is no longer reported
- `verify:` `python -m dev.quality.unreachable_module_ratchet`,
  `... docstring_reference_ratchet` and `... secure_store_write_path` all exit 0
- `verify:` `pytest .../test_derived_aggregate_override_real_path.py
  .../test_modelo_720_foreign_asset_producer_join.py` 7 passed
- `verify:` `ruff check` and `ty check` clean across every changed module

## Notes

Production now has ONE way into the bucket source mesh, and it returns the
diagnostics with the revision rather than beside it. The deleted wrapper's
hazard was its existence rather than its disuse: the shorter of two adjacent
names is the one a future caller reaches for, and it was the one that silently
dropped the advisories.

The shim forwards `**kwargs` rather than restating twenty-one parameters. A
second copy of the calculate signature is a second declaration of the contract
that can drift from the real one while still type-checking, and it would have
dragged twenty-one production type imports into test support. The wrapper's own
filing-repository default turned out to be redundant: the diagnostics variant
resolves the same default itself, so the delegation is exact.

Two failures were investigated and neither is this step's.
`test_modelo_349_refuses_intracom_ledger_rows_without_operator_rows` fails
identically against `git show HEAD:` copies of both changed files.
`test_derived_aggregate_override_real_path.py` first failed with
`LedgerEvidenceRecaptureRefusedError is missing a declared ErrorCode registry
entry` -- a peer was mid-write across `action_errors.py` and
`_domain_part2.py`, exactly the concurrency the error text names. It passed once
their tree settled.
