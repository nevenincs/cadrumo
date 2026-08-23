---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:00bb872057bdc242234dfca54344a125fa65df7e07ca04e4b2529f4aa0c291c2'
step_id: 'S41'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# supply the encrypted inventory repository through calculation orchestration

## Scope

- `src/cadrumo/application/modelo/_calculation_actions.py`

## Description

- Compose the enrolled inventory resolver through the production bucket source mesh.
- Construct its encrypted repository only when the active revision declares an inventory binding.
- Bind secure storage explicitly to the work unit bucket and preserve canonical mesh-stage validation.
- Add real encrypted success, absence, corruption, bucket isolation, laziness, construction-count, and confidentiality proofs.

## Outcome

The production calculation action now supplies `InventorySourceResolver` with an `InventoryLedgerRepository` backed by the secure-object repository for the active work-unit bucket. Construction occurs only when the selected revision declares an inventory binding; revisions without inventory bindings allocate no inventory secure store, repository, or load.

The resolver runs once through the canonical mesh-stage guard and retains the S39 contracts for source-owned values, stable identity, sealed projection fingerprint, retained conflict diagnostics, and value-free storage degradation. No root-profile fallback, unencrypted state, alternate repository, CLI prompting, caller-override rule, registry binding, or census claim was introduced.

Independent review reported zero findings. Forty-nine broader focused tests passed, and Ruff, the focused type checker, and scoped diff hygiene were clean.

## Notes

The non-tautological orchestration tests spy on the secure factory, repository constructor and load, and route-stage guard while separately exercising real encrypted storage. Review requested a canonical `CalculationRouteStage` annotation on the route spy; the correction removed the only type-check failure before final clearance. Caller ownership remains S42 and registry bindings remain S43 and later.
