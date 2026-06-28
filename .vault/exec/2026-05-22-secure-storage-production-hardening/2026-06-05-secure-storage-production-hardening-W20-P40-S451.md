---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S451'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W20.P40.S451 - Verify custody command and API exposure

Scope: verify recovery, lock, unlock, rekey, recover, show-recovery, and
verify-recovery command/API exposure against the accepted custody architecture,
then add owner rows for any accepted operation still absent.

## Description

- Re-read the accepted custody ADR sections for recovery enrollment, lock/unlock
  semantics, rekey, and the canonical `aeat config` verb set.
- Inspected the config CLI command modules, bootstrap-exempt registry, config
  help output, profile help output, repair help output, and command-policy
  scanner.
- Inspected the master-key recovery primitives, recovery facade, bucket session,
  and file-fallback `complete_recovery()` backend.
- Added `W20.P40.S457` for implementation of the missing first-class config
  custody verbs.
- Added `W20.P40.S458` for stale custody/recovery guidance replacement.
- Closed `W20.P40.S451` through `vaultspec-core vault plan step check`.

## Outcome

The verification row is closed, but the custody command rollout is not complete.
The backend recovery API exists; the first-class CLI command surface and operator
copy remain open, now owned by `S457` and `S458`.

## Notes

No source code was changed in this step. Locale work for the follow-up rows must
use `python -m aeat.locales`.
