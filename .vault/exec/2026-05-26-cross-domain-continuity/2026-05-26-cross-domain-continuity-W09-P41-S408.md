---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S408'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-S359-A compute activity-start Art. 109 coverage per payment period instead of relying only on the declared profile fact

## Scope

- `closed by b645c8df3: introduced a period-scoped Art. 109 activity-income coverage resolver that derives the 70 percent income/withholding test from current-period ledger and observation evidence when numerator and denominator are provable`
- `while still failing closed when evidence is absent or insufficient`
- `pinned by real period-evidence tests for Modelo 130 coverage derivation`
- `src/aeat/application/modelo/ src/aeat/domain/deadlines/ src/aeat/_data/registry/aeat/modelos/130/`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `b645c8df3c` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
