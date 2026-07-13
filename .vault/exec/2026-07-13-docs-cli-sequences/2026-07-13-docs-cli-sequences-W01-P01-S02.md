---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S02'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-cli-sequences with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-07-13-docs-cli-sequences-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Re-run the repaired conformance gate and capture the full inventory of latent verb-path and option-name defects it now surfaces and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
