---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:dbcfda361402246b98796923ea64573cae66fa8fa05510e6401f573164a48737'
step_id: 'S02'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add the closed Direccion StrEnum (owed, refundable) to core as its own typed axis rather than a sign, mirroring the ledger contract amount-is-magnitude convention, verified by a unit test

## Scope

- `src/cadrumo/core`

## Description

Declared the owed-versus-refundable direction axis in `core` as a closed
StrEnum, so a deuda's `importe` can stay a non-negative magnitude and flow
lives on a field.

## Outcome

Modified files:

- `src/cadrumo/core/_deuda_direccion.py` (new)
- `src/cadrumo/core/__init__.py` (facade import plus `__all__`)
- `src/cadrumo/core/tests/test_deuda_direccion.py` (new)
- `docs/api/cadrumo.core._deuda_direccion.rst`, `docs/api/cadrumo.core.rst`

Named `DeudaDireccion` rather than a bare `Direccion`. The plan row said
"Direccion"; every sibling direction axis in this tree is qualified
(`RegularizacionDireccion`, `IvaFlowDirection`, `RegularizacionProrrataDireccion`,
`AmendmentLiabilityDirection`), and an unqualified `Direccion` in `core` would
be a semantically unowned name adjacent to four others. Members are `DEUDOR`
and `ACREEDOR`.

## Verification

`src/cadrumo/core/tests/test_deuda_direccion.py`, 4 tests, green, including an
assertion that no member name or value carries sign vocabulary -- a member
valued after a sign would invite exactly the reconstruction-from-the-number
the axis exists to prevent. Commit `29bfa56d3f`,
`2 0 src/cadrumo/core/__init__.py`,
`49 0 src/cadrumo/core/_deuda_direccion.py`,
`54 0 src/cadrumo/core/tests/test_deuda_direccion.py`.

## Notes

Checked `AmendmentLiabilityDirection` for substitutability before adding a new
axis, since it lives in `core` and reads as the closest match. It is not
substitutable: it classifies whether CORRECTING a declaration raises or lowers
the declared liability and selects between the complementaria and
rectificacion procedures. A regression asserts neither enum subclasses the
other and their token sets stay disjoint.
