---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:06d714edbb6e2d7cf51df8543a5b158a51287c1586125270cc6b0e1146cbf009'
step_id: 'S23'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Replace recovery display and rotation spellings with recovery status, create, and rotate

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

- Replace `config show-recovery` and its `--rotate` spelling with the `config recovery` subgroup exposing `status`, `create`, and `rotate`.
- Route the CLI through the landed storage lifecycle authority via new application operations `create_recovery_code` / `rotate_recovery_code` in `src/cadrumo/application/user_profile/_custody.py` (create refuses an existing enrollment; rotate requires one; the prior envelope survives an unverified candidate).
- Extend `inspect_recovery_status` with the non-secret recovery fingerprint; `status` never exposes the words.
- Register `config.recovery.status` / `config.recovery.create` / `config.recovery.rotate` payload schemas carrying path, fingerprint, and rotated only.

## Outcome

The recovery display/rotation spellings are gone; the lifecycle subgroup is mounted with typed, secret-free envelopes and enrollment routed through the atomic verified-install storage facade.

## Notes

The old `mint_recovery_code` (which returned the mnemonic on a result record) and `CustodyRecoveryEnrollment` were deleted outright per no-legacy-compatibility; no consumer remained.
