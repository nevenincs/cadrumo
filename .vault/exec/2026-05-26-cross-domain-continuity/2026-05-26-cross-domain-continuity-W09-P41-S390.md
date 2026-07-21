---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S390'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# wire representante-fiscal verification predicate as the first non-M131 use site of implies_nonzero per dsl-conditional-predicate ADR

## Scope

- `runtime evaluator consults profile.ue_eee_status to skip the predicate for EEA residents documented escape hatch per ADR D2.5`
- `author refusal text via tr with locale keys es en ca hu under application.modelo.findings.representante_fiscal_required namespace`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations.toml + src/aeat/application/modelo/_actions.py + src/aeat/locales/`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `e5e3c630ea` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
