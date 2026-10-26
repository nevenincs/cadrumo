---
tags:
  - '#reference'
  - '#modelo-history'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:fb8dab13d58af4dbfff97ec5a233d051a9bc04e16c98acecbf3de6dfdf71b350'
related:
  - "[[2026-09-07-tuimodelo-filing-lifecycle-adr]]"
  - "[[2026-07-02-arch-remediation-ports-inversion-adr]]"
---
# `modelo-history` reference: application-owned persistence boundary

## Summary

`src/cadrumo/application/modelo/history.py` is the application service for the two read projections: `assemble_work_unit_history` joins work-unit, calculation, verification, filing, and bucket-event catalogues; `assemble_modelo_lifecycle_history` filters the bucket-event catalogue by modelo, year, and period. The pre-remediation module constructed five concrete persistence adapters itself, so its application boundary depended on the adapter tree.

The accepted ports-inversion decision in `2026-07-02-arch-remediation-ports-inversion-adr.md` (amended 2026-09-11) requires application-owned ports and outer composition: domain protocols define the repository shapes, concrete encrypted repositories remain under `adapters.persistence.profile`, and an executable composition root constructs and injects them. Existing analogues are `src/cadrumo/application/modelo/calculation_action_ports.py`, `filing_action_ports.py`, and `verification_repository_ports.py`, with their concrete builders in `src/cadrumo/entrypoints/adapter_composition.py`.

The shared production root `profile_adapter_composition` already constructs all five repositories against one bucket-scoped secure-object store. A history-specific required bundle can therefore carry the existing domain repository protocols without exposing adapter DTOs or storage errors. The CLI root publishes the bundle factory in root state through `state_projection_support`; `work_history` uses the selected work unit's bucket and `modelo_history` uses the active bucket. The application service keeps its existing application DTOs (`WorkUnitHistory`, `ModeloLifecycleHistory`) and its `WorkUnitNotFoundError` translation for malformed or absent work-unit selection.
