---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:79c87db9c7e233453b7588b641c13a567075101ad8cbc51ed15332ad62e4aee1'
step_id: 'S38'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# record the deferred sectores diferenciados per-sector registers, the art-104.Tres financial/inmobiliario special denominator, and the art-105.Cinco interrupted-activity three-year rule as noted follow-ups behind the from-birth sector schema slot

## Scope

- `.vault/exec/2026-07-06-cross-period-prorrata/`

## Description

- Re-read the live plan status and confirmed `W06.P09.S38` was the next open step after S37.
- Re-grounded the follow-up with semantic search, the cross-period prorrata ADR, the W06 plan row, the `ProrrataRegisterEntry.sector_id` slot, and the domain sectoral prorrata predicate.
- Confirmed the register aggregate already keys entries by `(ejercicio, sector_id)` and rejects duplicate keys, so sectores diferenciados can land without a persistence migration.
- Confirmed the domain substrate can compute the Art. 9.1.c sectoral-separation predicate from supplied sectors, but sector identification and per-sector register orchestration are not yet live application behavior.
- Recorded the remaining Art. 104.Tres financial/inmobiliario special-denominator rules and the Art. 105.Cinco interrupted-activity three-year rule as follow-ups; neither is implemented by the current general-prorrata ledger rollup.

## Outcome

- S38 is formally deferred.
- Follow-up 1: build per-sector register orchestration and persistence flows over the existing `sector_id` key.
- Follow-up 2: implement the Art. 104.Tres special denominator treatment for the financial and immovable-operation cases that require more than the current exclusion set.
- Follow-up 3: implement the Art. 105.Cinco interrupted-activity three-year rule before claiming full sectoral lifecycle coverage.
- No source kind, resolver convention, validator convention, or registry selector was added.

## Notes

- Verification passed: `uv run --no-sync pytest -q src\aeat\domain\prorrata_register\tests\test_prorrata_register.py src\aeat\domain\iva\tests\test_prorrata.py -n 0` (51 passed).
