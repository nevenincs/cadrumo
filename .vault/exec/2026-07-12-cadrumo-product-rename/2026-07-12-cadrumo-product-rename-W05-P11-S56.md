---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S56'
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
     The S56 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Rename manual publish choices, builders, filename guards, and Trusted Publisher expectations and ## Scope

- `.github/workflows/publish.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rename manual publish choices, builders, filename guards, and Trusted Publisher expectations

## Scope

- `.github/workflows/publish.yml`

## Description

- Rename manual publish choices and builders to `cadrumo`, `cadrumo-data-manuals`, and `cadrumo-data-official`.
- Build companions from their canonical `packaging/cadrumo_data_*` projects and guard normalized wheel filenames against the selected distribution.
- Keep the slim-wheel corpus leak and PyPI size-cap guards on Cadrumo paths.
- State that all three PyPI projects require their own confirmed Trusted Publisher registration for this workflow and environment.

## Outcome

Manual publishing now selects, builds, validates, and uploads only canonical
Cadrumo distributions. The workflow remains human-dispatched and OIDC-gated,
and it refuses mismatched, oversized, or corpus-leaking artifacts.

## Notes

- `actionlint` passed and the workflow parsed successfully as YAML.
- Structural checks confirmed the three real project names, normalized filename guards, `pypi` environment, `id-token: write`, and Trusted Publishing command.
- Former product distribution, companion, builder-path, and wheel-prefix residue was absent.
