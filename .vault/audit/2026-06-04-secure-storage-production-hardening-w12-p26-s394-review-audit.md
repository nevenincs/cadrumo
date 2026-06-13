---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S394]]'
---

# `secure-storage-production-hardening` `W12.P26.S394` Review

## S394-001 | PASS | Locale CLI is a developer catalogue boundary

`src/aeat/locales/cli.py` is a Typer wrapper around `LocaleManager`. It resolves the in-tree locale directory, delegates catalogue reads/writes to the manager, and does not construct secure-storage repositories, inspect active profiles, manage master-key material, or write arbitrary plaintext paths.

## S394-002 | PASS | User-facing CLI output is localized

The CLI uses `tr()` for command help, option/argument help, audit drift output, and set/remove/scaffold confirmations. `LocaleError` from the manager is converted into `typer.BadParameter` with exception chaining, so failures are not silently swallowed and diagnostics remain attached.

## S394-003 | PASS | Duplication review

Vaultspec RAG semantic search clustered this slice with `LocaleManager`, locale CLI translation tests, and locale coverage gates. The CLI imports `_covered_by_namespace` from the manager instead of redeclaring the helper, and the write commands reuse `set_locale_value()` and `remove_locale_value()`.

## S394-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/locales/cli.py src/aeat/locales/test_cli.py src/aeat/locales/test_parity.py`
- `uv run --no-sync pytest -q src/aeat/locales/test_cli.py src/aeat/locales/test_parity.py::test_locale_set_cli_rejects_path_like_locale_without_writing`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uvx vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-292`.
