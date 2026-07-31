---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:a903651b68474144c4e7ea3f8cb0b5119363c959723ec2566df8cb13c62ec4d1'
step_id: 'S18'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

# Verify W03.P05 no-shift: run pytest --collect-only -q clean, the affected aggregation / sede / oracle test modules green, and assert the calc/registry-tier anchor carriers (CasillaObservation, RegistryModeloObservation) and all role-suffixed *ObservationRequirement / *Repository / *Store / *Protocol names were NOT renamed

## Scope

- `src/aeat/application/aggregation/tests`
- `src/aeat/domain/calculations/registry/tests`

## Description

- Run `pytest --collect-only -q` over the aggregation, registry, sede, declaracion, and borrador test surfaces; observe clean collection (no import or collection errors).
- Run the affected aggregation / sede / oracle carrier test modules and observe all green.
- Assert the calc/registry-tier anchor carriers `CasillaObservation`, `RegistryModeloObservation`, and `OracleModeloObservation` were NOT renamed and remain defined in `_bindings.py`.
- Assert the role-suffixed families (`*ObservationRequirement`, `*ObservationRepository`, `*ObservationStore`, `*ObservationProtocol`, `*ObservationEnvelopePayload`) were NOT renamed and their stems are intact.

## Outcome

W03.P05 verified no-shift. Collect-only is clean (4019 tests collected, no errors). The affected carrier suites pass (341 passed across the retenciones, counterpart, retención-repository roundtrip, sede NIF-IVA, declaracion, and the two oracle modules). The anchor carriers and every role-suffixed `*Observation*` family name are unchanged, and the ledger / sede / oracle base carriers each carry a domain-discriminating prefix with no cross-tier class-name collision.

## Notes

W03.P05 closed as a verify-and-assert phase: the genuine bare-stem sede/inbound renames landed via peer relocation commits (recorded under `S16`); the ledger and oracle tiers required no rename (`S15`, `S17`). The two ledger carriers a stricter reading might further prefix are family-anchored and locale-WIP-blocked, deferred rather than family-de-syncing. No production code was modified in this phase.
