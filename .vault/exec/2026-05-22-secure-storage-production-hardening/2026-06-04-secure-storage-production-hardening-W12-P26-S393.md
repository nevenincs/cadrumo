---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S393'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s393-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S393`

Closed `AFR-291` for the locale AST scanner plaintext-exception slice.

## Description

- Enrolled `translation_key=` kwargs as authoritative dotted-literal locale declarations in the AST scanner.
- Added a regression test proving helper APIs that accept `translation_key` are discovered by `scan_source_tree()`.
- Re-ran the canonical `aeat.locales` set and audit flow so live `translation_key=`, error-registry, and wizard test strings remain catalogued.
- Aligned the AFR register entry for `AFR-291` to `closed`.

## Outcome

`AFR-291` is closed as `plaintext-exception`. The locale catalogue pipeline now treats `translation_key=`-based operator strings as live declarations, and the catalog includes the additional registry/test leaves that the canonical audit reported as required.

Validation passed:

- `uv run --no-sync ruff check src/aeat/locales/_ast_scanner.py src/aeat/locales/test_parity.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py::test_ast_scanner_collects_translation_key_kwargs`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

## Notes

This was surfaced while validating S270 locale updates. S270 itself was already committed separately as `fix(user-profile): harden secure profile repository errors`; this step records the scanner hardening needed to keep the canonical locale CLI trustworthy.
