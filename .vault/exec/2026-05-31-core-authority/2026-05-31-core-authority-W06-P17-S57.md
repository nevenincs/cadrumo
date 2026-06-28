---
step_id: S57
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P17.S57

## Summary

Promoted bare-str `tax_id`/`profile_tax_id` return type annotations on two confirmed domain Protocol property declarations to the typed `SubjectTaxId` alias from `core/identity`, per PROMOTE-002 and Rule 5.

## Changes

- `src/aeat/domain/filing/_protocols.py`: `ModeloProfile.tax_id` return type promoted from `str` to `SubjectTaxId`. Added `TYPE_CHECKING` guard for the import.
- `src/aeat/domain/submission/_protocols.py`: `ModeloDraftLike.profile_tax_id` return type promoted from `str` to `SubjectTaxId`. Added `TYPE_CHECKING` guard for the import.

Both files use `from __future__ import annotations` so `SubjectTaxId` is a string annotation at runtime.

## Commit

`92f035609` — feat(domain): W06.P17.S57 - annotate SubjectTaxId on domain Protocol tax_id properties
