---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S48'
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
     The S48 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rename plugin identity, distribution pin, command, source path, metadata, and environment interpolation and ## Scope

- `src/cadrumo/agent/_workspace.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename plugin identity, distribution pin, command, source path, metadata, and environment interpolation

## Scope

- `src/cadrumo/agent/_workspace.py`

## Description

- Derive plugin, MCP, distribution, source-path, and product environment identities from `PRODUCT_IDENTITY`.
- Rename plugin and marketplace metadata to Cadrumo while preserving AEAT authority language.
- Remove former product names from generated MCP configuration and operator-workspace copy.

## Outcome

The plugin generator now emits the `cadrumo` plugin at `plugins/cadrumo`, pins
`cadrumo[agent]`, launches `cadrumo-mcp`, and configures the `cadrumo` MCP
server with `CADRUMO_MCP_PERSONA` and `CADRUMO_MCP_SURFACE`. Product-owned
metadata names Cadrumo; AEAT remains only where it denotes the tax authority,
its legal corpus, and filing boundary, while lowercase `aeat` remains the sole
human executable under the accepted CLI-executable decision.

## Notes

Ruff formatting, Ruff lint, Python compilation, scoped residue search, and
whitespace validation passed. Generated marketplace output and generator tests
remain owned by S50 and S49 respectively and were not changed here.
Formal review corrected operator copy that had initially treated the Cadrumo
product name as the human executable instead of preserving the canonical
lowercase `aeat` command.
