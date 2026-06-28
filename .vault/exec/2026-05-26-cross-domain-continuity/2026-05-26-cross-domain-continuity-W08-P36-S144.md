---
step_id: S144
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S141]]"
  - "[[2026-05-26-cross-domain-continuity-W08-P36-S143]]"
---

# cross-domain-continuity W08.P36.S144

## Objective

Regression test asserting every S141-S143 target command (and the pre-existing auth commands)
accepts `--output-language`.

## Changes

- `src/aeat/entrypoints/cli/test_output_language_parity.py` (new file): 10 tests covering
  `auth clear`, `auth providers`, `auth configure`, `config profile show`,
  `trabajo work calculate`, `work verify`, `work file` (new, S141-S143) and
  `auth status`, `auth login`, `auth test` (existing, anti-regression guards).
  Uses `--help` introspection via real CLI runner; no active profile required.

## Verification

10/10 tests pass in 2.52s. This test fails on any regression where a command drops the flag.
