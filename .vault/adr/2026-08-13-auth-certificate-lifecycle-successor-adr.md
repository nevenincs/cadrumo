---
tags:
  - "#adr"
  - "#auth-certificate-lifecycle"
date: '2026-08-13'
related:
  - "[[2026-08-13-profile-password-custody-research]]"
supersedes:
  - '2026-07-25-auth-cert-recovery-custody-adr'
  - '2026-07-17-auth-cert-recovery-custody-adr'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:3c67680898709de808219060615783fa7bc22b2e3cced82f2c937adbab7d085d'
---
# `auth-certificate-lifecycle` adr: `authentication certificate lifecycle` | (**status:** `accepted`)

## Problem Statement

AEAT authentication certificates have acquisition, selection, expiry, replacement, and revocation semantics independent of profile-data custody.

## Considerations

- Recovery of profile data does not recover or revoke an external certificate.
- Certificate actions can create external effects and need explicit authority.

## Considered options

- Couple certificate recovery to profile recovery: rejected.
- Preserve a separate certificate lifecycle owner: accepted.

## Constraints

Certificate private material remains encrypted secure-storage data after profile unlock. Revocation and remote validation are separate authorized operations.

## Implementation

The authentication owner controls certificate import, validation, profile association, expiry status, replacement, and explicit revocation workflows. It stores private material only through current secure storage and never supplies a profile DEK or alternate unlock route. Profile backup includes certificate data only as ordinary encrypted profile inventory. Recovery restore recovers that ciphertext but makes no claim about external certificate validity or revocation.

## Rationale

Separating external credential lifecycle from local data custody prevents either recovery mechanism from overclaiming authority.

## Consequences

Restored profiles may still require certificate replacement or a separately authorized revocation operation.
