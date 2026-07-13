---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S57'
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
     The S57 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rename packaging smoke labels, commands, and evidence artifacts and ## Scope

- `.github/workflows/packaging-smoke.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename packaging smoke labels, commands, and evidence artifacts

## Scope

- `.github/workflows/packaging-smoke.yml`

## Description

- Rename the packaging-smoke workflow, job, and step labels to sentence-prose
  Cadrumo, and uploaded evidence artifacts to lowercase machine `cadrumo`.
- Retain the host/core lane and explicitly execute the split-distribution and clean-Docker gates.
- Add a real-workflow structural test for canonical recipes, evidence paths,
  product identity, and the binding human-executable boundary.
- Reject former package/import identity and `cadrumo` as a human command without
  banning the valid `aeat` executable from command contexts.

## Outcome

The GitHub workflow presents sentence-prose `Cadrumo Packaging Smoke` labels,
uses machine job and evidence names `cadrumo-packaging-smoke` and
`cadrumo-packaging-smoke-evidence`, and runs the canonical Linux/core,
split-distribution, and Docker recipes. Those recipes own the installed-product
probes and invoke the sole human CLI as `aeat`; the workflow does not introduce
a direct `cadrumo` human command.

The structural contract separates labels from commands: `aeat` remains invalid
as product branding or a former package/import root, but remains valid as the
binding executable in a command context. Former `import aeat`, `python -m aeat`,
`src/aeat`, packaging paths, and former distributions are rejected explicitly.

## Notes

The focused real split-wheel installation test exceeds the bounded S57
structural-test window and was not needed to validate workflow wiring; its
canonical recipe is retained and resolves successfully through `just --dry-run`.

YAML parsing, the Linux/core, split-distribution, and Docker recipe dry-runs,
six focused workflow/Docker structural tests, Ruff, formatting, and Ty pass.
