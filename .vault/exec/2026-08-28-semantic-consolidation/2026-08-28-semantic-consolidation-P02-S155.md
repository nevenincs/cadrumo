---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:d957852094aac3caa834d4a9fd9928d9635596884b1a5025ae658c9b7d000340'
step_id: 'S155'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Correct the fifteen fixture sites left carrying a CIF the merged leader policy refuses, after re-deriving the checksum I had dismissed them on

## Scope

- `src/cadrumo/application/overview/tests/`
- `src/cadrumo/domain/calculations/registry/tests/`

## Changes

- `M` `src/cadrumo/application/overview/tests/test_applicability.py`
- `M` `src/cadrumo/application/overview/tests/test_obligation_coverage.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_840_applicability.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_modelo_applicability.py`
- `verify:` `_cif_check_value("4567890")` -> 1, letter `A`
- `verify:` `validate_spanish_tax_id("A45678901")` -> accepted
- `verify:` grep for the old literal -> 0 remaining
- `verify:` `pytest the five files -n 0 -m ""` -> 84 pass, 3 unrelated

## Notes

A correction to S131, and to what was reported at the time.

The CIF leader merge made `ABEH` digit-control-only, which was the point. Its
blast radius was reported as one literal, `B1234567D`, on the strength of a
census that DID surface a second -- `A4567890A` -- and dismissed it with
arithmetic done in my head: I derived the check value as 0, letter `J`, and
concluded `A` was invalid under both the old and new readings.

The real value is 1, letter `A`. So `A4567890A` was a VALID CIF under the old
mixed reading and is invalid under the correct one, at fifteen fixture sites
across five files, which have been failing since that merge landed.

The census was right and the dismissal was wrong, which is the part worth
keeping. A grep that surfaces a candidate and a hand-derivation that clears it
are not equal evidence, and the checksum function was available to call the whole
time. Every one of the fifteen now carries `A45678901` -- the same entity, the
digit form its leader class requires -- and the function was asked rather than
re-derived.
