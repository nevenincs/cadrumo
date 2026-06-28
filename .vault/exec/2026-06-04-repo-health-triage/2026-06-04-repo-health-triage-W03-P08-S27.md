---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P08.S27'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P08.S27 - Extract modelo binding-resolution service

Scope: execute the modelo application orchestration decomposition step for calculation binding resolution.

## Description

- Add `_binding_resolution.py` as the application-layer binding assembly service for calculation.
- Move profile, borrador, relation, previous-filing override, bound-casilla, and informational-period input assembly behind the new service.
- Keep IVA wallet reconciliation in `_actions.py`; that remains the next dedicated W03.P08 slice.
- Preserve the existing calculation action contract and bucket-aggregation bound-casilla projection behavior.

## Outcome

- `_actions.py` dropped from 4,632 lines to 4,278 lines in the current worktree.
- `_binding_resolution.py` landed at 347 lines.
- The moved behavior remains covered by focused profile, real-profile, borrador, previous-filing override, and declaration-period tests.

## Notes

- Verification:
  - `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/_binding_resolution.py src/aeat/application/modelo/test_actions.py src/aeat/application/modelo/test_source_mesh_calculation.py src/aeat/application/modelo/test_profile_binding.py src/aeat/application/modelo/test_borrador_binding.py`
  - `uv run --no-sync pytest src/aeat/application/modelo/test_profile_binding.py src/aeat/application/modelo/test_profile_binding_real_path.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_previous_filing_casilla_override.py src/aeat/application/modelo/test_declaration_period_binding.py -q`
- Discovered edge:
  - `uv run --no-sync pytest src/aeat/application/modelo/test_profile_binding.py src/aeat/application/modelo/test_profile_binding_real_path.py src/aeat/application/modelo/test_borrador_binding.py src/aeat/application/modelo/test_previous_filing_casilla_override.py src/aeat/application/modelo/test_declaration_period_binding.py src/aeat/application/modelo/test_source_mesh_calculation.py -q` failed in two `test_source_mesh_calculation.py` cases before the moved binding-resolution helper is reached. The Renta expense source resolver raises `aggregation.renta_ledger.errors.invoice_bucket_mismatch` while building source resolution.
