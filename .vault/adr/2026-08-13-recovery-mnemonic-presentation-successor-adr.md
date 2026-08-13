---
tags:
  - "#adr"
  - "#recovery-mnemonic-presentation"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-08-08-recovery-mnemonic-surface-adr'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:155db43f2f40e2f18ff92bc64fa9a49719daba332f5d9a52b29a0082a3e99b6b'
---
# `recovery-mnemonic-presentation` adr: `recovery mnemonic presentation and handling` | (**status:** `accepted`)

## Problem Statement

Mnemonic encoding and one-time presentation remain useful operator-surface decisions after recovery custody becomes optional and independent.

## Considerations

- Recovery authority, artifact import/export, and password-reset semantics belong to `2026-08-13-profile-password-custody-adr`.
- Mnemonic plaintext is a secret and must not enter durable results or logs.

## Considered options

- Store or repeatedly display the mnemonic: rejected because it multiplies secret exposure.
- One-time explicit handoff with verification: accepted.

## Constraints

The wordlist and encoding version are canonical and locale-independent. Presentation must preserve exact word order and spacing.

## Implementation

Recovery enrollment presents mnemonic words once through a secret-capable interactive surface or bounded secret descriptor. The operator confirms possession through an explicit verification step before the recovery record becomes enrolled. Durable application results carry only version, enrollment state, and a non-secret fingerprint. Logs, telemetry, action envelopes, clipboard automation, shell history, and normal JSON output never contain words. Import accepts mnemonic only through the secret channel and zeroizes transient buffers.

## Rationale

This keeps human handling stable without making presentation state part of login or custody authority.

## Consequences

Lost mnemonic words cannot be redisplayed. Password login remains unaffected, and a new recovery enrollment requires current-password authentication.
