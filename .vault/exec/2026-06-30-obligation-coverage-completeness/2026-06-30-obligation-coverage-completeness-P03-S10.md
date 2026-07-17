---
tags:
  - '#exec'
  - '#obligation-coverage-completeness'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-06-30-obligation-coverage-completeness-plan]]"
---

# Bind the reconciliation to the AEAT universe (registry union unmodeled) and advise unmodeled obligations with the REGISTRY_UNMODELED reason.

## Scope

- `src/aeat/application/overview/_coverage.py`

## Description

- Bind `build_obligation_coverage` to the AEAT universe (registry ∪ unmodeled), not
  the registry alone.
- Add the `REGISTRY_UNMODELED` advice reason and classify universe-but-not-registry
  obligations under it before the applicability call.
- Update the completeness invariant test to bind to the universe and assert every
  unmodeled obligation surfaces as advised (registry-unmodeled).

## Outcome

A recognized obligation AEAT expects but the app never modeled now surfaces as advised
rather than being invisible — the external-universe gate. Verified end-to-end: a real
calendar build advises 117/216/296 as `registry_unmodeled` alongside 190
(`applicable_window_missing`); the partition stays total over the universe.

## Notes
