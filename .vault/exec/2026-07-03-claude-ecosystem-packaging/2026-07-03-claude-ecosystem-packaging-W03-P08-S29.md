---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S29'
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
     The S29 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Extend the aeat app agent CLI with a plugin layout target option selecting the plugin materialisation over the workspace layout and ## Scope

- `src/aeat/entrypoints/cli/_app_agent_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the aeat app agent CLI with a plugin layout target option selecting the plugin materialisation over the workspace layout

## Scope

- `src/aeat/entrypoints/cli/_app_agent_workspace.py`

## Description

- Extend `_app_agent_workspace.py` with a `--layout plugin|workspace` Typer enum option selecting plugin materialisation over the existing workspace layout.
- Add the corresponding en/es/ca/hu locale keys through the locales CLI (`python -m aeat.locales set` / `scaffold`), never by hand-editing the catalogues.
- Commit `9d07e95585`.

## Outcome

- `python -m aeat.locales scaffold --check` clean at commit time.

## Notes

Committed after `S30` even though the plan lists `S29` first: the CLI option imports the payload/enum `S30` adds, so `S30` had to land first to keep collection green. No incidents. No skipped work.
