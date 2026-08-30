---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:bedf5899873cc3eccd2ed78607657859c45d55f48d2508f0eeabed91cf3f2a4e'
step_id: 'S61'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Adjudicate Modelo 165's 2013-2015 design hole, which is a CORPUS DEFECT in an authoritative source rather than a parser gap, and needs a ruling before it can be closed. DIAGNOSED 2026-08-28, NOT FIXED. The sheet 'Tipo 2 - Registro De Socios O Participes' in `02-165-orden-hap-2455-2013.pdf` declares 500 total positions but nothing describes 102-103: the record runs 97-101 PORCENTAJE DE PARTICIPACION (subdivided 97-99 ENTERO, 100-101 DECIMAL) and then jumps straight to '104-500 BLANCOS'. COMPARED ACROSS ALL THREE BUNDLED EDITIONS of the same orden, which are byte-identical everywhere else (95-96 DIA, 97-101, 97-99, 100-101, 108-120 NUMERO IDENTIFICATIVO): `01-165` (actualizado 2023) and `03-165` (actualizado por orden HFP-1822-2016) both publish '102-500 BLANCOS'. Only the original 2013 BOE orden says 104, and no edition describes any field at 102-103, so the two positions are filler in every reading and the original simply mis-declares where filler starts. THIS IS NOT COSMETIC BOOKKEEPING: `02-165` is `aeat-dr-165-2013-2015`, marked design_authority='authoritative' and cited by revision 2013-2015, so if that era ever acquires an export layout the hole becomes a real byte-coverage gap. It has layouts=0 today, which is why nothing has bitten yet. THE EXISTING CORRECTION MECHANISM DOES NOT FIT and must not be stretched to make it: the three declared kinds address a row read with a blank type cell, a header cell, and one naturaleza-less single-position row, whereas this is a filler row whose declared START is wrong. The schema comment states the narrow gate is deliberate, so widening it is an ADR-grade decision, not a loop-tick patch. Options are a fourth range-start correction kind grounded in the two sibling editions, or acquiring a corrected 2013-2015 diseno from AEAT

## Scope

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_165 and registry/record_design_schema.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_165_historical_layout_authority.py`
- `verify:` `uv run --no-sync pytest --noconftest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_narrow_mechanism_admissions.py src/cadrumo/domain/calculations/registry/tests/test_modelo_165_historical_layout_authority.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_narrow_mechanism_admissions.py src/cadrumo/domain/calculations/registry/tests/test_modelo_165_historical_layout_authority.py` -> `pass` (23 passed, 56.27s)

## Notes

The normal focused pytest invocation was initially blocked by the shared worktree's unrelated half-landed declaracion relocation: `cadrumo.adapters.inbound.declaracion._detect` could not import `extract_pages_text` from `_parsers`. The normal rerun now passes (23 passed, 56.27s); the earlier `--noconftest` result is retained as historical troubleshooting evidence rather than the sole verification.

