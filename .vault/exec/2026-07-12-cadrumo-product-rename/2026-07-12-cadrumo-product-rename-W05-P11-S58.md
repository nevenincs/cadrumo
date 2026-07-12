---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S58'
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
     The S58 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Retarget CI source paths and named product jobs and ## Scope

- `.github/workflows/ci.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retarget CI source paths and named product jobs

## Scope

- `.github/workflows/ci.yml`

## Description

- Rename the workflow and matrix job display identity to Cadrumo.
- Retarget registry verification and oracle-audit commands to the canonical executable.
- Add structural tests for Cadrumo commands, source paths, labels, and former-product absence.

## Outcome

The primary CI workflow is now `Cadrumo CI`, with a Cadrumo-owned job identifier
and display label across Ubuntu and Windows. Registry validation invokes the
canonical `cadrumo` command, while Semgrep continues to inspect `src/cadrumo`.
Generic cache identities remain tool-owned and require no product rename.

## Notes

Actionlint, direct YAML parsing, Ruff formatting and lint, two real workflow
structure tests, whitespace validation, and the focused former-product residue
gate passed. No authority-owned AEAT term was present on this workflow surface.
Formal review against the committed product-rename ADR found no unresolved
finding.
