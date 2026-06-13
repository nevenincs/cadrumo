---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S393]]'
---

# `secure-storage-production-hardening` `W12.P26.S393` Review

## S393-001 | PASS | Locale scanner preserves `translation_key` surfaces

The AST scanner now treats dotted-literal `translation_key=` kwargs as concrete locale key declarations alongside `message_key=` and `translated_message=`. This closes the scaffold/audit gap that allowed live CLI helper strings to be pruned from the catalogues even though runtime calls still rendered them through `tr()`.

## S393-002 | PASS | Regression coverage is non-tautological

The parity test writes a temporary Python module with a helper call using `translation_key='cli.app.modelo.work.sal_reserva_not_decimal'` and asserts that `scan_source_tree()` discovers the concrete key. The test exercises the scanner behavior directly rather than mirroring locale YAML contents.

## S393-003 | PASS | Locale CLI roundtrip remained canonical

After the scanner fix, `python -m aeat.locales set` and `python -m aeat.locales audit` preserved the live `cli.app.modelo.work.*` key covered by the regression test and restored registry/test leaves reported as missing by the canonical audit. The final audit returned clean for all four locale files.

## S393-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/locales/_ast_scanner.py src/aeat/locales/test_parity.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py::test_ast_scanner_collects_translation_key_kwargs`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`

Disposition: close `AFR-291`.
