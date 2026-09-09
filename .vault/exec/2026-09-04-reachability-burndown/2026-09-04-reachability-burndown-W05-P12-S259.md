---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:1ef64bf4711b60c0e7c2ea5f0e475d08f6880371ed4f44696413ff1c7d4da5a7'
step_id: 'S259'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Move the conformance and secure-replay request DTOs from the shipped proof contract into the development proof owner now that no production adapter consumes them; remove request-only production tests and exports without aliases, retain shared proof evidence contracts, run focused gates, remeasure exact reachability, update the cadence reference, and write the Step Record.

## Scope

- `filing export proof request DTOs and request-only tests`
- `development proof owner`
- `focused gates`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/filing/export_proof.py`
- `M` `dev/registry/filing_export_proof.py`
- `M` `src/cadrumo/application/filing/tests/test_export_proof_contracts.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/export_proof.py dev/registry/filing_export_proof.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/registry/tests/test_filing_export_two_channel_proof.py dev/registry/tests/test_filing_export_live_proof.py dev/registry/tests/test_pinned_conformance_vector.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit remains campaign-red at 31 unreachable modules and 287 unused symbols. Both request DTO findings disappeared from production; the unchanged aggregate symbol count reflects newly exposed downstream residue elsewhere in the live tree rather than retained request aliases.
