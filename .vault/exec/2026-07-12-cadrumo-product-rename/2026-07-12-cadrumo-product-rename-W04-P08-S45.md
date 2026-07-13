---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S45'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S45 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rename MCP prompts and product-facing tool copy and ## Scope

- `src/cadrumo/entrypoints/mcp/_prompts.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename MCP prompts and product-facing tool copy

## Scope

- `src/cadrumo/entrypoints/mcp/_prompts.py`

## Description

- Rename the orientation prompt, title, and operating brief to Cadrumo.
- Delegate embedded prompt URI construction to the canonical MCP resource helper.
- Preserve AEAT wording only where it denotes the Spanish tax authority or its period codes.
- Prove Cadrumo prompt names, copy, and embedded resource URIs through the real prompt and server surfaces.

## Outcome

MCP guided prompts now expose one Cadrumo product identity and use the
`cadrumo://` resource contract without a duplicate URI scheme authority.
Focused Ruff checks and all ten MCP prompt integration tests pass.

## Notes

The two prompt-test URI expectations originated with the concurrent S44
resource-scheme change. The S44 owner confirmed `resource_uri` as the final
constructor and explicitly transferred those cohesive assertions to S45; no
changes were made to `_resources.py` in this step.
