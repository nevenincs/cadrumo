---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-07-04'
modified: '2026-07-04'
body_hash: 'sha256:c2f8eb826bd3d7eb8c855cbf2ee08263c0cf2bb248b0a5b3a9459f562a3f33c9'
step_id: 'S03'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

# Migrate the dual-module consumer to a single import site and run the identity validation test suite green

## Scope

- `src/aeat/domain/calculations/registry/_schema_scalars.py`

## Description

- Confirm the registry schema-scalar consumer `_schema_scalars.py` resolves the tax-id validator through the single public facade `aeat.core.identity` (importing `IdentityError` and `validate_spanish_tax_id`), not by dotting into `_documents` or `_tax_id` privately.
- Align the `_validate_nif_string` docstring to name the `aeat.core.identity` facade rather than the private `_tax_id` module path.
- Run the identity validation and registry NIF/scalar test suites green after the S01/S02 kernel consolidation.

## Outcome

- The consumer already imported from the single `aeat.core.identity` facade, so no import-site split existed to collapse; the single-import-site posture is confirmed and the docstring now points at the facade rather than an internal module.
- The consolidation underneath the facade (S01 check-letter, S02 CIF kernel) is transparent to this consumer: `validate_spanish_tax_id` keeps its signature and behavior.
- Gates green: identity suite 16 passed; registry schema-scalar / NIF data-type suite 91 passed; `ruff` and `ty` clean.

## Notes

- The plan step framed this consumer as a dual-module consumer; at HEAD it already used the facade single-import site (per `service-imports-via-top-level-reexports`), so the migration reduces to confirmation plus the docstring correctness fix. No functional change to the import graph was required.
