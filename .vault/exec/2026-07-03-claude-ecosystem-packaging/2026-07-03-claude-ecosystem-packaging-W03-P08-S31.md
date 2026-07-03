---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S31'
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
     The S31 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Add a claude plugin validate --strict packaging gate that runs against a freshly materialised plugin when the claude CLI is on PATH and skips honestly when it is not (verify the validate flag against live official docs at execution time) and ## Scope

- `dev/packaging/smoke_plugin_validate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a claude plugin validate --strict packaging gate that runs against a freshly materialised plugin when the claude CLI is on PATH and skips honestly when it is not (verify the validate flag against live official docs at execution time)

## Scope

- `dev/packaging/smoke_plugin_validate.py`

## Description

- Add `dev/packaging/smoke_plugin_validate.py`, materialising a fresh plugin tree and running `claude plugin validate --strict` against it when the `claude` CLI is on `PATH`.
- Verify the `validate --strict` flag against the live official docs at execution time, per the plan's frontier-surface directive.
- Skip honestly, naming the missing tool, when the `claude` CLI is absent rather than silently passing.
- Commit `2788f3d382`.

## Outcome

- The smoke lane reports an explicit `SKIPPED` status naming the missing tool on a machine without the `claude` CLI, and a real strict-validate pass on a machine with it.

## Notes

No incidents. No skipped work.
