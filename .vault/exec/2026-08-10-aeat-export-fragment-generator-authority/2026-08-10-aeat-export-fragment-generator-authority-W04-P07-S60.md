---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:292c8e5befafd2ded34f3d06082bafb19ab2b0376bc911be25761d4e167d3a3c'
step_id: 'S60'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-11-aeat-export-fragment-generator-authority-s60-producer-projection-address-review-audit]]"
---
# Close the S19-exposed producer and projection-address gaps by adding the distinct taxpayer tax-id producer and replacing activity-specific DP30302 module identities with exact annual-Orden module ordinals, with no alias or compatibility reader

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

The shared worktree committed the production and plan declaration while review was running. This record preserves that delivered history and carries only the corrected direct proofs and lifecycle closure. No compatibility facade, alias, legacy reader, or English `VAT` identifier was introduced. No production `module_identity`, alias, default, normalization, raw mapping, compatibility reader, or prohibited test double remains in the audited path.

### Reconciliation of the parallel execution

This step was executed twice in parallel on diverged history. Both executions reached the same two answers — a distinct closed taxpayer tax-ID producer key resolved only from immutable taxpayer identity in the filing producer snapshot, and DP30302 module projection addressed by validated annual-Orden ordinals with strict refusal of the retired `module_identity` shape. Neither introduced an alias, default, normalization, raw mapping or compatibility reader.

The second execution additionally proved that taxpayer and presenter identifiers cannot collapse or fall back to one another. That property is the point of splitting the producer key at all — a fallback would silently file the presenter's NIF as the taxpayer's — so its proof is retained. Nothing else from the second execution was absent here, and no behaviour was lost in reconciling them.
