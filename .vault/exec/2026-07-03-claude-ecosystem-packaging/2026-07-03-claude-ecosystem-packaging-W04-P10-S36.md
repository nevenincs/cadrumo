---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S36'
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
     The S36 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Define the marketplace repository layout and a .claude-plugin/marketplace.json with name, owner and a plugins[] entry sourcing the aeat plugin tree (verify the marketplace.json schema against live official docs at execution time) and ## Scope

- `packaging/marketplace/marketplace.json` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Define the marketplace repository layout and a .claude-plugin/marketplace.json with name, owner and a plugins[] entry sourcing the aeat plugin tree (verify the marketplace.json schema against live official docs at execution time)

## Scope

- `packaging/marketplace/marketplace.json`

## Description

- Define the marketplace repository layout under `packaging/marketplace/`: `.claude-plugin/marketplace.json` with name, owner object, and one `plugins[]` entry sourcing the aeat plugin tree, plus a README stating the directory is the marketplace repo content and that the plugin subtree is generated, never hand-edited.
- Commit `25932fec52`.

## Outcome

- The marketplace manifest scaffold exists for the generator (S37) to keep in lock-step with the plugin emission.

## Notes

Record authored by the coordinator from the verified commit at HEAD: the executing agent's session was terminated by the account rate limit mid-phase (S37 generator work was left as uncommitted working-tree WIP in `src/aeat/agent/_workspace.py` / `__init__.py`, preserved untouched for the resumed agent; S38 not started).
