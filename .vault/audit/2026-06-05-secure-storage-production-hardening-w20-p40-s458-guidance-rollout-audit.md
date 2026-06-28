---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-14-secure-backend-passkey-custody-adr]]'
---

# `secure-storage-production-hardening` `W20.P40.S458` guidance rollout audit

## S458-001 | PASS | Recovery guidance names first-class commands

Master-key torn-state, passphrase mismatch, existing-material, bucket-DEK, and
unsupported key-schedule guidance now names `aeat config recover` or
`aeat config rekey` instead of the old generic profile recovery or rotation
flow.

## S458-002 | PASS | Runtime unlock guidance names `config unlock`

Active-session and runtime-readiness messages now direct operators to
`aeat config unlock NAME` when no active bucket session exists, a session is
sealed, or a session has expired. Storage-refusal locale messages and adapter
error-registry suggestions use the same canonical unlock command.

## S458-003 | PASS | Recovery verification suggestion is no longer profile switch

The recovery-verification error registry suggestion now points at
`aeat config verify-recovery --recovery-key <WORDS>`, matching the first-class
recovery-code test surface added in S457.

## S458-004 | PASS | Locale updates used the required CLI path

The runtime and storage-refusal locale leaves were updated through
`uv run --no-sync python -m aeat.locales set`. The final locale audit reports
`ca.yml`, `en.yml`, `es.yml`, and `hu.yml` as valid.

## S458-005 | PASS | Focused gates passed

Focused ruff, master-key tests, adverse-session tests, error-registry tests, and
locale audit passed after the guidance replacement.

Disposition: close `W20.P40.S458`. Remaining W20 work stays open for S452
passphrase/redaction bootstrap hardening, S453 guard narrowing, S454 broader
filing/modelo localization, S455 provenance path privacy, and S456 central
redaction enrollment proof.
