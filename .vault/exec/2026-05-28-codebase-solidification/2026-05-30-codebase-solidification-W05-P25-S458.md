---
step_id: S458
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W05.P25.S458

## Step

Introduce `OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "AEAT_OUTPUT_LANGUAGE"` in `aeat.core.i18n` and migrate `_render.py:121` + test fixtures.

## Outcome

- Added `OUTPUT_LANGUAGE_ENV_VAR: Final[str] = "AEAT_OUTPUT_LANGUAGE"` to `_render.py`.
- Replaced bare `"AEAT_OUTPUT_LANGUAGE"` at `_render.py:121` with `OUTPUT_LANGUAGE_ENV_VAR`.
- Exported from `aeat.core.i18n.__init__` with proper multi-line `__all__`.
- Migrated `core/errors/test_envelope.py` context manager (4 occurrences) to `OUTPUT_LANGUAGE_ENV_VAR`.
- Migrated `entrypoints/cli/conftest.py` `monkeypatch.setenv` to `OUTPUT_LANGUAGE_ENV_VAR`.
- 15 tests pass (output_language + render_override + envelope).

## Files touched

- `src/aeat/core/i18n/_render.py`
- `src/aeat/core/i18n/__init__.py`
- `src/aeat/core/errors/test_envelope.py`
- `src/aeat/entrypoints/cli/conftest.py`
