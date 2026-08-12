---
tags:
  - '#exec'
  - '#iva-service-localisation'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:a9c2fcc138aed384cc37d2b0262b13ba0e9c61d10bb75816a91377d82f79e71c'
step_id: 'S02'
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
     The S02 and 2026-08-12-iva-service-localisation-plan placeholders are machine-filled by
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
     The Add citation rows for LIVA arts 68 (goods), 69 and 70 (services), each pinned to its anchor in the consolidated law. Verify through the gate rather than by assertion: each row's claim must survive reading the article's own rubric. The disconfirming observation: if any category turns out to cite art 68 alongside 69 or 70 the join now reports CONTRADICTED for it, which would be a real finding about the component table rather than a reason to drop a row - stop and report it and ## Scope

- `src/cadrumo/domain/iva/_supply_nature.py`
- `src/cadrumo/domain/iva/tests/test_supply_nature.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add citation rows for LIVA arts 68 (goods), 69 and 70 (services), each pinned to its anchor in the consolidated law. Verify through the gate rather than by assertion: each row's claim must survive reading the article's own rubric. The disconfirming observation: if any category turns out to cite art 68 alongside 69 or 70 the join now reports CONTRADICTED for it, which would be a real finding about the component table rather than a reason to drop a row - stop and report it

## Scope

- `src/cadrumo/domain/iva/_supply_nature.py`
- `src/cadrumo/domain/iva/tests/test_supply_nature.py`

## Description

- Added rows for LIVA arts. 68 (goods), 69 and 70 (services), each pinned to
  its anchor in the bundled consolidated law.
- Rewrote the table's own prose: the two `corpus_ref` shapes and why both are
  sound, and art. 22's absence as its own separate reason.

## Outcome

Done. Each row passes the same gate every other row passes, against the
article's own rubric.

The disconfirming observation the row asked for did not occur. Measured over the
shipped tables after the change: three goods families derive GOODS, both service
members derive SERVICES, and nothing is CONTRADICTED -- no category cites art. 68
alongside arts. 69 or 70.

## Notes

The join was not touched. The services half arrived entirely through the
citation table, which is the point of keeping the two authorities joined rather
than writing a category-keyed map.

Art. 22 stays out and its reason is now on the table rather than in a campaign
note. Scoping was never its obstacle -- assimilated exports have their own
bundled file. Its opening enumerates operation kinds instead of naming a limb,
so what it establishes is decidable only by consulting arts. 8 and 11, where the
statute defines the two limbs. Adding the row without that lookup would mean
typing the answer in, which is the paraphrase the gate exists to prevent.
