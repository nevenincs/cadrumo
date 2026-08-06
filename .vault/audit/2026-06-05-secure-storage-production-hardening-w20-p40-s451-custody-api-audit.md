---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:edc01139b8dba6556fa62878f87d126b1365d6c790d5dc144866a6bc7346b1ca'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
---

# `secure-storage-production-hardening` `W20.P40.S451` custody API audit

## S451-001 | PASS | Accepted current operator architecture requires first-class verbs

The custody ADR originally named `aeat config unlock`, but the later D1
operator-surface decision hard-replaces it with `aeat config switch`. The
canonical surface is `aeat config switch`, `aeat config lock`,
`aeat config rekey`, `aeat config recover`, `aeat config show-recovery`, and
`aeat config verify-recovery` as the canonical operator command surface. Current
help output for `aeat config`, `aeat config profile`, and `aeat config repair`
does not expose those first-class leaves.

## S451-002 | PASS | Lower-level recovery API exists but is not enough

The master-key package exports the recovery primitives and the recovery facade
implements `mint_recovery_envelope`, `unwrap_recovery_envelope`,
`verify_recovery_mnemonic`, and `open_session_from_recovery`. The file fallback
provider also has `complete_recovery()` for re-wrapping a recovered key under the
current passphrase. These APIs satisfy part of the backend foundation, but they
do not satisfy the ADR's operator-facing CLI verb set by themselves.

## S451-003 | PASS | Current lifecycle substitutes remain useful but incomplete

The secure-storage plan already accepts `profile create`, `config switch`, and
`profile logout` as the current profile lifecycle custody path. They cover
profile creation, session activation, and pointer logout behavior, but they are
not equivalent to the ADR's first-class recovery, recovery verification, or
passphrase rewrap verbs.

## S451-004 | PASS | Missing work is now executable

`W20.P40.S457` now owns implementation of the first-class custody verbs through
the config CLI, recovery facade, bucket-session lifecycle, and locale catalogues.
`W20.P40.S458` now owns stale custody/recovery guidance replacement, including
copy that names superseded `config unlock` behavior or vague
profile recovery prose. Localization work in those rows must use
`python -m aeat.locales`.

Disposition: close `W20.P40.S451` as a verification/adoption row. Do not treat
the custody command implementation as complete until `S457` and `S458` close.
