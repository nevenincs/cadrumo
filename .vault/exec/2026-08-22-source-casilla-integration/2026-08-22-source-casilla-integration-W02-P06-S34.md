---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9f59e453a217a400511dc5c6d944898b2e3dbcf1a87e534dd5062d722d28366f'
step_id: 'S34'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# remove or correct the stale Anexo D casilla 0155 intent after adjudication

## Scope

- `src/cadrumo/domain/contribuyente/inventory/__init__.py`

## Description

- Remove the obsolete signed inventory-variation helpers and every code claim that inventory maps to casilla `0155`.
- Add a strict frozen 2025 projection that records its opening and closing basis and splits variation exclusively between `0177` and `0182`.
- Refuse unsupported years, cross-year movements, non-cent result values, and unexplained conflicts between explicit and movement-derived closing values.
- Keep acquisition cost for `0181` absent until its complete source fact is implemented, and retain the census disposition as `connect_candidate`.
- Update the reviewed capability identity and architecture wording without claiming a live inventory resolver.
- Add focused projection tests and obtain a formal code review.

## Outcome

The stale `0155` API has no compatibility alias or remaining source reference. The new projection is activity-scoped by its ledger, grounded only for 2025, auditable from its stored basis, mutually exclusive by construction, and deliberately non-authoritative for purchases. Eight projection tests plus the inventory application, encrypted persistence, and CLI payload regressions pass.

## Notes

The source-connectivity comparison and census suites could not reach this change because unrelated concurrent command-spec work is structurally unresolved in `_modelo_work_command_specs.py`. The documentation build likewise reached an unrelated missing Modelo 210 Spanish locale key; its other sixteen tests passed. The formal review reported no high or critical findings; its medium cross-period and low cent-normalisation findings were resolved before closure.
