---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2cb863cbf529c8f89005cad185ef43c77821371b23f433c290180f816f65d6a9'
step_id: 'S60'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Close the S19-exposed producer and projection-address gaps by adding the distinct taxpayer tax-id producer and replacing activity-specific DP30302 module identities with exact annual-Orden module ordinals, with no alias or compatibility reader

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/domain/calculations/registry/`

## Description

- Add the distinct closed taxpayer tax-ID producer key.
- Resolve it only from immutable taxpayer identity in the filing producer snapshot.
- Prove taxpayer and presenter identifiers cannot collapse or fall back.
- Prove DP30302 module projection uses validated annual-Orden ordinals and retains strict legacy-shape refusal.

## Outcome

Completed with 57 targeted tests passing. The combined dependency lane passed 80 tests. Scoped Ruff, formatting, `ty`, BasedPyright, and diff checks passed. Formal review approved with zero unresolved critical, high, or medium findings.

## Notes

No production `module_identity`, alias, default, normalization, raw mapping, compatibility reader, or prohibited test double remains in the audited path.
