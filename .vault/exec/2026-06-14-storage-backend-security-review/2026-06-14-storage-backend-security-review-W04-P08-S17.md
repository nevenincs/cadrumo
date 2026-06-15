---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S17'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Move exported_at out of the equality-bearing portable bundle payload

## Scope

- `src/aeat/domain/user_profile/_portable_export.py`

## Description

- Document `UserProfilePortableExport.exported_at` as deliberate non-payload
  provenance metadata.

## Outcome

The bundle-determinism finding is resolved as working-as-intended: the sealed
archive uses a random AEAD nonce per seal, so a byte-stable bundle would not yield
a content-addressable archive, and the strict roundtrip gate compares re-loaded
repository objects, not this wrapper. 15 lifecycle tests green. Committed in
`4a5176c9e`.

## Notes

Chose documentation over removing the field: a precise consumer check was
obscured by tooling, and the timestamp is legitimate provenance.
