---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e2e30a54bcb737b049306f641fc4ba63ee51afdae93163336ef74c5af71c8cb8'
step_id: 'S149'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S149`

## Scope

- `P05.S149`

## Changes

- `M` `src/cadrumo/application/ledger/identity_roles.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S149.md`

## Notes

- `uv run --no-sync ruff check src/cadrumo/application/ledger/identity_roles.py` emitted `All checks passed!` (exit 0); `ruff format --check` emitted `1 file already formatted` (exit 0).
- A direct four-outcome probe of absent, checksum-unverified, positively evidenced, and ambiguous identities emitted `direct identity outcomes: absent/unverified/anchored/ambiguous` (exit 0).
- The exact callable-size probe measured `src/cadrumo/application/ledger/identity_roles.py::resolve_counterparty_identity` at 159 lines against the default 180 (exit 0); no baseline or policy changed.
- `uv run --no-sync pytest --collect-only -q src/cadrumo/application/ledger/tests/test_identity_roles.py` and its target run both stopped before collection (exit 4) at peer-owned `src/cadrumo/adapters/persistence/storage/_secure_object_namespaces.py:12`: `SensitivityClass` is absent from `cadrumo.core.classification`.
