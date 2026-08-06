---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:93fd9cb489d3263db76a57dabcfb03b6ea15ca6e7d70b3aeb605dc8ce04dc053'
step_id: 'S75'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Preserve the established recovery fingerprint across verification and recovery operations

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_record.py`

## Description

- Add a `recovery_fingerprint` computed property to the recovery envelope record, deriving a SHA-256 digest over the non-secret wrap material (ciphertext, nonce, tag), the HKDF info string, and the word count.
- Surface the fingerprint through the status, verify, and recover result records.

## Outcome

The established recovery fingerprint is preserved across verification and recovery: verify reads the envelope without writing it, and recover rewraps the master key but never touches the recovery envelope, so reloading yields the same fingerprint. The digest carries no plaintext mnemonic or master key.

## Notes

The property is not a serialized field, so the persisted envelope shape is unchanged and existing envelopes still validate. Delegated the digest to the canonical `core.hashing.sha256_hex` rather than inlining `hashlib`.
