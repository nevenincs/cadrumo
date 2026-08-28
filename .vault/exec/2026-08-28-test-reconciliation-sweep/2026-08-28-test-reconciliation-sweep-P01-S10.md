---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:de1df508646fbfbeda359805104a008ea5f6bdab633809808f18d250186ff951'
step_id: 'S10'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Author a per-modelo requiredness capability so the profile schema can express a modelo-scoped required fact without over-demanding it

## Scope

- `src/cadrumo/application/user_profile/`

## Changes

- `M` `src/cadrumo/domain/user_profile/schema.py`
- `M` `src/cadrumo/application/user_profile/preflight.py`
- `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `A` `src/cadrumo/application/user_profile/tests/test_preflight_modelo_scoped_requirement.py`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_preflight_modelo_scoped_requirement.py` -> `pass`
- `verify:` `pytest src/cadrumo/application/user_profile/tests/test_preflight_reports_unassessed_axis.py` -> `pass`
