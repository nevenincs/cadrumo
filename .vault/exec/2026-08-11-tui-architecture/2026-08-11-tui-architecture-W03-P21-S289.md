---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ac5d3a9ca992f0eb77113ed8bb027cd9ff541dc787f296045193717dad78469e'
step_id: 'S289'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Stop the modelo 184 socio record truncating a multi-member attribution to a single member: its export record carries twenty-seven manual scalar casilla fields, no binding fields and no repeat marker, while the per-row member bindings already exist in the registry and a real per-row resolver already computes their values, so every member beyond the first is computed correctly and never reaches the fichero; repoint the record's fields onto the existing per-row binding ids, declare the record repeating, and prove a real multi-member attribution emits one socio occurrence per member with the right values

## Scope

- `the modelo 184 socio export record declaration`
- `src/cadrumo/domain/calculations/registry/schema_exports.py if the repeat contract needs it`
- `and a real multi-member M184 export parity test`

## Changes

- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2025-y-siguientes/export/0004-record-m184-socio.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2023-2024/export/0004-record-m184-socio.toml`
- `A` `src/cadrumo/application/filing/tests/test_m184_socio_repeat_wiring.py`
- `verify:` `pytest src/cadrumo/application/filing/tests/test_m184_socio_repeat_wiring.py` -> `pass`
- `verify:` `ruff check/format + ty check on the new test file` -> `pass`
- `verify:` `bundled_authority() full registry build` -> `pass`

## Notes

Repointed four of the socio record's fields (member_tax_id, member_legal_name,
share_percentage, base_imponible_assigned) onto the existing
`modelo-184-member-row-*` bindings and declared `repeat = "binding_rows"`, in
both the `2025-y-siguientes` and `2023-2024` revisions. The remaining ~23
scalar casilla fields on the record (representante-fiscal-nif, provincia,
clave, importe, the inmueble block, etc.) are unchanged and still render one
shared value across every repeated member line; extending them to real
per-row bindings needs roughly twenty new `attribution_entity_socios.N.*`
bindings and was out of this Step's scope per the team lead's split (reported
before starting, split into S289/S294/S295). Also corrected the base-assigned
field's data_type from `text` to `money` (matching the casilla's own declared
type and the binding's own `money` selector) — this was a pre-existing,
never-exercised mismatch that only surfaced once a real value flowed through
render for the first time.
