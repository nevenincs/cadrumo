---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S13'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# add real-behavior tests proving --language no longer silently fails for help text, asserting the chosen outcome and leaving the profile-owned precedence and AEAT_OUTPUT_LANGUAGE override unchanged

## Scope

- `src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py`
- `pyproject.toml`

## Description

- Add a real-behavior test module that drives the **installed `aeat` console via subprocess** (the only path exercising the `main()` pre-parse; the in-process `CliRunner` bypasses `main()`).
- Pin the chosen make-it-work contract: `--language en` renders English leaf help, `--language es` renders Spanish, `--lang` alias localizes identically, an explicit flag overrides ambient `AEAT_OUTPUT_LANGUAGE=es`, the env-var-without-flag path is unchanged, and an invalid value is refused with the accepted-set hint.
- Add nine parametrized unit assertions over the pure `_language_from_argv` parser (no external dependency, so direct assertions are appropriate).
- Allowlist the new test module for `S603` (subprocess) in `pyproject.toml`, matching the `test_root_help_shape.py` precedent.

## Outcome

15 tests pass (6 subprocess integration tests proving real help-text localization end to end through the console, 9 pure-parser unit tests). No mocks, skips, xfail, or tautological assertions; the English/Spanish help strings asserted are distinct locale-authored values that only render in the chosen language. The profile-owned precedence and the `AEAT_OUTPUT_LANGUAGE` override are asserted unchanged.

## Notes

The subprocess tests use `shutil.which("aeat")` and a `AEAT_*`-stripped env so the only language signal is the flag under test. The dev-test passphrase is sourced via the shared `dev_test_database_password()` helper rather than `Settings(_env_file=None)`, avoiding the pre-existing pyright `reportCallIssue` on the `_env_file` kwarg.
