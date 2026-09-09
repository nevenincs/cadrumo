---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:8a66345e66da72600b012ec7b536a41f32054ef8a7cced366a5791fd6a65bbcf'
step_id: 'S257'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Move the three filing export proof authority protocols from the shipped contract module to their sole development owner; preserve the production proof DTOs, remove production exports and unused imports without compatibility aliases, update the focused proof lanes, remeasure exact reachability, update the cadence reference, and write the Step Record.

## Scope

- `src/cadrumo/application/filing/export_proof.py`
- `dev/registry/filing_export_proof.py`
- `focused filing export proof tests`
- `exact reachability`
- `cadence reference`
- `Step Record`

## Changes

- `M` `src/cadrumo/application/filing/export_proof.py`
- `M` `dev/registry/filing_export_proof.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/export_proof.py dev/registry/filing_export_proof.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/registry/tests/test_filing_export_two_channel_proof.py dev/registry/tests/test_filing_export_live_proof.py dev/registry/tests/test_pinned_conformance_vector.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m integration dev/registry/tests/test_filing_export_two_channel_proof.py dev/registry/tests/test_filing_export_live_proof.py dev/registry/tests/test_pinned_conformance_vector.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit remains campaign-red at 32 unreachable modules and 287 unused symbols. Moving three dev-only protocols removed their production signals but exposed two request DTOs as the next ownership edge, producing a net reduction from 288 to 287; those live findings remain for the next owning-mechanism Step.
