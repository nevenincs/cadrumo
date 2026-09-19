---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:41239e9dff73ee45254921a6c675003a600ede352d144ce2e020adbdf3e0b3ee'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S238 sessionless profile delete review`

## Scope

Audit the S238 root admission change, profile-delete custody boundary, Windows
tombstone rename behavior, and real subprocess evidence against the accepted
per-profile custody authority.

## Findings

### s238-sessionless-profile-delete-review | low | root admission now matches custody ownership

The exact delete leaf no longer demands the session that logout deliberately
removes. Its own boundary continues to resolve one positional label, refuse the
active pointer, assess statutory retention, require explicit confirmation, and
bind destruction to the custody transaction's inventory witness and receipt.

### s238-sessionless-profile-delete-review | low | subprocess evidence closes the in-process gap

Fresh interpreters now prove both sides of the boundary: logout followed by
exact inactive deletion succeeds and leaves no registered profile, while an
active exact target receives the typed refusal and remains active and listed.
The exemption cites both test names as executable justification.

### s238-sessionless-profile-delete-review | high | resolved active-target race and recovery gap

Formal review found that an unlocked CLI check could race a concurrent login,
and that an invocation-only policy would not survive crash recovery. The final
implementation holds the canonical reentrant root transaction across the CLI
decision and lifecycle, persists `requires_inactive_target` in the digest-bound
journal, and revalidates it before any owner effect. Reset explicitly records
its distinct active-target authority. Native, WSL/POSIX, and real subprocess
evidence pass; final formal review reports no remaining findings.

## Recommendations

- Retain the exact-leaf exemption rather than widening it to the profile group.
- Keep the two subprocess witnesses named by the exemption whenever the command
  graph or authentication posture changes.
- Retain the durable inactive-policy recovery witness and the reentrant pointer
  transaction; do not replace either with an unlocked CLI-only check.
