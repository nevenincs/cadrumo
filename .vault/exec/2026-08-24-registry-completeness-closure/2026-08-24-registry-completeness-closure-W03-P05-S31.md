---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:8501882d5c5d579463834715228bc6a7fdec7b0cf6948647b84c30fd321c1d57'
step_id: 'S31'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Verify casilla identity, semantic linkage, and continuity chains across every supported revision boundary

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py`
- `src/cadrumo/domain/calculations/registry/_validate_registry_scope.py`
- `src/cadrumo/domain/calculations/registry/tests/`
- `src/cadrumo/_data/registry/aeat/modelos/303/`
- `src/cadrumo/_data/registry/aeat/modelos/390/`

## Description

- Used semantic discovery to locate the existing cross-revision authority and extended `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py` rather than introduce a parallel scanner.
- Enrolled the semantic-linkage check in `validate_registry_scope`; it is now a registry-build invariant rather than a test-only audit.
- Derived continuity candidates from the shipped registry, then adjudicated only officially evidenced identity and constraint changes across supported revision boundaries.
- Restored the M303 2026 prorrata CNAE roles as era-specific roles and declared 25 non-duplicative `repurposed` evolution edges from each prior supported revision.
- Retained the M390 2021 informational compensation roles because they are not substitution-compatible with the 2022 bound, non-negative filing fields, but removed the false 2021-to-2022 `repurposed` declarations: AEAT record designs retain the legal concepts at 97 and 662.
- Removed stale family-disposition declarations that contradicted the newly declared evolution families.
- Added the truthful Modelo 390 2022 no-evolution family disposition: the remaining same-concept section drift stays advisory until an ADR extends the evolution vocabulary.

## Outcome

- Added canonical semantic-linkage and evolution-endpoint checks, including duplicate-boundary detection, to the existing registry authority.
- Added mutation coverage for missing semantic roles, role-derived chain mismatches, width and constraint drift, missing endpoints, and duplicate evolution edges.
- The committed corpus has no semantic-linkage failures; the M303 width barrier is backed by official record-design evidence and Modelo 390 has no invented continuity barrier.

## Notes

- The M390 catalogue-key migration and its locale test were already captured by concurrent commit `d8a313e2c6`; this S31 scope deliberately does not redeclare or revert that work.
- M303 casilla 112 has no evidence-backed predecessor in the supported corpus and remains role-less rather than receiving an invented chain.
- Revalidated on 2026-08-25 after the independently authored Modelo 038, 194, 721, and 763 revision splits exposed 16 repeated-id groups. The ratchet now records those groups as explicitly unreviewed backlog (`038: 2`, `194: 5`, `721: 7`, `763: 2`) rather than treating matching ids as evidence of legal identity or inventing `continuidad_id` stamps.
- The full sequential continuity-ratchet module passed (`10 passed`); no registry data, continuity stamp, or parallel validation authority was added.
