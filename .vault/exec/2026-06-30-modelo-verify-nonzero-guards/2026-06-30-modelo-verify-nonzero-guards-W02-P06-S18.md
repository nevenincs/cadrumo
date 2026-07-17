---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S18'
related:
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# Investigate the M714 base-imponible-to-base-liquidable edge against the minimo exento mechanics (a filer obligated to file on gross assets at or above EUR 2M can legitimately have a positive base-imponible and a zero or floored base-liquidable below the EUR 700000 default exemption), decide whether a false-positive-free ADVISORY condition exists, and either author it with legal_refs ley-19-1991:art-28 plus a two-tier test pair or record the wontfix rationale as a vault audit finding

## Scope

- `src/aeat/_data/registry/aeat/modelos/714/revisions/2021-y-siguientes/verification_expectations/0001-verification_predicates.toml`

## Description

- Re-confirm the M714 `patrimonio.base-imponible` and `patrimonio.base-liquidable` casillas are both `input_kind = "manual"` with no formula linkage, against `casillas/0001-casillas.toml`.
- Read the bundled authoritative corpus for Ley 19/1991 art. 28 and confirm the minimo exento general (EUR 700.000, CCAA-variant) text.
- Confirm no parameter or formula encoding the minimo exento exists anywhere under the M714 `2021-y-siguientes` revision tree.
- Confirm `KNOWN_VERIFICATION_PREDICATE_OPERATORS` carries no threshold-comparison or subtraction-against-a-parameter operator that could express "base-imponible minus the minimo exento is still positive".
- Decide: no false-positive-free ADVISORY condition is expressible for this edge with the current registry data and DSL; record the wontfix rationale as a vault audit finding rather than authoring a guard.
- Persist the rationale and the prerequisite (model the minimo exento as a parameter plus formula) in `.vault/audit/2026-06-30-modelo-verify-nonzero-guards-audit.md`.
- Strengthen `test_modelo_714_riskier_edges_remain_unguarded` in `src/aeat/domain/calculations/registry/tests/test_modelo_714_registry.py` to cite the audit document and the legal grounding for the deferral, locking the deliberate non-guard.
- Update the `0001-verification_predicates.toml` header comment to reference the audit document.

## Outcome

Decision: **documented non-guard (wontfix-for-now)**. The `base-imponible -> base-liquidable` edge is not guardable today: the minimo exento (Ley 19/1991 art. 28, EUR 700.000 default, CCAA-variant) legitimately floors `base-liquidable` at zero for any filer near the threshold while the filer remains obligated to file (gross assets >= EUR 2M), and neither a parameter, a formula, nor a casilla in the registry encodes that exemption amount, so no existing `implies_nonzero`-shaped predicate can exclude the legitimate case from a genuine omission. The rationale, the legal grounding, and the concrete prerequisite (model the minimo exento parameter and formula) are persisted in the `modelo-verify-nonzero-guards` audit document; the existing `test_modelo_714_riskier_edges_remain_unguarded` regression now asserts the predicate id's continued absence with a docstring citing the audit. No new predicate was authored; this is consistent with the no-silent-under-declaration discipline because the alternative (a guard with a structurally guaranteed false-positive rate) would have trained operators to ignore the advisory.

## Notes

No incidents. No peer WIP conflicts: the `verification_expectations/` directory and `test_verification_m714_advisory.py` were untracked sibling-agent WIP for the Wave W01 SAFE guard, left undisturbed; only the riskier-edges test docstring and the predicate file's header comment were edited (both additive, non-conflicting with the sibling's content). No engine, schema, or operator change was made -- this Step is registry-investigation plus documentation only, per the ADR's "no implementation in this feature beyond the recommended guards" constraint. Full focused test run (`test_modelo_714_registry.py`, `test_verification_m714_advisory.py`): 25 passed.
