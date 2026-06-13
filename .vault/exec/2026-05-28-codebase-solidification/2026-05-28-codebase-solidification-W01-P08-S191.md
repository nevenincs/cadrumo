---
step_id: S191
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P08.S191 — typed Envelope.for_payload_type factory

## Outcome

Added `Envelope.for_payload_type(payload_cls)` classmethod to
`src/aeat/adapters/persistence/storage/envelope/_envelope.py`. Returns
`type[Envelope[PayloadT]]` via a documented `type: ignore[return-value]` on
`cls.__class_getitem__(payload_cls)` (the only safe escape point).

Replaced `cast(Any, Envelope).__class_getitem__(...)` in `_envelope_cls()` with
`Envelope.for_payload_type(self.payload_type)`. Removed `Any` from imports.

## Verification

All 13 tests pass. Commit: b00a08f94
