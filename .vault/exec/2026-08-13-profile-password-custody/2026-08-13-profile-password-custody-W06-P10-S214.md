---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:85c4b6fa1a99fb355f9dcb7d18d21c4de7aef74e47e58d6dad58af7f1e316686'
step_id: 'S214'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Migrate the scripted CLI creation consumer to the required application recovery handoff while preserving bounded descriptor transfer, collision preflight, verification, and failure atomicity

## Scope

- `src/cadrumo/entrypoints/cli/_config/_scripted_registration.py and src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py`

## Description

- Return the CLI-verified recovery phrase from the scripted handoff to the mandatory application publication gate.
- Preserve terminal and paired-descriptor delivery, strict verification JSON parsing, descriptor collision preflight, and CLI-specific mismatch refusal.
- Exercise the complete real scripted profile-creation matrix across interactive and non-interactive lanes.

## Outcome

Scripted profile creation now satisfies the required application handoff contract without weakening the CLI leaf protocol. The CLI still refuses malformed, missing, colliding, or mismatched recovery channels before a profile can survive; after its surface-specific verification succeeds, the exact phrase reaches the application for the final pre-publication comparison.

Verification completed with the thirty-six-test scripted creation integration matrix, scoped Ruff and type checks, a clean diff check, and a formal review with zero CRITICAL, HIGH, MEDIUM, or LOW findings.

## Notes

The profile command specification already owned the paired leaf-channel declarations and required no code change. Terminal manager and TUI consumers remain intentionally untouched for S215.
