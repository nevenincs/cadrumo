---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:2dd0e44b0b93f9d21f25473a43ac27eba5395745e33655e9a73c73bae7db1b06'
step_id: 'S256'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
