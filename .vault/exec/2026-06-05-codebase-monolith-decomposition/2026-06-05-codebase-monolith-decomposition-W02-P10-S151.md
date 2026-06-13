---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S151'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S151 Secret Custody Transport Split

Scope: `src/aeat/entrypoints/cli/_config/_custody.py`; `src/aeat/entrypoints/cli/_config/_custody_secret.py`; config custody tests.

## Description

- Extracted lock, rekey, recover, show-recovery, and verify-recovery command registration from `_custody.py` into `_custody_secret.py`.
- Left `_custody.py` focused on profile unlock routing and registrar composition.
- Kept all secret-store policy calls in application services; the new module remains a Typer transport helper.

## Outcome

The config custody surface is split by responsibility without changing operator command names or payload behavior.

## Notes

Verification passed for `test_config_custody_profile_lifecycle.py` and `_config/tests/test_config.py` with the integration marker, plus ruff on the touched custody modules.
