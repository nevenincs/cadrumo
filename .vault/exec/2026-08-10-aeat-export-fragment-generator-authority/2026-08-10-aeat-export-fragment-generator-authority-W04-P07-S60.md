---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:d2bb1a8b0dbaa9ea494bee49d5d6dd5afbf9b98a7e60086d87e7cf6ff96d73fc'
step_id: 'S60'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-11-aeat-export-fragment-generator-authority-s60-producer-projection-address-review-audit]]"
---
# S60 producer and projection address remediation

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/calculations/registry/`

## Description

- Add the distinct `taxpayer.tax_id` producer and resolve it from the filing snapshot taxpayer identity.
- Replace activity-specific simplified-regime module identity with the closed module ordinal address.
- Reject coercive module ordinals and the retired `module_identity` field without an alias or tolerant reader.
- Prove exact ordinal projection, missing higher ordinals, producer exhaustiveness, and Spanish IVA naming conformance.

## Outcome

The filing producer vocabulary now distinguishes taxpayer NIF from presenter NIF. The simplified-regime projection address is the exact integer module ordinal from 1 through 7, while annual Orden identity and order validation remains upstream of ordinal lookup. The first module projects its exact value and an absent seventh module projects `None`.

The implementation was delivered in commits `061223738a` and `62d257486d`. The focused implementation lane passed 78 tests; the corrected exact ordinal proof passed 12 tests. Scoped Ruff and BasedPyright passed, the Spanish IVA conformance lane passed five tests, and the real `config profile list` console path succeeded.

Formal review approved the step with no unresolved findings after the initial weak positive-ordinal assertion was replaced by an exact ordered-field assertion.

## Notes

The shared worktree committed the production and plan declaration while review was running. This record preserves that delivered history and carries only the corrected direct proofs and lifecycle closure. No compatibility facade, alias, legacy reader, or English `VAT` identifier was introduced.
