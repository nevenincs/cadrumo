---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-19'
modified: '2026-06-19'
step_id: 'S18'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---




# add LIRPF art. 27/28/30 to M130 casillas 01/02/03, the income and gasto bindings, and the construct, verified by registry load and legal-grounding gates

## Scope

- `src/aeat/_data/registry/aeat/modelos/130/`

## Description

Completed the M130 actividad-económica legal grounding so the income, gasto, and
rendimiento-neto casillas cite the LIRPF articles that ESTABLISH the value, not
only the pago-fraccionado computation provision.

- Add `ley-35-2006:art-27` (concept of rendimientos de actividades económicas) and
  `ley-35-2006:art-28` (reglas generales de cálculo) to casilla 01 "Ingresos".
- Add `ley-35-2006:art-28` and `ley-35-2006:art-30` (estimación directa, gastos
  deducibles) to casilla 02 "Gastos" and casilla 03 "Rendimiento neto".
- Add art-27/art-28 to both income bindings and art-28/art-30 to the
  rendimiento-neto and gasto bindings, matching each binding's concept.
- Add the union art-27/art-28/art-30 to the construct `legal_refs` so the
  registry three-layer coverage check (construct covers member casillas and
  bindings) holds.

Modified files:

- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/casillas/0001-casillas.toml`
- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0003-m130-income-cumulative.toml`
- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0004-m130-gastos-cumulative.toml`
- `src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/constructs/0001-constructs.toml`

## Outcome

Registry loads with the added refs resolving to their catalogue entries (each
carries a `corpus_ref` to the bundled consolidated LIRPF / RD 439/2007). Gates
green: `test_casilla_legal_refs_resolve`, `test_modelo_130_registry`,
`test_verification_substance`, `test_binding_value_provenance_roundtrip`
(68 passed), and the full registry + aggregation sweep (3242 passed). The
provenance test reads the casilla refs from the snapshot oracle, so it adapted
without a hardcoded change.

## Notes

The one red gate in the sweep (`test_record_design` completeness-manifest drift)
is unrelated peer WIP on Modelo 303 (closure casillas 01/04/07/28 added by a peer
without the manifest update yet); it is outside this Step's M130 surface and was
left untouched. No code changes beyond the four M130 registry files; the change is
additive grounding with no value or formula change.
