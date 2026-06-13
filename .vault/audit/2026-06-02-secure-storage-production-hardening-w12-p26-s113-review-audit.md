---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S113]]'
---

# `secure-storage-production-hardening` Code Review

## S113-001 | LOW | Sanitizer source-parse errors endorsed raw exception chaining

Initial audit found that the sanitizer error contract documented raw pikepdf/QPDF exception chaining. For PDF sanitization inputs, raw parser exceptions can carry local paths, provider payload snippets, or third-party diagnostic strings that should not become operator-facing output.

Resolution: `SanitizerSourceParseError` now defaults to a redacted `<input-pdf>` message and structured context, carries only the upstream exception type name when supplied, ignores legacy positional diagnostic text for rendering/context, and uses the existing `errors.fail.fail_sanitization_source_parse` translated-message key.

Status: closed for the error class; S114 tracks the pipeline call-site migration.

## S113-002 | LOW | Already-sanitized refusal rendered a full source digest

Initial audit found that `AlreadySanitizedError` rendered the full source PDF SHA-256 in the public exception message. The full digest is useful internally, but a complete content fingerprint is unnecessary in operator-facing diagnostics.

Resolution: the full digest remains available through the typed `source_sha256` attribute, while the public message omits it and structured context carries only a short prefix.

Status: closed.

## S113-003 | INFO | Tests exercise direct error contracts

The S113 tests instantiate the real sanitizer exceptions and assert on hierarchy, message redaction, structured context, translated-message keys, unsafe positional diagnostic suppression, and full-digest non-rendering. They do not patch or fake the sanitizer pipeline.

Status: closed.

## S113-004 | INFO | Pipeline call-site remains the next row

The sanitizer pipeline still has a raw pikepdf failure boundary in `sanitize_pdf()`. This is the explicit scope of W12.P26.S114 / AFR-012 and should be migrated next.

Status: open follow-up.
