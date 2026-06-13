---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'S16'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01.S16`

Promote `src/aeat/entrypoints/cli/_config.py` from a single module to the `_config/` package so that the google sub-CLI ships inside the package from the start (drift-corrected execution order pins S16 before S04 per the plan's Drift Amendments section).

- Moved: `src/aeat/entrypoints/cli/_config.py` → `src/aeat/entrypoints/cli/_config/__init__.py` (via `git mv` for history preservation)
- Modified: relative imports in the moved file bumped one level (`...application` → `....application`, `...domain` → `....domain`, `...core` → `....core`, `._common` → `.._common`, `._errors` → `.._errors`, `._i18n` → `.._i18n`)

## Description

The original `_config.py` lived at `cli/_config.py`, so `from ...application` resolved to `aeat.application` (three-dot = package three levels up from a module inside `cli/`). The promoted `_config/__init__.py` lives one level deeper, so the same physical target is four dots away. All 30+ parent-package imports and the 3 sibling imports (`_common`, `_errors`, `_i18n`) were retargeted to keep the import targets identical.

The package body is otherwise unchanged: every Typer sub-app (`app`, `profile_app`, `auth_app`, `doctor_app`, `bucket_app`), every command (`config_root`, `doctor`, `doctor_logs`, `doctor_quarantine`, `config_list`, `config_get`, `config_set`, `config_unset`, `config_status`, `config_reset`, `auth_providers`, `auth_configure`, `auth_status`, `auth_test`, `auth_clear`, `bucket_history`), and every registration call (`app.add_typer(...)`) lives at the same import path as before.

Both downstream importers continue to work without changes:

- `src/aeat/entrypoints/cli/__init__.py:43` — `from . import _config` resolves to the package init module.
- `src/aeat/entrypoints/cli/test_apex_workflow_verification.py:15` — `from . import _config, app, app_app` resolves identically.

S04 onward will land new modules as siblings inside `_config/` (specifically `_config/_google.py` per the plan's drift-amended path).

## Tests

- `from aeat.entrypoints.cli import _config; _config.app.info.name` returns `"config"`; `profile_app` and `bucket_app` resolve as before.
- `ruff check src/aeat/entrypoints/cli/_config/__init__.py` clean.
- `pytest src/aeat/entrypoints/cli/test_apex_workflow_verification.py` 4/4 passed.
