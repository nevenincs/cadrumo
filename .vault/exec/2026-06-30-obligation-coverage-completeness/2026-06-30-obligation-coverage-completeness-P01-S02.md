---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S02'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Implement the build_obligation_coverage reconciliation

## Scope

- `src/aeat/application/overview/_coverage.py`.`
- `src/aeat/application/overview/_coverage.py`

## Description

- Add the `_coverage` module with `CoverageAdviceReason`, `AdvisedObligation`,
  and `ObligationCoverageReport` typed models.
- Implement `build_obligation_coverage`, which walks the full
  `registry_modelo_codes()` set and assigns each modelo to exactly one
  disposition: surfaced, confidently excluded (`NOT_APPLICABLE` /
  `ATTRIBUTION_PASS_THROUGH`), advised (`APPLICABLE` but window-less, or
  `INCOMPLETE`), or out of scope.
- Lazily import `registry_modelo_codes` inside the function to avoid an
  import-time coupling to the modelo package.

## Outcome

The classification is total by construction, so no registry modelo can be silently
absent. A functional check confirmed the partition equals the registry set (30/30)
and that Modelo 190 lands in `advised` with the window-missing reason.

## Notes
