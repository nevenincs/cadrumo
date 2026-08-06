---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:828709994494871d37ba67505a57355f8461358566dd5277f704ad2eec0869a2'
step_id: 'S73'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Preserve the prior recovery envelope until a candidate mnemonic has been fully verified

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery.py`

## Description

- Add `atomically_install_verified_recovery` to the recovery primitives module: it runs a caller-supplied verification callback and only writes the payload through the atomic secure writer once that callback returns without raising.
- Wire the facade create/rotate flow to install the staged candidate exclusively through this primitive, with a verification closure that fully unwraps the candidate under the operator's retype.

## Outcome

The prior recovery envelope is preserved until a candidate mnemonic is fully verified. Because the atomic write is unreachable until verification passes, a cancelled, mistyped, or corrupt candidate leaves any existing envelope untouched, and the replacement is all-or-nothing.

## Notes

The primitive is intentionally shape-agnostic (payload bytes plus a verify callback), so it lives in the low-level primitives module without importing the higher-level envelope record and without creating an import cycle with the facade.
