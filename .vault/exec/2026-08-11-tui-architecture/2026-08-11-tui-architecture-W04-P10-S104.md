---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:efac91e386310f332e7a4ef3e98ccf862203451bbe821b19009faac43f72630c'
step_id: 'S104'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S104 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Relocate the sole Casilla review screen and tests to the canonical Modelo view as a read-only consumer of the existing public application.modelo ModeloWorkReview facade, preserve named-outlier evidence, delete the legacy inbound screen, facade exports, and locale references atomically without compatibility, and provide the migration evidence consumed by the interface C1 exit validator and ## Scope

- `src/cadrumo/entrypoints/tui/modelo/view and src/cadrumo/adapters/inbound/tui/_modelo_work_review_screen.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Relocate the sole Casilla review screen and tests to the canonical Modelo view as a read-only consumer of the existing public application.modelo ModeloWorkReview facade, preserve named-outlier evidence, delete the legacy inbound screen, facade exports, and locale references atomically without compatibility, and provide the migration evidence consumed by the interface C1 exit validator

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view and src/cadrumo/adapters/inbound/tui/_modelo_work_review_screen.py`

## Description

- Hard-move the Modelo work-review contracts and builder to the public `application.modelo.work_review_projection` defining module.
- Hard-move the sole Textual review view and tests to `entrypoints.tui.modelo.view.work_review` and its owning test package.
- Move reusable real review test setup to `cadrumo.tests.modelo_work_review` and remove the private cross-package test fixture reach.
- Delete the legacy inbound review screen, private application modules, facade exports, locale references, API stubs, ignored bytecode, and all compatibility residue.
- Supply zero-remnant migration evidence for the interface C1 validator.

## Outcome

Modelo work review now has exactly one frontend-neutral application definition and one canonical TUI view. Consumers import both defining modules directly; package initializers republish neither surface. The retired inbound TUI directory is physically absent.

Independent review approved S104 after remediation. Focused evidence includes 11 review/CLI unit tests, 13 TUI integration tests, clean Ruff/format/type/docs gates, and 29 passing zero-remnant migration gates.

## Notes

The historical 515-row migration census was stale authority after hard deletion. S88 replaces it with a planted, fail-closed zero-remnant detector; no legacy count, digest, disposition, shim, or allowlist remains.
