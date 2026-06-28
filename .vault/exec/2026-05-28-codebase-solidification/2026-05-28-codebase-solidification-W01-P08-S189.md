---
step_id: S189
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P08.S189 — annotate cast(T, envelope.payload)

## Outcome

Added inline rationale comment to `cast(T, envelope.payload)` at
`src/aeat/adapters/persistence/storage/envelope/_secure_repository.py` (load path).
Marker: `CAST-RATIONALE-SECURE-REPOSITORY-LOAD`. Explains that `_envelope_cls()`
returns `Envelope[self.payload_type]` == `Envelope[T]`, so Pydantic has already
validated the payload as T before the cast executes. Wave 2 follow-up noted inline.

## Verification

13 tests pass: `uv run --no-sync pytest src/aeat/adapters/persistence/storage/envelope/test_secure_bound_repository.py src/aeat/entrypoints/cli/test_errors.py -x`

Commit: b00a08f94
