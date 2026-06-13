---
step_id: S143
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S141]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S144]]"
---

# cross-domain-continuity W08.P36.S143

## Objective

Register `--output-language` on `modelo work calculate`, `verify`, and `file`.

## Changes

- `src/aeat/entrypoints/cli/_modelo.py`:
  - Added `import click` and `SUPPORTED_OUTPUT_LANGUAGES` import.
  - Added `_OUTPUT_LANGUAGE_CLI = click.Choice(SUPPORTED_OUTPUT_LANGUAGES)` constant.
  - Imported `activate_subcommand_output_language` from `._common`.
  - Added `--output-language / --language` option and `activate_subcommand_output_language` call
    to `work_calculate`, `work_verify`, and `work_file`.

## Verification

`test_work_calculate_accepts_output_language`, `test_work_verify_accepts_output_language`, and
`test_work_file_accepts_output_language` all pass. Pyright reports 0 errors on `_modelo.py`.
