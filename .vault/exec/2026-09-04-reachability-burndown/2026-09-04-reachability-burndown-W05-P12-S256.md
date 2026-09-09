---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:fa4717f10cc287021881db148616c963c4a776a7a216d8346f33c303491ddd92'
step_id: 'S256'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Move filing export proof execution out of the shipped application package

## Scope

- `Keep production proof DTOs and protocols used by live closure consumers`
- `relocate the dev-only conformance and secure-replay executors with their private helpers to the development authority`
- `update tests and imports without compatibility aliases`
- `run focused two-channel proof gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `M` `src/cadrumo/application/filing/export_proof.py`
- `M` `dev/registry/filing_export_proof.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/export_proof.py dev/registry/filing_export_proof.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/registry/tests/test_filing_export_two_channel_proof.py dev/registry/tests/test_filing_export_live_proof.py dev/registry/tests/test_pinned_conformance_vector.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m integration dev/registry/tests/test_filing_export_two_channel_proof.py dev/registry/tests/test_filing_export_live_proof.py dev/registry/tests/test_pinned_conformance_vector.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit remains campaign-red at 32 unreachable modules and 288 unused symbols. Moving the two development-only executors correctly exposed three retained production proof protocols as dev-only consumers, so this boundary repair increased the symbol signal from 287 to 288; the protocols remain production contracts required by the development authority and are candidates for subsequent ownership analysis, not compatibility aliases.
