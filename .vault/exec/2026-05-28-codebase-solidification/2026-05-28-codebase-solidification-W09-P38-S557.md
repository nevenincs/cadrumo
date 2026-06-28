---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S557'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-28-codebase-solidification-adr]]'
---

# `codebase-solidification` `W09.P38.S557`

Added `BROAD-EXCEPT-RATIONALE-*` inline comments on three financial-provider teardown `except Exception` sites.

- Modified: `src/aeat/adapters/inbound/financial/providers/_pdf_n26.py`
- Modified: `src/aeat/adapters/inbound/financial/providers/_xlsx.py`
- Modified: `src/aeat/adapters/inbound/financial/providers/_ofx.py`

## Description

Each teardown site now carries a token of the form `BROAD-EXCEPT-RATIONALE-<NAME>` on the `except Exception` line, enumerating the known upstream exception types:

- `_pdf_n26.py:195`: pdfplumber raises `OSError`, `ValueError`, and `struct.error` from its C-level parser.
- `_xlsx.py:189`: openpyxl raises `OSError`, `ValueError`, `KeyError`, `IndexError`, and `TypeError`; `_close_workbook_during_teardown` must run unconditionally.
- `_ofx.py:173`: ofxparse raises bare `Exception`, `ValueError`, and `TypeError`; the library does not expose a typed exception hierarchy.

## Tests

Covered by the S561 inventory test `test_financial_provider_teardown_broad_except_carry_rationale` which asserts the token is present in each file. Commit: `1c2b02e82`.
