---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:05095ea3568a8032ae2f5d1737bad0fe67a2cf2446a0a6849bb1089ff0f0116f'
step_id: 'S23'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden protect-data-access.md

## Scope

- `docs/how-to/protect-data-access.md`

## Description

- Verify-close: read `protect-data-access.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm the audit's positive verdict: the protect-data-access flow delivered fully end-to-end (show-recovery, verify-recovery, passphrase `--rotate`, rekey-without-re-encrypt, `recover`, lock, reset guards) - data stayed readable through a passphrase change and a full recovery, and both reset guards fire.
- Confirm the recovery-key-first framing (create a recovery key before you need it; the words are shown once), the passphrase prerequisite, and the recover/rekey command surface are documented.

## Outcome

- Page verified compliant at HEAD; the recovery/rekey/lock surface is documented and confirmed working by the persona. Delta: none required. CLI conformance gate green.

## Notes

- Residual m17 (`<profile-id>` placeholder leak in `config lock`) is an APP-side output finding, out of documentation scope.
