---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:63640ac25a1da949405daf4af5188fdc181dde6f2ba818b67688dc3e9f3b1b2d'
step_id: 'S26'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# co-emit prorrata settlement register write-back

## Scope

- `src/aeat/application/modelo/_revision_persistence.py`
- `src/aeat/adapters/persistence/profile/prorrata_register.py`
- `src/aeat/application/modelo/tests/test_prorrata_settlement_writeback.py`

## Description

- Add `ProrrataRegisterRepository.to_secure_object_write` so the register can join the filing secure-object transaction without changing its existing direct JSON payload format.
- Co-emit the M303 settlement prorrata register write from `persist_filed_revision` through the existing `save_with_secure_object_writes` path.
- Persist `iva.prorrata-porcentaje`, `iva.prorrata-volumen-con-derecho`, and the derived sin-derecho volume only for M303 `4T` and `0A` filings when all three settlement inputs are present.
- Preserve existing whole-entity register facts when adding settlement fields, retain sector entries, and create a minimal whole-entity entry when no current-year row exists.
- Add real encrypted-repository tests for create, preserve, and non-settlement silence paths.

## Outcome

- S26 is implemented without a new binding source kind, resolver convention, validator convention, or registry selector shape.
- Settlement filing now writes the definitive prorrata percentage and annual volume inputs back to the register in the same secure-object save as the filing catalogue and filed calculation revision.
- Existing register save/load and upsert behavior remains direct-payload compatible.

## Notes

- Verification: `uv run --no-sync ruff check src\aeat\adapters\persistence\profile\prorrata_register.py src\aeat\application\modelo\_revision_persistence.py src\aeat\application\modelo\tests\test_prorrata_settlement_writeback.py`.
- Verification: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_prorrata_settlement_writeback.py -n 0` passed with 3 tests.
- Verification: `uv run --no-sync pytest -q src\aeat\adapters\persistence\profile\tests\test_prorrata_register_roundtrip.py -n 0` passed with 4 tests.
- Verification: `uv run --no-sync pytest -q src\aeat\application\modelo\tests\test_participation_co_emission.py -n 0` passed with 1 test.
