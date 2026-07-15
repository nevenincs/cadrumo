---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S359'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# R9-TOMAS-MEDIUM Art. 109 RIRPF high-withholding M130 advisory scope incomplete

## Scope

- `closed by a2dc84adc: introduced canonical irpf.art109_activity_income_withholding_ge_70pct profile fact and wizard flag`
- `removed professional_income_withholding_ge_70pct from schedule/advisory authority`
- `routed M130 deadline windows and verification advisory through the Art. 109 fact`
- `kept the professional-only field as a compatibility/model selector`
- `and pinned professional-only does-not-suppress-M130 guards`
- `grounded against BOE RD 439/2007 Art. 109 and AEAT pagos-fraccionados guidance`
- `verified by 201 focused tests`
- `ruff`
- `diff check`
- `and official source review`
- `broader test_authority.py still has unrelated synthetic legal-ref fixture failures and ty remains blocked by the shared-tree missing stubs directory`
- `src/aeat/_data/registry/aeat/modelos/130/ src/aeat/_data/registry/aeat/user_profile/schema.toml src/aeat/application/modelo/ src/aeat/domain/deadlines/`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `a2dc84adc3` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
