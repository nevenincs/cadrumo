---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S42'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S42 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C4 Extract a shared ledger catalogue load/save helper for the evidence and business-invoice modules and ## Scope

- `src/aeat/application/ledger/_evidence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C4 Extract a shared ledger catalogue load/save helper for the evidence and business-invoice modules

## Scope

- `src/aeat/application/ledger/_evidence.py`

## Description

- Re-read the C4 candidate (`application/ledger/_evidence` and
  `_business_operation_invoice` `_repository`/`_load`/`_save` helper triplet)
  under the substitutability pre-filter.

## Outcome

**Constraint-divergent / thin-idiom — NOT actioned.** The `_repository` helpers
already delegate to the canonical `secure_object_repository_for_bucket` (no
duplication there); the `_save` builders construct different document types with
a divergent `source_kind` axis (business-invoice) the evidence variant lacks;
and the only genuinely-shared fragment is the one-line load unwrap
`list(document.records) if document is not None else []` — an F4-class trivial
idiom whose extraction (a 2-line generic over 2 sites) provides negligible value.
Its natural home would have been the C3 single-catalogue base, which is itself
excluded as constraint-divergent (see S41).

## Notes

Folds into the S41 finding. No code change; the disciplined pre-filter verdict
is "no clean, non-leaky extraction exists."
