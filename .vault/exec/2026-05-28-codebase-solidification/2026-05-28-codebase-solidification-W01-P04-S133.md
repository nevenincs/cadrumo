---
step_id: S133
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S133 — DiagnosticPayload pydantic envelope

## Outcome

Replaced the internal `Mapping[str, object]` boundary in `_payload()` with a
typed `_DiagnosticPayload(BaseModel)` envelope.  Updated all callers
(`_summary_from_payload`, `load_auth_diagnostic`, `record_auth_diagnostic_phone_state`,
`_detail_fingerprints_from_payload`) to access typed attributes instead of
`.get()` on an untyped mapping.  Removed the now-unused `_json_object` helper
and `from collections.abc import Mapping` import.

The `_DiagnosticPayload` uses `extra="allow"` so payloads from older schema
versions validate cleanly.

## Files touched

- `src/aeat/application/auth/_diagnostics.py` (new model, callers updated)

## Collision check

Clean — `git diff` before first edit returned empty on target file.

## Test outcome

All 3 pre-existing tests passed after the refactor (no behaviour change).
