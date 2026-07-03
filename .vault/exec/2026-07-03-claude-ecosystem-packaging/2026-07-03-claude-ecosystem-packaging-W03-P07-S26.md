---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S26'
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
     The S26 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Emit the plugin .mcp.json declaring the stdio aeat-mcp server launched via uvx aeat at a pinned version with AEAT_MCP_PERSONA wired from the userConfig persona interpolation and ## Scope

- `src/aeat/agent/_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit the plugin .mcp.json declaring the stdio aeat-mcp server launched via uvx aeat at a pinned version with AEAT_MCP_PERSONA wired from the userConfig persona interpolation

## Scope

- `src/aeat/agent/_workspace.py`

## Description

- Extend `_workspace.py` to emit the plugin `.mcp.json`, declaring the stdio `aeat-mcp` server launched via `uvx --from aeat==<version> aeat-mcp` at a pinned version.
- Wire `AEAT_MCP_PERSONA` from the `${user_config.persona}` interpolation so the persona selected in the client's `userConfig` reaches the launched server.
- Landed together with `S25` and `S27` in one commit because the three facets (agents tree, `.mcp.json`, `userConfig` persona option) co-build one emission function in one file, and the plan lists them as sequential same-file Steps.
- Commit `ccb13180be`.

## Outcome

- The emitted `.mcp.json` launches `aeat-mcp` at a pinned version with the persona sourced from user configuration, never hardcoded.

## Notes

No incidents. No skipped work.
