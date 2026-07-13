---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S51'
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
     The S51 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Validate the regenerated marketplace and plugin with the live strict Claude validator and ## Scope

- `packaging/marketplace validation evidence` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Validate the regenerated marketplace and plugin with the live strict Claude validator

## Scope

- `packaging/marketplace validation evidence`

## Description

- Run the repository plugin-validation smoke with the live Claude CLI.
- Validate the committed Cadrumo plugin subtree and marketplace root directly under strict mode.
- Assert the generated plugin name, source, distribution pin, MCP command, and environment interpolation.
- Reject former plugin, distribution, MCP, source-path, and product-copy residues in generated manifests.

## Outcome

Claude CLI 2.1.207 accepted all three strict validation surfaces. The repository
smoke returned `validated` after materialising 34 skills and 7 agents. Direct
strict validation passed for both `plugins/cadrumo` and the marketplace root.

Generated identity assertions confirmed plugin and MCP server `cadrumo`, source
`./plugins/cadrumo`, launcher `uvx`, pin `cadrumo[agent]==0.1.1`, executable
`cadrumo-mcp`, and the two `CADRUMO_MCP_*` user-config interpolations. The
focused former-product residue gate found no obsolete plugin, distribution,
MCP, source-path, or CLI branding in the three generated manifests.

## Notes

This evidence establishes strict manifest validation and generator identity
alignment only. It does not claim plugin installation, package publication,
network retrieval, MCP process startup, or end-to-end runtime behavior.

Formal review against the committed product-rename ADR and canonical
`PRODUCT_IDENTITY` found no unresolved finding. An unapproved executable
decision outside the committed governing chain was not used as acceptance
authority.
