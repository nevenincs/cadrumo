---
step_id: S142
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-07-17'
body_hash: 'sha256:7b51bb5905958cec90dab50c9bf88237554f7b844837bf89e791f01463c5429f'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S141]]"
---

# cross-domain-continuity W08.P36.S142

## Objective

Register `--output-language` on `config profile show`.

## Changes

- `src/aeat/entrypoints/cli/_config/__init__.py`: Added `--output-language / --language` option to
  `config_profile_show` and wired `_activate_subcommand_output_language` at the start of its body.

## Verification

`test_config_profile_show_accepts_output_language` passes.
