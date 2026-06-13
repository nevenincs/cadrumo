---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S121'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W05.P17.S121 file-discovery blast-radius audit

Scope:
- `fd blast-radius inventory`

## Description

- Run `fd` over modelo, work, revision, reconcile, project, compare, locale, quickstart, and filing-spine surfaces.
- Classify discovered production, test, documentation, locale, generated reference, and API documentation surfaces for later W05 closure.
- Exclude vendored data and generated build output from the discovery pass.

## Outcome

The source-tree file-discovery blast radius includes these implementation groups:

- Application modelo services: `_actions.py`, `_selectors.py`, `_revision_persistence.py`, `_export.py`, `_reconcile.py`, `_history.py`, `_taxation_comparison.py`, and `_result_summary.py`.
- Application adjacent projections: `src/aeat/application/state_projection.py` and projection/reconciliation consumers.
- Domain records and repositories: work unit, calculation revision, filing record, work-unit repository, calculation repository, and filing repository modules.
- CLI implementation: `src/aeat/entrypoints/cli/_modelo.py`, `src/aeat/entrypoints/cli/_modelo_payloads.py`, and `src/aeat/entrypoints/cli/_modelo_work.py`.
- Locales: `src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`, `src/aeat/locales/ca.yml`, and `src/aeat/locales/hu.yml`.
- User docs: getting-started, tutorial, filing-spine, quickstart, modelo 303, modelo 390, reconcile, and how-to index pages.
- Generated/API docs: `docs/cli/app.rst` and API reference pages for touched application/domain modules.
- Tests: CLI work UX, natural-key, ID type hint, export, reconcile, projection, compare, history, calculate, workflow resume, payloads, and application selector/persistence tests.

## Notes

- Discovery commands excluded `docs/_build` and `__pycache__`; generated HTML was not
  treated as an editable source surface.
- `fd` established the source file inventory and `rg -l` cross-checked files that
  mention work-unit, calculation-revision, work lifecycle, export, reconcile,
  project, and compare terms.
- This step records blast radius, not implementation completeness.
- S122 through S126 remain open for final classification and closure verification after implementation changes land.
