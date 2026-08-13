---
tags:
  - '#exec'
  - '#iva-art-69-dos-services'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:7e9921b18ac3d90ee9eab63cd5fd99a0eefc7d68d2e71104d5db6523a3049bad'
step_id: 'S02'
related:
  - "[[2026-08-12-iva-art-69-dos-services-plan]]"
---

# Split the outbound B2C branch on the declared item: a declared item with a third-country recipient is not-subject under art 69.Dos, and everything else stays taxed at the rate tier. The recipient test is third-country ONLY, because art 69.Dos states its own limit in the same sentence and excludes Canarias, Ceuta and Melilla though they sit outside the Comunidad. An undeclared item is not evidence of absence and must stay on the taxed branch

## Scope

- `src/cadrumo/domain/iva/_classification.py`

## Description

- Split the outbound B2C branch: a stated item with a third-country recipient
  is not-subject under art. 69.Dos, everything else stays taxed at the rate
  tier.
- Put the exception's two conditions in one predicate, so the rows and the
  rate-tier demand cannot answer it differently.
- Gave the criteria record the optional item field, absent by default.

## Outcome

Done. The two rows are disjoint by construction rather than by table order --
one is the exception, the other its complement over the same shared shape -- so
neither can shadow the other if the table is ever reordered.

## Notes

The recipient test is `THIRD_COUNTRY` alone, which reads like a narrowing of
"outside the Comunidad" and is not one. Art. 69.Dos excepts a recipient
established outside the Comunidad and then limits itself in the same sentence,
naming Canarias, Ceuta y Melilla back out. Subtracting them from the territories
outside the Comunidad leaves exactly a third country. The predicate's docstring
carries that arithmetic, because the next reader will otherwise see a narrower
test than the sibling rows use and "fix" it.

An absent item is refused as evidence. Reading the empty field as "not on the
list" would be right often and a silent relief the rest of the time, which is
the asymmetry that makes it the wrong default.
