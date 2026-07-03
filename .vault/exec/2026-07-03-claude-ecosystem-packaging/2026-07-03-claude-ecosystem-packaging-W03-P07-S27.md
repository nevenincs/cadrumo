---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S27'
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
     The S27 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Declare the userConfig persona string option with a default in the plugin manifest, keeping server-side validation as the refusal surface and ## Scope

- `src/aeat/agent/_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the userConfig persona string option with a default in the plugin manifest, keeping server-side validation as the refusal surface

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Extend `_workspace.py` to declare the `userConfig` persona string option on the plugin manifest with a default of `""`.
- Keep server-side validation (the MCP server's own persona gate) as the sole refusal surface for an invalid persona; the manifest option only exposes the client-facing configuration point.
- Landed together with `S25` and `S26` in one commit because the three facets (agents tree, `.mcp.json`, `userConfig` persona option) co-build one emission function in one file, and the plan lists them as sequential same-file Steps.
- Commit `ccb13180be`.

## Outcome

- `plugin.json` declares a `userConfig.persona` string option with an empty-string default; no client-side persona validation duplicates the server gate.

## Notes

No incidents. No skipped work.
