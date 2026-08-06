---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:fe9dc1dacc5084c2cd32f62c39a5afb142ada7117a4ee971b6bad9aaf1bd5873'
step_id: 'S11'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
## Description

- Re-run RAG against relation period alignment, source-period derivation, and the clean-state dependency inventory.
- Use the validated authority and authority-selected snapshots for every revision representative year and declared target period.
- Project `relation_source_requirements` into typed relation-period rows, preserving source filing year, source periods, source casilla, dependency treatment, aggregation, and legal/source references.
- Classify clean-state contracts as required, conditional, or advisory from the registry dependency classification; leave taxpayer-specific runtime verdicts explicitly unmeasured.
- Add real bundled-authority assertions for the finite row counts, M100 2025 advisory and conditional examples, and no unresolved rows.

## Outcome

S11 is complete. The measured denominator is 108 relation-period rows from 74 validated relations: 81 active, 27 not applicable, and 0 unresolved. Clean-state contract classes are 73 required, 13 conditional, and 22 advisory. The focused real-registry module passes 3 tests; Ruff, format, basedpyright, and the owned-path diff check are clean.

## Notes

This step measures the registry-side requirement contract only. It does not run a taxpayer clean-state verdict and does not substitute synthetic repositories, mocks, or fabricated evidence for behavioral proof.
