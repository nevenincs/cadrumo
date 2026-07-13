---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S59'
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
     The S59 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Retarget agent-harness evaluation to cadrumo-mcp and ## Scope

- `.github/workflows/agent-harness-eval.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retarget agent-harness evaluation to cadrumo-mcp

## Scope

- `.github/workflows/agent-harness-eval.yml`

## Description

- Rename the workflow and job evidence labels to Cadrumo and identify the evaluated server as `cadrumo-mcp`.
- Retarget live harness, identity, confirmation, replay, faithfulness, and provenance fixtures to canonical `cadrumo_*` tool identities.
- Use the live abbreviated `cadrumo_modelo_ivaw_balance` name where the client-visible budget contract requires it.
- Reject former executable, tool-prefix, resource-scheme, and source-path identities across the evaluated surface.

## Outcome

The standing agent-harness gate now records Cadrumo evidence and exercises the
real Cadrumo MCP server and tool namespace without a former-product alias.

## Notes

- Thirty-two focused real harness tests passed; Ruff and `actionlint` passed.
- YAML parsing and structural checks confirmed the Cadrumo workflow label, `cadrumo-mcp` job evidence, canonical source paths, and absence of former executable/path residue.
- The first replay run exposed the intentionally abbreviated IVA wallet tool name; the fixture was corrected to the live dispatch authority and the rerun passed.
- Formal review found that the live test still launched the module through `python -c`; it now spawns the real `cadrumo-mcp` console script and the focused live test passes.
