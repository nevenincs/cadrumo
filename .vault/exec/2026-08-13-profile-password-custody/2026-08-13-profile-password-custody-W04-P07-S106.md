---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:1d7b29c8646363f7173ab11fb90d3c0472e1fd4f48e7829bdc6752fb4f8e2448'
step_id: 'S106'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh close the under-declaration in the minimal profile registration helper whose signature accepts a plain string identifier while it builds a record whose identifier is UUID-constrained, so every caller passing a readable identifier fails at construction rather than at the boundary that declared the looser type, this being the same defect reached independently from two directions tonight

## Scope

- `src/cadrumo/tests/ and src/cadrumo/application/user_profile/`

## Description

Repair UUID-constrained harness fixtures and validate the affected profile-capsule construction paths without weakening canonical profile identity.

## Outcome

The minimal registration helper now accepts `str | UUID` and normalises through `canonical_profile_bucket_id` at the door, so a readable identifier fails with one instructive refusal at the helper boundary instead of deep inside record construction. The eight UUID-harness fixture sites were swept: bucket-maintenance browse/disk-usage fixtures adopt fixed UUIDv4 ids, and the recipient-encryption test keeps its readable/whitespace ids only as the refusal subject while the runtime bucket becomes a UUIDv4.

## Notes

The contemporaneous execution record reported no additional incident beyond the implementation and verification evidence retained above.
