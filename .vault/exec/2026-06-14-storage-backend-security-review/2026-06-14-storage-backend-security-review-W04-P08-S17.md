---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S17'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S17 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Move exported_at out of the equality-bearing portable bundle payload and ## Scope

- `src/aeat/domain/user_profile/_portable_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move exported_at out of the equality-bearing portable bundle payload

## Scope

- `src/aeat/domain/user_profile/_portable_export.py`

## Description

- Document `UserProfilePortableExport.exported_at` as deliberate non-payload
  provenance metadata.

## Outcome

The bundle-determinism finding is resolved as working-as-intended: the sealed
archive uses a random AEAD nonce per seal, so a byte-stable bundle would not yield
a content-addressable archive, and the strict roundtrip gate compares re-loaded
repository objects, not this wrapper. 15 lifecycle tests green. Committed in
`4a5176c9e`.

## Notes

Chose documentation over removing the field: a precise consumer check was
obscured by tooling, and the timestamp is legitimate provenance.
