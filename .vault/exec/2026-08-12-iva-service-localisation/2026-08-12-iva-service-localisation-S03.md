---
tags:
  - '#exec'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:431a649b8f93de9e744830fab722a20953bac584da14f03c7bd378bde49d04a2'
step_id: 'S03'
related:
  - "[[2026-08-12-iva-service-localisation-plan]]"
---

# Prove the two SERVICE categories now derive SERVICES through supply_nature_implied_by_category, and that the goods categories still derive GOODS. Assert the property per category from the shipped component table, never a total count of deriving categories - a count encodes this moment and goes stale the next time an article is bundled. Correct the module docstring that states the two SERVICE members derive nothing and names the gap as the citation table's

## Scope

- `src/cadrumo/domain/iva/_supply_nature.py`
- `src/cadrumo/domain/iva/tests/test_supply_nature.py`

## Description

- Added the invariant that a category the catalogue NAMES a service derives
  `SERVICES`, discovered from the catalogue rather than listed.
- Kept the goods families as a regression guard on the same change.
- Added the property that no shipped category is `CONTRADICTED`.
- Corrected the join's docstring, which stated the two service members derive
  nothing and named the gap as the citation table's.

## Outcome

Done. 69 pass across the domain module and the application-layer assertion
suite.

Proven to bite rather than assumed to: with the two new rows removed from the
vocabulary, both service members fall back to deriving nothing and the case
reds.

No count was asserted anywhere. The row's own instruction warned that a tally of
deriving categories encodes this moment and goes stale the next time an article
is bundled, so every case states a property instead.

## Notes

The name-based discovery is deliberate and is doing real work rather than being
a convenience. It asserts agreement between two independent declarations -- what
the catalogue calls a member, and what the articles its component row cites
establish -- so it fails if either drifts from the other. A hand-listed pair
would only ever have tested the two members that exist today.
