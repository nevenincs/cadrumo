---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:50ec6cd68872dd3ec6a4726255e277e0ef5c18af5f009c732a28cfcd1eeed781'
step_id: 'S07'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Write the strict roundtrip test against a real SecureObjectRepository, real key provider and real SQLite engine, populate every defaultable field non-default, assert strict pydantic equality, then the anti-tautology proof deleting a persisted field on disk and asserting reload refusal

## Scope

- `src/cadrumo/application/live/tests/test_deudas_service.py`

## Description

Wrote the strict roundtrip against real adapters plus two anti-tautology
proofs.

## Outcome

Modified files:

- `src/cadrumo/application/live/tests/test_deudas_service.py` (new)

The roundtrip runs through `isolated_runtime_profile`: real key provider, real
`SecureObjectRepository`, real SQLite engine, no test double anywhere. The
fixture populates every defaultable field with a non-default value --
`authenticated_identity` set, `periodo` set on three of four rows and
explicitly `None` on the fourth, a zero importe, and four distinct
`ObjetoTributario` categories across the rows. `mode` is the stated exception:
a single-value `Literal` has no non-default value to carry, which is the
structural marker it exists to be.

Assertions are strict pydantic equality (`loaded == persisted`), plus per-field
witnesses for the values a silent re-default would change, including that
`Decimal` survives as `Decimal` rather than float or str.

## Verification

8 tests, green:
`uv run --no-sync pytest src/cadrumo/application/live/tests/test_deudas_service.py`.
Commit `685abbf6b4`, `254 0 .../tests/test_deudas_service.py`.

Anti-tautology proof one: persist, decrypt the on-disk envelope, delete
`direccion` from the first nested deuda row, re-encrypt, assert the load raises
`ValidationError`. It asserts the field is present in the serialised payload
first, so the proof cannot pass vacuously against a fixture that never wrote
it. `direccion` was chosen over an easier field because it carries the
owed-versus-refundable axis: a silent re-default would make a debt read back as
a refund.

Anti-tautology proof two: rewrite the persisted `importe_pendiente` to a
negative value and assert the load refuses, proving the magnitude constraint
binds on the way IN and not only at construction.

## Notes

Known debt, reported to the coordinator rather than worked around: this
feature's application module introduces five locale keys that are NOT enrolled
in the four catalogues -- the four `application.live.deudas.errors.*` values
carried on `translated_message=` kwargs, plus the
`errors.refused.refused_live_deudas_snapshot_not_found` key from the error-code
entry. The locale AST scanner collects those kwargs as required keys, so
`test_codebase_to_locale_parity` counts them.

They could not be enrolled here. The `set` verb refuses a key that does not yet
exist, and the only verb that creates one, `scaffold`, is tree-wide: a run
would inject self-referencing placeholder leaves for the 83-to-118 keys a
concurrent M390 casilla-schema campaign has not yet enrolled, across all four
catalogues, and that placeholder value is itself refused by a shipped honesty
gate. Measured during this run: 118 keys missing from `es.yml` and 88 from each
of `en`, `ca` and `hu`, of which exactly 5 are this feature's in every
catalogue. The catalogues were also being actively written during the run --
`en.yml` was momentarily unparseable YAML -- so they are contended as well as
in debt.
