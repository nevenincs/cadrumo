---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S120]]'
---

# `secure-storage-production-hardening` Code Review

## S120-001 | LOW | Deserialiser errors could expose malformed wire bytes

Initial audit found that RESERVED mismatch errors included `raw!r`, and envelope collision errors echoed parsed divergent values. For a remote/export parse boundary, malformed payloads may contain taxpayer identifiers or filing values; diagnostics should identify the failure without copying the offending payload.

Resolution: malformed byte diagnostics now report length plus a short SHA-256 digest. Multi-segment divergent casilla and field errors name the colliding key but no longer include the conflicting values.

Status: closed.

## S120-002 | LOW | Decode failures could escape outside the AEAT export error hierarchy

Date parsing, invalid currency digits, and text decode failures could surface as stdlib `ValueError` or `UnicodeDecodeError`. That made the API less consistent under corrupt remote/export inputs.

Resolution: date, currency, and text decode failures now raise `AeatExportFormatError` with redacted length/digest context and no retained stdlib exception cause/context for malformed wire payloads.

Status: closed.

## S120-003 | INFO | Canary tests cover malformed wire privacy

New malformed CURRENCY and RESERVED tests feed taxpayer-like byte canaries through the real `deserialise()` path and assert the resulting `AeatExportFormatError` messages include length/digest breadcrumbs but not the raw canary bytes.

Status: closed.

## S120-004 | INFO | Broader golden export tests are currently blocked by unrelated registry validation

The broad export-format run failed only in the Modelo 130 and Modelo 303 golden tests because registry validation currently rejects Modelo 151 legal references before those tests reach the export deserialiser. The S120-focused decoder and envelope tests passed.

Status: open external blocker.

## S120-005 | MEDIUM | Chained stdlib exceptions could retain raw wire payloads

Mandatory review found that the first typed wrapping pass used exception chaining. Even with redacted `AeatExportFormatError` messages, a full traceback or debug renderer could still expose the original stdlib `ValueError` or `UnicodeDecodeError` containing raw decoded bytes.

Resolution: the date, currency, and text decode wrappers now capture only the stdlib failure type and raise outside the `except` context, leaving `__cause__` and `__context__` unset for the malformed payload cases covered by S120. The tests assert this for date and currency canaries.

Status: closed.

## S120-006 | INFO | Mandatory re-review found no remaining blockers

The mandatory S120 re-review confirmed that the prior medium chained-exception privacy finding is closed and found no remaining medium, high, or critical issues in the S120 scope.

Status: closed.
