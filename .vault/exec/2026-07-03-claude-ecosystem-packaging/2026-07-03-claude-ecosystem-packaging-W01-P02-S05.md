---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S05'
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
     The S05 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Demote vaultspec-rag[mcp] out of [project.dependencies] into the dev dependency group so a published product wheel carries no developer search tooling and ## Scope

- `pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Demote vaultspec-rag[mcp] out of [project.dependencies] into the dev dependency group so a published product wheel carries no developer search tooling

## Scope

- `pyproject.toml`

## Description

- Demote `vaultspec-rag[mcp]` from `[project.dependencies]` to the dev dependency group, consolidating the `[mcp]` extra and the `>=0.2.28` pin into the existing dev entry.
- Grep-verify production `src/aeat` carries zero `vaultspec_rag` imports before the demotion.
- Regenerate `uv.lock`.
- Commit `d15b484dfa`.

## Outcome

- A published product wheel no longer carries the developer semantic-search stack; the dev loop keeps it via the dev group.

## Notes

No incidents. No skipped work.
