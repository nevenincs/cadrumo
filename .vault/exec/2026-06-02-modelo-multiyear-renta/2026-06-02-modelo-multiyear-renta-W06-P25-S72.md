---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S72'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enroll M721 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer)

## Scope

- `src/aeat/_data/registry/aeat/authorization.toml`

## Description

- Enroll Modelo 721 through the directory-mode authorization manifest.
- Classify the evidence as `threshold_continuity` for the 2023 and 2024 annual contexts.
- Remove the stale calculation-surface link from the registry and keep Modelo 721 on the non-calculation informativa path.
- Remove the retired `ley-11-2021:da-10` anchor from Modelo 721 model/revision/construct legal refs; the legal corpus still retains it only as enabling-statute context.

## Outcome

- Satisfied by `authorization.d/721.toml` plus the existing two-year repository/advisory enrollment test in `src/aeat/application/calculations/tests/test_modelo_721_cripto_extranjero_fidelity.py`.
- The authorization gate accepts the 2023 and 2024 manifest year-set.
- The registry test now asserts Modelo 721 has threshold parameters but no `surface = "calculation"` application link.

## Notes

- S69, S70, and S71 now close the stale engine/calculation path as no-calculation threshold-continuity work.
- The remaining Modelo 721 prior-year row-set binding question is tracked by S89.
- Verified in the final scoped run by `uv run --no-sync pytest -q -n 0 ...`, which passed the targeted Modelo 720/721 tests.
