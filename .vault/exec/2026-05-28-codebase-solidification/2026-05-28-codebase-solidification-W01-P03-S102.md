---
step_id: S102
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S102 — empty-NIF localized envelope tests

## Outcome

Appended two real-behavior tests to
`src/aeat/adapters/outbound/aeat/sede/test_declarations.py`:

- S102-A: `capture_filed_declaration_observation` raises `SedeNavigationError`
  with `translated_message` when `identity_nif` is whitespace-only (strips to empty).
  Exercises the guard before any IO, using a synthetic `Declaracion` with
  `storage_state_path` set to a synthetic non-existent path.
- S102-B: `adapters.sede.errors.empty_identity_nif` locale key resolves to
  real non-placeholder copy.

Both tests pass.

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`

## Verification

`uv run --no-sync pytest src/aeat/adapters/outbound/aeat/sede/test_declarations.py -k "empty_nif" -v`
→ 2 passed.
