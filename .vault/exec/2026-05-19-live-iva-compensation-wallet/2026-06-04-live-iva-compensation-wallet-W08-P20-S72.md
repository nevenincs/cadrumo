---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S72'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---

# W08.P20.S72 three-year production-service regression

Scope: Execute W08.P20.S72 from the live IVA compensation wallet plan.

## Description

- Reuse the S68 three-year filed-history regression as the S72 production-service coverage.
- Verify the regression spans 2024, 2025, and 2026 with multiple Modelo 303 periods.
- Verify the regression persists sanitized filed observations through the secure IVA compensation history repository, reloads them, and invokes the production carry-forward projector.
- Confirm no private taxpayer fixture or live AEAT write path is involved.

## Outcome

S72 is satisfied by the new repository-backed three-year regression in `src/aeat/application/calculations/test_iva_compensation_history.py`.

Focused three-year coverage and the broader IVA compensation history plus Modelo 390 continuity gate passed.

## Notes

The test exercises production services and repository boundaries; it does not use mocks, fakes, stubs, monkeypatching, private taxpayer history, or test-local shadow services.
