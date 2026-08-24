---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:910b31e103e402a14cf4aa9623b4d54baddf3d9d9d87f0885af19d39e7037480'
step_id: 'S31'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Verify casilla identity, semantic linkage, and continuity chains across every supported revision boundary

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Used semantic discovery to locate the existing cross-revision authority and extended `src/cadrumo/domain/calculations/registry/_validate_cross_revision.py` rather than introduce a parallel scanner.
- Derived continuity candidates from the shipped registry, then adjudicated only officially evidenced identity and constraint changes across supported revision boundaries.
- Restored the M303 2026 prorrata CNAE roles as era-specific roles and declared 25 non-duplicative `repurposed` evolution edges from each prior supported revision.
- Versioned the M390 2021 informational compensation roles and declared the two evidenced 2021-to-2022 `repurposed` evolution edges.
- Removed stale family-disposition declarations that contradicted the newly declared evolution families.

## Outcome

- Added canonical semantic-linkage and evolution-endpoint checks, including duplicate-boundary detection, to the existing registry authority.
- Added mutation coverage for missing semantic roles, role-derived chain mismatches, width and constraint drift, missing endpoints, and duplicate evolution edges.
- The committed corpus has no semantic-linkage failures; all new continuities are backed by official record-design evidence.

## Notes

- The M390 catalogue-key migration and its locale test were already captured by concurrent commit `d8a313e2c6`; this S31 scope deliberately does not redeclare or revert that work.
- M303 casilla 112 has no evidence-backed predecessor in the supported corpus and remains role-less rather than receiving an invented chain.
