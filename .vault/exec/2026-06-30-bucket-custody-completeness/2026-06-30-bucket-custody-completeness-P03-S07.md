---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S07'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Add a CustodyProfile parameter to serialize_profile_bundle and read carry-set secure objects generically through the substrate

## Scope

- `src/aeat/application/user_profile/_bundle.py`

## Description

- Add the `custody_profile` selector to `serialize_profile_bundle`.
- Enumerate carried secure-object namespaces from the storage namespace registry.
- Read generic secure-object rows through the active bucket substrate.
- Harden the final implementation to import real source modules directly rather than package reexports.

## Outcome

- Complete. Structured profile export remains the cleartext default; sealed archive export passes the full profile explicitly.
- Verified by focused custody tests, CLI profile export/import integration, ruff, direct-source import scan, and reviewer pass.

## Notes

- The final hardening pass replaced package-facade imports in `src/aeat/application/user_profile/_bundle.py`, `src/aeat/application/user_profile/_custody_carry.py`, and related transport callers.
