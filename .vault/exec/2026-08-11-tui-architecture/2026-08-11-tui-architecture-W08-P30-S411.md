---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:722263b21b4cd026e453bd1a7a748774905b10b535a5058e4a80d9f186e2db49'
step_id: 'S411'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Carry an operator's Ledger selection into the areas that are entered with one. CORRECTED AFTER MEASURING THE REFUSAL RULES, which the first wording got wrong in two ways. It is THREE areas, not four: reconciliation has no door check and is reachable whenever the projection admits it. And of the three, only EVIDENCE was a composition gap -- now closed, the installed factory binds the evidence action and reads the attachment review queue. CLASSIFICATION and IMPORT are not composition gaps at all: classification refuses without a selected transaction and import without a prepared file, and neither is a fact a factory can hold at mount because both are produced by the operator inside the workspace. So what remains is NAVIGATION, not wiring: the entries and review screens must be able to carry a chosen row into the classification area, and the import action must be able to hand a prepared import back to its own area, with the controller re-composed around that state. Until that exists the two areas are correctly refused, and the navigation table should say why rather than listing a destination the session can never open.

## Scope

- `src/cadrumo/entrypoints/tui/ledger/controller.py and src/cadrumo/entrypoints/tui/ledger/routes.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py`
- `verify:` `uv run --no-sync pytest -q -m "unit or integration" src/cadrumo/entrypoints/tui/tests/test_installed_workbench.py src/cadrumo/entrypoints/tui/ledger/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

PARTIAL. The evidence door is composed; the step stays open for the navigation work its
restated action describes.

The first wording of this row was wrong on two counts, both corrected by reading the
refusal rules rather than a rendered frame. It is three refused areas, not four:
reconciliation carries no door check and is reachable whenever the projection admits it.
And only evidence was ever a composition gap. Classification refuses without a selected
transaction and import without a prepared file, and neither is a fact a factory can hold
at mount, because the operator produces both inside the workspace. Binding a stand-in
would have manufactured a selection over rows nobody chose.
