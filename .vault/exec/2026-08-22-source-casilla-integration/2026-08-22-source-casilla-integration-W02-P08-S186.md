---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8863272671c717ba31b48aa899c4085bc3009b18caff93fd0fe4a171db21d4e7'
step_id: 'S186'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# add typed row-indexed casilla values and direct-materialization provenance to the canonical source-resolution carrier

## Scope

- `src/cadrumo/domain/calculations`
- `src/cadrumo/application/aggregation/_source_mesh.py`

## Description

- Define the reusable row-casilla coordinate and frozen direct-materialization provenance in the lower calculation domain.
- Extend the canonical source-resolution carrier with deterministic row-casilla value and secret provenance maps.
- Enforce exact value/provenance bijection, source binding and identity equality, row-index alignment, typed revision identity, and direct-rule identity.
- Refuse duplicate serialized coordinates and every exclusive or precedence merge collision, including identical claims.
- Prove scalar isolation, redaction, deterministic serialization, compatibility defaults, validation failures, and collision behavior.

## Outcome

`CalculationSourceResolution` now carries typed `(CasillaId, row_index)` Decimal results with provenance that names the exact binding row, canonical row-source identity, binding-owned direct-materialization rule, and registry revision. The reusable types live below the application layer so encrypted calculation revisions can consume the same authority in S187 without an inverted dependency or duplicated schema.

The carrier is born provenance-complete: value and provenance coordinate sets must be equal, the named binding value and identity must exist and agree, and no caller precedence tier can replace or strip a row-casilla claim. Raw source-row identity is excluded from ordinary representations and dumps. Independent Sol review returned PASS with no findings.

## Notes

The production and focused-test changes landed in shared commit `13ac7a670b` while this lifecycle record was being prepared. The plan scope was widened through the CLI before implementation to record the lower-domain type authority. Targeted Ruff and 13 focused tests passed; the complete source-mesh module passed 59 tests.
