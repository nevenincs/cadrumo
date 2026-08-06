---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2e65e473ca8fe9719290cc400267d96ed80a57fea47fa0cb4fe51dea1e6253e6'
step_id: 'S12'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# Route the declaracion parser administrative-token set through the core authority, it hardcodes four tokens and is missing COMUNICACION and VARIACION from the core set it shadows

## Scope

- `src/cadrumo/adapters/inbound/declaracion/_parser.py`

## Description

- Replace the parser's inline administrative-token set with a question asked of the core authority.
- Fold accents before the membership test.

## Outcome

Landed as `f829499ba7` ("fix(declaracion): ask core which period tokens are administrative"),
four files, 127 insertions and 4 deletions, including a new test module for the routing.

The row names the defect exactly: the parser hardcoded four tokens while the core set it
shadowed held five. Two authorities for one membership question, diverging in both directions,
since core in turn lacked every accented spelling the parser carried.

## Verification

    git log --format=%H --grep="ask core which period tokens are administrative" -1
    git show f829499ba7 --numstat
    17      4       src/cadrumo/adapters/inbound/declaracion/_parser.py
    84      0       src/cadrumo/adapters/inbound/declaracion/tests/test_parser_administrative_period_routing.py
    (plus core exports)

## Notes

The landed fix is wider than the row asks, and correctly so. The row asks for routing through
the core authority; the fix also folds diacritics before the question is asked. That is
required rather than optional: AEAT prints these tokens accented while the registry declares
them unaccented, so a bare membership test against core would have begun refusing
`MODIFICACION` in its accented form, a spelling the hardcoded set handled. Routing without
folding would have been a regression wearing a consolidation's clothes.

The divergence was unreachable in production when it was fixed. The two members the parser
lacked belong to Modelo 145, which ships no extraction profile, so the parse raises before the
filing-period step is reached. This closed a latent gap rather than a live defect.
