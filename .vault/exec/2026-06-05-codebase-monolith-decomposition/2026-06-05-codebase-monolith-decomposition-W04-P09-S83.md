---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S83'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S83 Core Config Route Extraction

Scope: decompose core config by settings source and validation concern behind the core config facade.

## Description

- Extract storage-route classification and active-bucket route derivation into `src/aeat/core/_config_storage_route.py`.
- Keep `classify_storage_route` and `settings_for_active_profile_bucket` exported from `src/aeat/core/config.py`.
- Preserve `load_settings` and `override_settings` in `config.py` because they own the context override state.

## Outcome

`config.py` now delegates storage-route details to a focused helper module while preserving the public core config facade.

## Notes

No consumer import path changed.
