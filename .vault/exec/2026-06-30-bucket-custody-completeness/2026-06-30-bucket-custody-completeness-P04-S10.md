---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Merge the carried bucket event-history catalogue idempotently and rebuild the participation index after import

## Scope

- `src/aeat/application/user_profile/_bundle.py`

## Description

- Restore carried bucket event-history rows through the generic secure-object carry path.
- Rebuild the derived transaction participation index after bundle import.
- Route the rebuild through the defining participation-index module, not the `application.modelo` package facade.

## Outcome

- Complete. Imported buckets regain durable audit history and rebuild derived participation state from restored typed catalogues.
- Verified by focused custody tests, participation rebuild coverage through import, ruff, and reviewer pass.

## Notes

- The direct-source import rewrite in `deserialize_profile_bundle` was part of the final no-reexports hardening pass.
