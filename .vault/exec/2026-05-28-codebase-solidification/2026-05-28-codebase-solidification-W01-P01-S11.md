---
step_id: S11
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S11 — replace bare TypeError with BrowserAdapterTypeError in verify

## Outcome

Replaced the bare `raise TypeError(...)` at line 125 of
`src/aeat/adapters/outbound/aeat/verify/__init__.py` with
`raise _BrowserAdapterTypeError(...)`, importing it from
`aeat.adapters.outbound.aeat.sede._errors`.

Reused `BrowserAdapterTypeError` (from sede) rather than introducing a new
`VerifyAdapterTypeError` because both guard the same conceptual boundary: a
browser-adapter factory returned a structurally incompatible object. The error
is already registered under `ERROR_SEDE_BROWSER_ADAPTER_TYPE` with locale
coverage in en, es, ca, and hu. Creating a parallel class for the
session-factory vs. page-factory distinction would add taxonomy noise without
meaningful consumer value and would violate the no-duplication rule.

## Files touched

- `src/aeat/adapters/outbound/aeat/verify/__init__.py`

## Verification

All 13 tests in `src/aeat/adapters/outbound/aeat/verify/test_verify.py` pass.
Commit SHA: d23b1303d.
