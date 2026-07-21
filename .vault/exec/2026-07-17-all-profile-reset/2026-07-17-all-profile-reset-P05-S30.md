---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S30'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace all-profile-reset with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S30 and 2026-07-17-all-profile-reset-plan placeholders are machine-filled by
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
     The Prove the removed reset and sandbox spellings are absent from every source and generated surface and ## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove the removed reset and sandbox spellings are absent from every source and generated surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

- Extend `test_root_grammar_invariants.py`: prove `config reset` mounts exactly start/status/resume (no flat/DATA/AUTH/profile action), rejects the retired `--scope` flag on the group and leaves, that `config profile sandbox use` and `config profile use` are unmounted, and that `config profile sandbox use` / `config reset --scope` / `reset --scope` are absent from source, locales, docs, and sequence contracts (probe files exempted).
- Clear the two production-source citations the absence scan would otherwise catch: reword the `_custody.py` switch-resolver docstring to drop the literal `sandbox use`, and drop the stale `config reset --scope` example from the `_input_schema.py` MCP comment.

## Outcome

17 grammar invariants pass (5 new). The absence scan is green, confirming no `.py`/`.yml`/`.md`/`.seq` operator or harness surface carries a removed reset/sandbox spelling. Every removed spelling refuses on the live surface (exit code 2).

## Notes

The generated terminology evaluation dataset (`_data/terminology/evaluation/coverage-report.json`) still names the old command but is a `.json` artifact outside the operator/harness scan surface; recorded in the S29 record for the lead's terminology regeneration.
