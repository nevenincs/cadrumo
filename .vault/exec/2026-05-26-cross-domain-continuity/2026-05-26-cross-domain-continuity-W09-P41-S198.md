---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S198'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# delete duplicate AuthProviderReservedError registration

## Scope

- `the class is registered twice at lines 62-65 and 106-109`
- `src/aeat/core/errors/registry/_application.py`

## Description

Removed the duplicate `AuthProviderReservedError` registration in `src/aeat/core/errors/registry/_application.py` (the second of the two `REFUSED_AUTH_PROVIDER_RESERVED` ErrorCode entries). The registry now has 106 unique declared codes, zero duplicates (verified by Counter on the tuple-key list). The 33 error-registry tests under `src/aeat/core/errors/` continue to pass.

## Outcome

Closed by direct code edit; see Description above.

## Notes

Real cleanup, not audit-based — duplicate registrations were live in the registry and the alias was unused.
