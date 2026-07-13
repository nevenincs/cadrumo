---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S52'
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
     The S52 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rename the secondary bundle manifest identity and executable and ## Scope

- `packaging/mcpb/manifest.json` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename the secondary bundle manifest identity and executable

## Scope

- `packaging/mcpb/manifest.json`

## Description

- Rename the secondary bundle identity, display copy, author, and keywords to Cadrumo.
- Hard-cut the MCP entry point and command to `cadrumo-mcp`, the product environment to `CADRUMO_MCP_PERSONA`, and product tools to `cadrumo_*` names.
- Retain AEAT only where it identifies the tax authority, BOE/AEAT legal corpus, or authority search keyword.

## Outcome

The secondary MCP bundle manifest now presents only the Cadrumo product identity
and executable contract, with no former command, tool alias, or fallback.

## Notes

- Re-execution followed the binding ADR's ratified convention: `Cadrumo` in
  sentence prose, machine identity `cadrumo`, product environment prefix
  `CADRUMO_`, human CLI `aeat`, and authority referent `AEAT`.
- The real project manifest checker reported `manifest.json valid: cadrumo 0.2.0`.
- Two manifest-focused MCPB build tests passed; later bundle-build and signing
  behavior remains assigned to S54.
- Completion audit found the root release had advanced to `0.2.1` while the MCPB
  manifest remained `0.2.0`. S52 was reopened and the manifest version was
  realigned to the root `pyproject.toml` authority without changing identity or
  prose fields.
- The existing live version-parity test required no duplication: the real
  manifest checker reported `manifest.json valid: cadrumo 0.2.1`; Ruff format,
  Ruff lint, Ty, and all six MCPB tests passed.
