---
step_id: S141
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S142]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S143]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S144]]"
---

# cross-domain-continuity W08.P36.S141

## Objective

Register `--output-language` on `auth clear`, `auth providers`, and `auth configure`.

## Changes

- `src/aeat/entrypoints/cli/_common.py`: Added `activate_subcommand_output_language` as a
  shared helper (previously private in `_config/__init__.py`).
- `src/aeat/entrypoints/cli/_config/__init__.py`:
  - Moved `_OUTPUT_LANGUAGE_CLI = click.Choice(SUPPORTED_OUTPUT_LANGUAGES)` before the first
    profile_app command (was defined after, causing `NameError` when profile commands used it).
  - Replaced `_activate_subcommand_output_language` body with a delegation to the shared helper.
  - Added `--output-language / --language` option to `auth_providers`, `auth_configure`, and
    `auth_clear`.

## Verification

All 10 parity tests in `test_output_language_parity.py` pass. Locale audit clean.
