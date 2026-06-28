---
tags:
  - '#exec'
  - '#core-authority'
step_id: S16
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P05.S16 — Replace AEAT_NIF_IVA_ENTRY_URL with lazy Settings read (RELOC-006)

## Change

Removed module-scope `AEAT_NIF_IVA_ENTRY_URL` constant from
`domain/calculations/registry/_aeat_nif_iva_oracle.py` and its re-export from
`domain/calculations/registry/__init__.py`.

Updated `planned_operations` entry URL and all call sites in `_nif_iva_check.py`
to compute the entry URL lazily via
`f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.help_pages.nif_iva_landing}"`.

Updated test files to remove the constant import and use `Settings.external_constants()`.

## Verification gate

NIF/IVA oracle and sede driver test suites — passed sequentially.

## Commit

Committed as part of W03.P05 URL constant lazy-reads block (combined with S15).
