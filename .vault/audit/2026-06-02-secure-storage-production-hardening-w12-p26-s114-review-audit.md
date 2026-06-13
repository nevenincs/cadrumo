---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S114]]'
---

# `secure-storage-production-hardening` Code Review

## S114-001 | LOW | Sanitizer digest path could expose filesystem diagnostics

Initial audit found that `_digest_source()` let `Path.open()` failures escape as native filesystem exceptions. Missing or unreadable PDF paths could therefore surface operator basenames or absolute paths.

Resolution: `_digest_source()` now catches `OSError`, logs a redacted debug diagnostic with `<input-pdf>` and the failure type, builds a `SanitizerSourceParseError`, and raises it outside the `except` frame so `__cause__` and `__context__` are both empty.

Status: closed.

## S114-002 | LOW | pikepdf parse failures rendered raw upstream text

Initial audit found that `sanitize_pdf()` interpolated the raw pikepdf/QPDF exception text into `SanitizerSourceParseError`, chained the original exception, and logged `exc_info=True`.

Resolution: `sanitize_pdf()` now logs only a redacted debug diagnostic with the parser exception type, builds `SanitizerSourceParseError(failure=...)`, and raises it outside the `except` frame so `__cause__` and `__context__` are both empty.

Status: closed.

## S114-003 | INFO | Tests exercise the real runtime boundary

The S114 tests call `sanitize_pdf()` with a real missing path and real invalid bytes. They assert that rendered errors, structured context, captured debug logs, `__cause__`, and `__context__` do not expose the basename, absolute path, or parser payload.

Status: closed.

## S114-004 | INFO | Successful provenance SHA-prefix logging retained

Successful sanitizer runs still log short source/output SHA prefixes for deterministic provenance. This is not part of the S114 failure-emission defect, but remains an adjacent privacy policy question for the broader remote-mirror logging sweep.

Status: open follow-up.
