---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S03'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




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
