---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S199'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# delete duplicate AuthConfigureDanglingActiveProfileError registration

## Scope

- `the class is registered twice at lines 84-92 and 95-103`
- `src/aeat/core/errors/registry/_application.py`

## Description

Removed the duplicate `AuthConfigureDanglingActiveProfileError` registration in `src/aeat/core/errors/registry/_application.py` (the second of the two `REFUSED_AUTH_CONFIGURE_DANGLING_ACTIVE_PROFILE` ErrorCode entries). Co-landed with the S198 dedup since both lived in the same adjacent duplicate-pair block. Registry now has 106 unique declared codes.

## Outcome

Closed by direct code edit; see Description above.

## Notes

Real cleanup, not audit-based — duplicate registrations were live in the registry and the alias was unused.
