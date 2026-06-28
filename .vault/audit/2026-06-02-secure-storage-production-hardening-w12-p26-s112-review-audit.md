---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S112]]'
---

# `secure-storage-production-hardening` Code Review

## S112-001 | LOW | Shared PDF hashing errors exposed source paths

Initial audit found that `sha256_file()` let native filesystem exceptions escape from `Path.open()`. Missing or unreadable PDF paths could therefore include the operator-provided basename or absolute path in rendered diagnostics.

Resolution: `sha256_file()` now catches `OSError` only, logs the failure type at debug level with `<input-pdf>`, and raises `PdfModeloImportError` from `None` with redacted structured context and the `adapters.inbound.pdf.errors.hash_failed` translated-message key.

Status: closed.

## S112-002 | INFO | Tests exercise the real helper boundary

The S112 regression tests write a real file for the successful digest path and call `sha256_file()` with a real missing path for the privacy path. They do not mock filesystem behavior or duplicate project business logic.

Status: closed.

## S112-003 | INFO | Locale catalogue updated through canonical CLI

The `adapters.inbound.pdf.errors.hash_failed` leaf was added through `python -m aeat.locales` for `ca`, `en`, `es`, and `hu`; unrelated scaffold reserialization was removed before verification.

Status: closed.

## S112-004 | INFO | Plan check retains unrelated monotonicity warning

`vaultspec-core vault plan check` still emits the existing `PLAN022` canonical-id monotonicity warning. The warning is plan-global and does not indicate a failed S112 closure.

Status: open follow-up.

## S112-005 | LOW | Reviewer flagged raw cause-chain retention

The mandatory code review found no HIGH or CRITICAL issues, but flagged that `raise ... from exc` could preserve the raw filesystem path in traceback-oriented diagnostics through `__cause__`.

Resolution: the final implementation suppresses the raw cause chain with `from None` and records the failure type through a redacted module debug log. The regression test asserts `__cause__ is None` and verifies the captured debug log omits both basename and absolute path.

Status: closed.
