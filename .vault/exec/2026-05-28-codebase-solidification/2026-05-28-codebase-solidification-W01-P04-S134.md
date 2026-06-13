---
step_id: S134
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S134 — DiagnosticPayload roundtrip tests

## Outcome

Added two tests to `src/aeat/application/auth/test_diagnostics.py`:

- `test_diagnostic_payload_round_trips_through_json`: validates from a raw dict
  with a future-extension field, serialises via `model_dump(mode="json")`,
  re-validates, and asserts strict model equality.  Anti-tautology probe mutates
  the serialised blob and confirms inequality is detected.

- `test_diagnostic_payload_rejects_non_object_json`: calls the private `_payload()`
  directly with a JSON array and asserts `ValueError` is raised.

No mocks, no skips, no xfail.

## Files touched

- `src/aeat/application/auth/test_diagnostics.py` (2 tests added, import extended)

## Test outcome

5 tests passed (3 pre-existing + 2 new).
