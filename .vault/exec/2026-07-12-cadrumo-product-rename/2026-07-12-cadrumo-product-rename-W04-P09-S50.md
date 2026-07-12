---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S50'
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
     The S50 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Regenerate the marketplace manifest and Cadrumo plugin subtree from the changed authority and ## Scope

- `packaging/marketplace generated output` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate the marketplace manifest and Cadrumo plugin subtree from the changed authority

## Scope

- `packaging/marketplace generated output`

## Description

- Regenerate the marketplace manifest and ignored served-plugin tree from the committed S48 authority.
- Emit only the `plugins/cadrumo` identity with the pinned Cadrumo distribution and MCP launcher.
- Compare a clean temporary emission byte-for-byte and repeat the in-place emission to prove idempotence.
- Reject former plugin, distribution, executable, URI, and environment identities from generated output.

## Outcome

The checked-in marketplace manifest now points exclusively to
`./plugins/cadrumo`. The generated served plugin is Cadrumo `0.1.1`, launches
`cadrumo-mcp` from `cadrumo[agent]==0.1.1`, and exposes only `CADRUMO_MCP_*`
product environment keys. Fourteen focused generator tests and Ruff pass.

## Notes

The served `plugins/cadrumo` subtree remains intentionally ignored and
uncommitted under the marketplace packaging contract; it was regenerated for
the following live-validator step. Existing README and `.gitignore` working
changes were present before S50 and were preserved outside this commit.
