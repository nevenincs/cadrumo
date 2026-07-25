---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S50'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Make the recovery-enrollment manifest flag write atomic with the verified envelope install, or reconcile the flag from the envelope on read, so a process kill between the two cannot leave recovery_enrolled reading false while a genuinely enrolled envelope exists on disk, deferred by the P04 door safety review as cosmetic because recovery status and verify both read the envelope file directly rather than the manifest flag, whose only untraced exposure is wherever it is consumed as a UI hint rather than a security-relevant gate, and tracked here so a later pass over this surface cannot re-introduce it as a false already-covered assumption

## Scope

- `src/cadrumo/application/user_profile/_custody.py`

## Description

## Outcome

## Notes
