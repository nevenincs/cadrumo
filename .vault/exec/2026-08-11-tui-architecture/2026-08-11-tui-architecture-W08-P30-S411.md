---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:27ee1eaf0b636f97a361813ca946840dec86e9b0da680fd6cb7f448d0b3454b7'
step_id: 'S411'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Carry an operator's Ledger selection into the areas that are entered with one. CORRECTED AFTER MEASURING THE REFUSAL RULES, which the first wording got wrong in two ways. It is THREE areas, not four: reconciliation has no door check and is reachable whenever the projection admits it. And of the three, only EVIDENCE was a composition gap -- now closed, the installed factory binds the evidence action and reads the attachment review queue. CLASSIFICATION and IMPORT are not composition gaps at all: classification refuses without a selected transaction and import without a prepared file, and neither is a fact a factory can hold at mount because both are produced by the operator inside the workspace. So what remains is NAVIGATION, not wiring: the entries and review screens must be able to carry a chosen row into the classification area, and the import action must be able to hand a prepared import back to its own area, with the controller re-composed around that state. Until that exists the two areas are correctly refused, and the navigation table should say why rather than listing a destination the session can never open.

## S14 corrective quarantine (2026-09-05)

The import-preparation operator reachability work recorded below was removed from production because this row remains `DISPLACED_AND_HELD_UNTIL_G3`. The prior IMPORT `CLOSED` claim is therefore superseded: there is no Overview path-entry route, controller admission, installed import submitter, import operator action, or TUI-only producer/coverage. The canonical application validator at `application/ledger/import_preparation.py` and its direct application tests remain backend-only. This record does not authorize reimplementation; clitui-ledger remains the sole owner through W05.P21.S136, with W05.P19.S128 as the disposition checkpoint.

The parallel Ledger classification production additions are likewise quarantined. Installed composition no longer builds or injects a classification submitter, and the controller no longer derives a target from entry selection. The dormant contracts, refusal path, screens, messages, and direct submission boundary remain; installed composition retains the classify action but no classification mutation door. The later descriptions of closed CLASSIFICATION wiring are historical context and are superseded by this quarantine.

## Scope

- `src/cadrumo/entrypoints/tui/ledger/controller.py and src/cadrumo/entrypoints/tui/ledger/routes.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/controller.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_flows.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_workspace.py`
- `verify:` `uv run --no-sync pytest -q -n 0 -m "" src/cadrumo/entrypoints/tui/ledger/tests` -> `pass` (60)

## Notes

Step remains `DISPLACED_AND_HELD_UNTIL_G3`. The classification-selection behavior and installed classification submitter were removed as held work; dormant component contracts, screens, messages, direct submission boundary, and refusal path remain.
