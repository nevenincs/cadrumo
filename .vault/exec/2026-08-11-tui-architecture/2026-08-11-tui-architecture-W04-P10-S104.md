---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:287e96be170487518b6f5acb057848bb8d24da6b40bca6b89fff5ff0581e2f66'
step_id: 'S104'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

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
