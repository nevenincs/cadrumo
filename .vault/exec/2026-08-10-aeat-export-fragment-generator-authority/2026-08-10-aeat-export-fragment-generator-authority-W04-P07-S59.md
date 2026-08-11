---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:c14732157751fe86ace46b1f4bbe0a756a11e8da72294a605c457149b75ce94f'
step_id: 'S59'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Establish the single annual Orden registry authority by authoring ActividadOrdenAnualId, the immutable year/revision-scoped Orden projection, and ActividadOrdenAnualRef with Orden id, ejercicio, registry revision, and canonical source/content digest, exposing one snapshot resolver for Orden and active record-design epoch, and deleting test-only rows, parallel selectors, parameter-table redeclarations, and runtime inference. Own only the required closed calculation-scope input whose not-claimed value is neutral and whose evidence-required value refuses pending S58. Do not derive secure-profile composition or own any regime-composition enum, positive censo applicability, or filing-evidence owner because S55 owns profile mapping and S58 owns evidence-bearing applicability

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/domain/iva/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/_data/registry/`

## Description

- Compile each 2023-2026 annual Orden from its pinned BOE HTML through one neutral DOM parser.
- Generate and strictly verify paired JSON and Markdown sidecars, semantic Annex II anchors, table-scoped legal references, and the closed manifest.
- Expose one immutable year, revision, source, content-digest, activity, and active-design-epoch snapshot.
- Migrate M303 simplified-regime formulas from the retired coefficient tables to canonical Orden identities and seven module inputs.
- Enforce a required explicit not-claimed or evidence-required scope input without deriving profile composition or claiming positive censo applicability.
- Delete caller-supplied Orden tuples, raw-IAE selection, silent-zero expectations, duplicate module-order validation, retired Annex I test anchors, and the five parallel coefficient tables.
- Reconcile the governing ADRs and preserve S58 as the sole owner of evidence-bearing applicability.

## Outcome

The annual Orden is now the sole M303 module-coefficient authority for every supported filing year. Each year contains exactly 49 activity tables and 141 module rows, and registry loading refuses stale, incomplete, extra, cross-year, or sidecar-divergent authority. Formula evaluation resolves the immutable snapshot rather than a parallel parameter table. Not-claimed scope remains neutral and rejects simplified rows; evidence-required scope refuses until S58 creates immutable evidence. S55 later owns the required persisted profile composition and exact mapping into this input.

The corrected isolated candidate passed 25 annual-authority and engine tests plus 2 real `build_draft` boundary tests, the annual-Orden generator check, targeted Ruff, and full registry verification. Fresh formal review of the corrected ownership boundary remains the final closure gate.

## Notes

The first scope-refusal fixture used an invalid casilla id and therefore exercised strict casilla validation before the intended guard. It was corrected to use empty formula inputs plus the real prior-compensation binding and the canonical refusal message. Positive censo evidence and `FilingEvidenceReference` remain explicitly outside S59 and belong to S58. Two pre-existing M210 type diagnostics and an unrelated deduction-authority fixture remain outside this step.
