---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S32'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S32 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Test the CLI materialises a schema-valid plugin tree end-to-end to an output directory and ## Scope

- `src/aeat/entrypoints/cli/tests/test_app_agent_plugin.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Test the CLI materialises a schema-valid plugin tree end-to-end to an output directory

## Scope

- `src/aeat/entrypoints/cli/tests/test_app_agent_plugin.py`

## Description

- Add `test_app_agent_plugin.py` proving the CLI's `--layout plugin` option materialises a schema-valid plugin tree end-to-end to an output directory.
- Absorb the pre-existing stale flat-path assertions in `test_app_agent_workspace.py` that the `--layout plugin` addition made incorrect (coordinator-approved in-scope regression fix, per the shared-worktree discipline of fixing regressions a campaign's own change touches).
- Commit `40712a6ffb`.

## Outcome

- New end-to-end plugin CLI test passes; the absorbed `test_app_agent_workspace.py` assertions are corrected rather than left red.

## Notes

No incidents. No skipped work.
