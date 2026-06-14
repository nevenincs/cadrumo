---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S03'
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
     The S03 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Accept an in-memory binary stream in the bbox declaration parse path so no decrypted bytes touch disk and ## Scope

- `src/aeat/adapters/inbound/declaracion/_parser.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Accept an in-memory binary stream in the bbox declaration parse path so no decrypted bytes touch disk

## Scope

- `src/aeat/adapters/inbound/declaracion/_parser.py`

## Description

- Add `_extract_pages_words_from_bytes` opening an in-memory `io.BytesIO` stream
  through `pdfplumber.open`, mirroring the path-based extractor.
- Thread an optional `pdf_bytes` argument through `parse_declaracion_bytes`,
  `_parse_declaracion_pages`, and `_extract_profile_values`; bbox extraction now
  prefers the in-memory bytes and only falls back to a real source file when
  bytes are absent.

## Outcome

The bbox-anchored declaration extraction path runs entirely in memory. Verified
by the existing `test_declaration_pdf_values_become_observed_casillas` (M130 bbox
profile) and the declaracion parser suite (245 passed). Committed in `25224b9e0`.

## Notes

Landed together with S04 in one atomic commit; the two are inseparable (the
in-memory capability and the removal of the disk path).
