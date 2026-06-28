---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-W12-P26-S109]]'
---

# `secure-storage-production-hardening` Code Review

## S109-001 | LOW | Justificante missing-file error exposed source path

Initial audit found that `parse_justificante()` raised a missing-file `JustificanteParseError` containing the caller-provided path.

Resolution: missing-file errors now use `<input-pdf>`, carry redacted context, carry a translated-message key, and expose `missing=("source_pdf",)`.

Status: closed.

## S109-002 | LOW | Justificante parser debug log exposed source path

Initial audit found that the parser entry-point debug log printed the caller path while selecting the backend.

Resolution: the debug log now records `source=<input-pdf>` and the backend only. A real fixture parse test captures the parser logger and asserts the source basename and path are absent.

Status: closed.

## S109-003 | LOW | Extractor failures could bubble path-bearing messages through parser

The extractor still uses the resolved PDF path for successful provenance and for some low-level parse-error messages. The parser entry point now redacts only errors whose rendered message mentions the caller path while preserving the original exception as the cause.

Resolution: path-bearing `JustificanteParseError` and `JustificanteCsvNotFoundError` instances are copied with `<input-pdf>`, redacted context, translated-message metadata, and the original structured attributes.

Status: closed.

## S109-004 | INFO | Justificante parse errors now carry core metadata

`JustificanteParseError` now accepts `context`, `suggestion`, and `translated_message`, matching the established declaración parse-error shape while still deriving from `AeatError`.

Status: closed.

## S109-005 | INFO | Tests exercise real parser behavior

The S109 tests use real PDF fixture parsing, missing filesystem paths, and a real ReportLab-generated non-justificante PDF. They do not use mocks, monkeypatches, fakes, or tautological assertions.

Status: closed.

## S109-006 | LOW | Successful justificante provenance still carries source paths

`Justificante.source_pdf_path` remains the resolved source path for successful records. Future secure-storage enrollment should decide whether persisted filing artifacts store full paths, redacted labels, or secure object references.

Status: open follow-up.

## S109-007 | LOW | Non-Justificante exceptions are not redacted at the parser boundary

Final review noted that the S109 wrapper redacts `JustificanteParseError` messages that mention the source path, but does not broad-catch unrelated downstream exceptions such as unexpected I/O or hashing failures. This is intentionally left open rather than swallowing or remapping unexpected exceptions in the parser entry point without a broader error-boundary design.

Status: open follow-up.

## S109-008 | INFO | Final review found no high-severity defects

Final review found no HIGH or CRITICAL issues. The reviewer confirmed the plan register, exec record, and audit record are present and that S109 is safe to commit and push with the success-path provenance and non-Justificante exception-boundary follow-ups deferred.

Status: closed.
