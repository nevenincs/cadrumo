---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:9f1f29fd7c45eebb2d1f68fc9b5b4344be3f73ac47ef278fac8b229c9ed92c2d'
step_id: 'S186'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# decide whether Modelo 131 IRPF objective estimation is in scope

## Scope

- `if yes scaffold a revision with casillas and deadline_windows`
- `if no document exclusion`
- `src/aeat/_data/registry/aeat/modelos/131/`

## Description

- Ground the Modelo 131 population through the RAG index and official AEAT and BOE sources.
- Inventory the committed revision roots and inspect the period selectors, statutory authority, source provenance, and 2026 deadline windows.
- Resolve 2025 and 2026 live registry snapshots and run direct committed-registry, deadline-engine, and lint checks.
- Obtain an independent review of the replacement scope decision and the real calculation/deadline surface.

## Outcome

The original zero-revision premise is obsolete. Modelo 131 now has complete 2019-2023, 2024, 2025, and 2026 revisions, with the 2026 revision carrying real casillas, formulas, bindings, constructs, official-source provenance, and four objective-estimation quarterly windows. Live resolution selects the year-specific revisions, and direct tests exercise the calculation and deadline surface. Independent review found no material gap; the scope decision is therefore to retain this populated revision family rather than scaffold or exclude it.

## Notes

The deadline-engine test confirms objective-estimation enrollment and registry ownership. Its generic first-quarter exact-date assertion is less specific than an explicit Modelo 131 filter, but the separate live resolution and committed-registry coverage make this a minor test-precision observation, not a defect in the scope decision.
