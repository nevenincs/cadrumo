---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S23'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M130 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/130.toml`

## Description

- Rebaseline stale-open M130 manifest row against the current split authorization registry.
- Ground the check with `uvx vaultspec-rag search "Modelo 130 carry forward continuity second renta year recorder captures two filing years real adapters" --type code --limit 10`.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/130.toml` already declares modelo 130 with `renta_years = [2025, 2026]`, `evidence_class = "calculation"`, and the enrolling test `test_modelo_130_multiyear_renta_enrollment.py`.
- The manifest claim matches the test's recorded distinct renta years and is enforced by `assert_enrollment_matches_manifest`.
- The original row's single-file `authorization.toml` scope was stale because the current registry uses per-modelo authorization fragments.

## Notes

- This closes the M130 manifest enrollment row only. It does not claim broader authorization fleet completeness.
