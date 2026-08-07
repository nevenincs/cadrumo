---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9dd8865ba311fea08f0104623c21be8db2c762bff02e166778f812d9f26f658a'
step_id: 'S03'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add the Deuda adapter schema model in a new _deudas.py module mirroring Expediente placement and STRICT_FROZEN_CONFIG, with clave_liquidacion, objeto_tributario, importe_pendiente as a non-negative Decimal, direccion, periodo, situacion as a bounded str following the Declaracion.estado precedent (never a StrEnum), and mode Literal read, verified by a model validation unit test

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`

## Description

Added the `Deuda` boundary record for AEAT's *Consultar deudas* listing row,
mirroring `Expediente`'s placement and `STRICT_FROZEN_CONFIG`.

## Outcome

Modified files:

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py` (new; carries the
  read-landing guard too)
- `src/cadrumo/adapters/outbound/aeat/sede/__init__.py` (facade)
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_deudas_schema.py` (new)
- `docs/api/cadrumo.adapters.outbound.aeat.sede._deudas.rst` and the sede and
  core stub indexes

Fields: `clave_liquidacion`, `objeto_tributario`, `importe_pendiente` as a
non-negative `Decimal`, `direccion`, `periodo` (optional -- AEAT attributes
some liabilities to no single period), `situacion` as a bounded `str`, and
`mode: Literal["read"]`.

`situacion` ships as a bounded `str`, not a StrEnum, per the amended plan and
the ADR's dedicated rationale. The cited precedent was verified rather than
taken on trust: `_declarations_schema.py:25` is
`estado: str = Field(min_length=1, max_length=16)`, a status label scraped from
the same declarations listing. The amendment also narrows the specimen-blocked
follow-up row to observing values and confirming the length bound, never
converting the field, which removes the provisionality that would otherwise
make an untyped closed axis permanent by default.

## Verification

`test_deudas_schema.py`, 16 tests, green. Commit `9009926158`,
`192 0 .../_deudas.py`, `10 0 .../sede/__init__.py`,
`115 0 .../tests/test_deudas_schema.py`. `ty check` clean; `ruff` clean.

## Notes

A `min_length=1` bound alone accepted the whitespace-only string `"   "`,
which is what an empty listing cell parses to -- so a parse defect would have
recorded a row whose identity and procedural state were both unknown as though
AEAT had reported them. Added a `field_validator` rejecting blank-after-strip
on `clave_liquidacion` and `situacion`, adopting the shape the ledger's
`RawTransaction` boundary already uses. The test asserted the property first
and the code lacked it; the code was corrected rather than the test relaxed.

This Step shares one commit with `S08`. Both plan rows name the same file, and
the guard is what makes the module's read-only claim structural, so splitting
them would have shipped an intermediate state with a record and no wall.
