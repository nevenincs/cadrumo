---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:287785881c07595f16e6a85a65bbf60dc164fb05d0376226c4ca0616cf38192d'
step_id: 'S215'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Migrate the terminal and TUI creation consumer to the required application recovery handoff while preserving masked exact re-entry and cancellation-before-publication

## Scope

- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py and src/cadrumo/adapters/inbound/tui/`

## Description

- Carry the mandatory string-returning recovery handoff contract through the terminal manager seam and TUI registration injection boundary.
- Return masked exact mnemonic re-entry from the recovery screen to the application publication gate.
- Keep cancellation, mismatch, escape, shutdown, and timeout paths fail-closed while leaving successful secret zeroisation to the application scope.
- Exercise real TUI registration, recovery-word, and language-switch flows serially to avoid concurrent KDF timing interference.

## Outcome

The terminal manager and TUI creation paths now satisfy the mandatory application recovery handoff. The recovery screen clears the masked re-entry before dismissal, returns the exact verified phrase to the waiting registration worker, and lets the application compare and wipe it before publication. Refusal paths still wipe immediately and release the worker without creating a profile.

Verification completed with twenty-three focused TUI tests, scoped Ruff and type checks, a clean scoped diff check, and formal re-review with no remaining CRITICAL, HIGH, or MEDIUM recovery findings. The adjacent login screen module reached six passed and two unrelated failures in wrong-password worker exception presentation after its recovery-backed fixture profiles were created successfully.

## Notes

The parallel focused run exposed two timing/context failures that each passed alone; the same complete set passed serially. No test was skipped or weakened. Two pre-existing type diagnostics in the touched registration screen were resolved with boundary casts that preserve the existing structural injection design. Formal review found and corrected one TUI login fixture that returned `None` from the now-required handoff; it now returns the real enrollment mnemonic.
