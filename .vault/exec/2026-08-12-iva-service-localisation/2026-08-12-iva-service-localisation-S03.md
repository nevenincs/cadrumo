---
tags:
  - '#exec'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:e83332a1155ab521caff0c97175b04ca53704c92b3a03d81442044a8058ac7b0'
step_id: 'S03'
related:
  - "[[2026-08-12-iva-service-localisation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-service-localisation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-08-12-iva-service-localisation-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Prove the two SERVICE categories now derive SERVICES through supply_nature_implied_by_category, and that the goods categories still derive GOODS. Assert the property per category from the shipped component table, never a total count of deriving categories - a count encodes this moment and goes stale the next time an article is bundled. Correct the module docstring that states the two SERVICE members derive nothing and names the gap as the citation table's and ## Scope

- `src/cadrumo/domain/iva/_supply_nature.py`
- `src/cadrumo/domain/iva/tests/test_supply_nature.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
