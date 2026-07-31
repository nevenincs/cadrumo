---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:bba5e0c1fc83caa6517713e7d1aa521d8a66a684e00b3f794e53eba57cf66aef'
step_id: 'S02'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Re-run the repaired conformance gate and capture the full inventory of latent verb-path and option-name defects it now surfaces

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`

## Description

- Re-run the repaired gate under the `integration` marker; write full output to disk (`scratchpad/s02-gate-run.log`), never truncated upstream of the file write.
- Probe the parsed-invocation count directly across the doc surface to distinguish a clean surface from a still-vacuous gate.
- Confirm the option-validity layer is genuinely exercised, not silently dropping tokens.

## Outcome

The gate is non-vacuous: it now decomposes 591 cited invocations across 58 docs (was ~0), of which 393 carry at least one option, for 1096 option tokens validated. The full gate run is green (60 passed). The complete latent-defect inventory the repaired gate surfaces is: zero documented-command defects across the how-to, tutorial, explanation, and runbook surface. The verb-path layer was already kept honest by the sibling verb-only educational gate; the option-name and dead-subcommand-under-live-group layers surface no additional defects.

## Notes

A direct `python -c` probe of `_validate_command` tripped a `FormerProductStateError` (a retired `aeat.db` present in the ambient state root) when materialising the Click tree outside the test harness; this is an environment artifact of bare invocation, not a gate defect. The pytest run itself uses isolated storage roots and passed cleanly, and `test_live_introspection_matches_reality` independently proves the validator flags bad options and dead subcommands.
