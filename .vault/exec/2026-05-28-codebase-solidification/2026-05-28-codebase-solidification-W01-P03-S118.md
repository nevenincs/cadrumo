---
step_id: S118
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S118 — test DEFAULT_OUTPUT_LANGUAGE routing

## Outcome

Three real-behavior tests added to `src/aeat/core/i18n/test_render_override.py`:

- `test_default_output_language_equals_es`: locks the constant value to "es".
- `test_default_output_language_exported_in_all`: asserts "DEFAULT_OUTPUT_LANGUAGE"
  is in `_render.__all__`.
- `test_fallback_language_is_default_output_language`: asserts that an invalid
  `aeat_output_language` override falls back to exactly `DEFAULT_OUTPUT_LANGUAGE`.

Landed in commit `1926f5cc4`. 51 tests pass.

## Files touched

- `src/aeat/core/i18n/test_render_override.py`

## Verification

pytest 51 passed. `vault plan step check S118` applied.
