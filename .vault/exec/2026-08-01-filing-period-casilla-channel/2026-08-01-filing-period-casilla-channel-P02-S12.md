---
tags:
  - '#exec'
  - '#filing-period-casilla-channel'
date: '2026-08-01'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:d46058c3885e493ee27559498e004e55501d849bcff66568be0d1963e795847e'
step_id: 'S12'
related:
  - "[[2026-08-01-filing-period-casilla-channel-plan]]"
---

# Reconcile the casilla_equals predicate text gates to family-derived membership with instructive refusals

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_verification_predicates.py`

## Description

- Enumerate every predicate the registry actually declares, and read the declared data type of each casilla they reference, before changing any gate.
- Convert the three antecedent gates from the text literal to a scalar-family test.
- Convert the two consequent gates and the date gate the same way, so the complement is closed rather than merely widened.
- Rewrite each refusal to name the required family and the casilla's declared data type instead of a bare literal.
- Update the three tests that pinned the old refusal wording.

## Outcome

All six gates now classify by the family a declared data type belongs to. The three antecedent gates were over-restrictive, refusing a categorical casilla that compares against a literal perfectly well; the consequent and date gates were the silent complement, admitting a string casilla into a comparison that assumes a number. Both directions are closed.

Safety of the change was established from the registry rather than assumed. The declared predicate set is small and enumerable, and every casilla it references was checked: the antecedents are text, the consequents are money, and the two date casillas are text. Widening the antecedents admits more without breaking anything declared, and tightening the consequents refuses nothing declared. No registry TOML needed to change.

The date gate now accepts either the string family or a declared date type, since either can carry a parseable date. It previously demanded the text literal, which would have refused a casilla properly declared as a date.

Gates: 3174 passed across the registry package, including the reviewability baseline.

## Notes

The reconciliation broke a complexity ratchet and was reshaped rather than allowed to raise it. The module sat at exactly its reviewed 431-line ceiling, and a first implementation carrying a membership helper plus two message builders took it to 462.

The ceiling is a frozen per-module baseline, so raising it to fit would have loosened a review gate to accommodate new code. Instead the helpers were removed, the family test inlined at all six sites at no line cost, the declared data type folded into the existing message strings, and one comment paragraph reflowed. The module is back at exactly 431 with the reconciliation in place.

This is recorded because the first instinct was to raise the number, and the file would have passed either way. The ratchet only means something if it is the code that moves.
