---
tags:
  - '#exec'
  - '#session-honest-followups'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S18'
related:
  - "[[2026-06-02-session-honest-followups-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace session-honest-followups with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-06-02-session-honest-followups-plan placeholders are machine-filled by
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
     The Clarify EncryptedString str-vs-bytes round-trip on object_key column and ## Scope

- `src/aeat/adapters/persistence/storage/sql/_orm.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Clarify EncryptedString str-vs-bytes round-trip on object_key column

## Scope

- `src/aeat/adapters/persistence/storage/sql/_orm.py`

## Description

- Backfill the missing execution record for checked Step `P03.S18`.
- Recover diagnostic evidence from commit `660f8486c1`.
- Record the historical finding that the encrypted column raw read returns opaque bytes by design and consumers should use accessors.

## Outcome

- `P03.S18` has a canonical exec record linked to the parent plan.
- The old closeout resolved the concern as behavior-by-design rather than landing an ORM change.
- No source files were changed by this backfill.

## Notes

- This is a diagnostic closure record, not a fresh storage round-trip proof.
