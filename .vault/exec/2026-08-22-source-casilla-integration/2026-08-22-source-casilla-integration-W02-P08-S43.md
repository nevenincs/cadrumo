---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:165c215681e90eec7ac930d2fc9312358f3f092b2114d5a79a1fb2303d57d7b3'
step_id: 'S43'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# add grounded inventory operation row-template bindings for supported M100 revisions without taxpayer activity identities

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions`

## Description


- Add exactly three 2025 Modelo 100 inventory activity row-template bindings for 0177, 0181, and 0182.
- Use the canonical inventory source, `rows` aggregation, and S172 selector vocabulary without taxpayer activity identity.
- Ground each template in LIRPF article 30 and the accepted 2025 Renta manual with validated source citations.
- Prove exact hydrated membership, operation/destination identity, absence from 2024, and refusal of legacy selector vocabulary.

## Outcome

The supported 2025 Modelo 100 revision now declares one registry-owned inventory row template for each adjudicated operation: positive closing increase, complete acquisition cost, and positive closing decrease. Runtime activity identity remains exclusively S176-owned and no wildcard, fabricated row identifier, stale 0155, or other-year copy exists.

The registry validates without S44 casilla `binding_ids` linkage, so that step remains separate. Independent review reported zero findings. The owner registry/selector/build selection passed 60 tests; the independent combined selection passed 104 tests; Ruff and ty were clean.

## Notes


Initial registry loading correctly refused templates without source citations. Exact manual citation probes were added before the final passing gates. No S44 linkage or S177 persistence work entered this step.
