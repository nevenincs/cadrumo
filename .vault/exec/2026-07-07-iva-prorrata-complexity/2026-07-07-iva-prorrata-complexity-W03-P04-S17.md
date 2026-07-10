---
tags:
  - '#exec'
  - '#iva-prorrata-complexity'
date: '2026-07-08'
modified: '2026-07-08'
step_id: 'S17'
related:
  - "[[2026-07-07-iva-prorrata-complexity-plan]]"
---

# Add operator-declared sector identification (CNAE/IAE) on the contribuyente profile and the sector reference on the ledger transaction

## Scope

- `src/aeat/domain/contribuyente/`
- `src/aeat/domain/transactions/_models.py`

## Description

- Declare the closed `SectorDiferenciadoLetra` StrEnum (art. 9.1.c letras a'/b'/c'/d') in `core/_prorrata_register.py` and export it through the `aeat.core` facade, per the core-authority discipline (closed axes live in `core`, hydrated at boundaries).
- Add the operator-declared `SectorDefinition` model to `domain/prorrata_register/__init__.py` — a differentiated sector carrying its `sector_id`, its `letra`, and its non-empty `member_activity_codes` (CNAE/IAE) — and carry a `sector_definitions` tuple on `ProrrataRegister` with a duplicate-`sector_id` validator plus the `is_sectorized` / `sector_ids` / `sector_definition_for` read helpers. Fail-closed: an empty partition is a whole-entity register (today's behaviour).
- Add the operator-declared `prorrata_sector_id: str | None` (min_length 1, max_length 64) sector reference to the ledger `Transaction` in `domain/transactions/_models.py`: `None` is common-use in a sectorized bucket (art. 104.Dos common percentage) and the whole-entity default in a non-sectorized bucket.
- Cover the new persisted fields with real-behaviour tests: a transaction `prorrata_sector_id` JSON roundtrip plus an anti-tautology blank-value-rejected-on-load proof; `SectorDefinition` construction/validation and register partition-query unit tests; and an extension of the encrypted-SQL `ProrrataRegister` roundtrip fixture to populate `sector_definitions` non-default with a reload assertion.

## Outcome

The differentiated-sector partition is now operator-declared over the register (the ADR-D1 surface) and each ledger row can reference its sector; both new persisted fields survive strict save/load cycles and refuse corrupted (blank) values on load. Focused suites green under `-n0`: 72 passed across the register-domain, transaction-model, and encrypted register-roundtrip tests; 5 IVA-ledger apportionment regressions still pass (the optional transaction field does not perturb aggregation). ruff, ruff format, and ty clean on every touched production file; registry collect-only clean.

## Notes

- Profile-level activity codes DEFERRED (honest scope call). The ADR (D1) makes the taxpayer profile's underlying CNAE/IAE codes an OPTIONAL "MAY carry", and chose the register sector-definition surface as the load-bearing operator-declared partition. That partition — including the CNAE/IAE `member_activity_codes` per sector — is delivered here on `SectorDefinition`. A separate `economic_activity_codes` field on the large, cross-campaign `TaxpayerProfile` (which lives in `domain/deadlines/`, not `domain/contribuyente/`) would be inert without wizard/projection/persistence threading, so it is deferred rather than landed as an unwired field on a hot shared model. The operator-declared CNAE/IAE sector identification the step calls for is satisfied by the register surface.
- The `SectorDiferenciadoLetra` StrEnum hydrates from its stored token only through the JSON persistence path (`model_validate_json`); the strict-frozen config rejects a loose python dict, which is the intended boundary behaviour.
- Pre-existing owner-distinct failure: `test_period_combined_string_gate.py::test_repo_has_no_unallowlisted_combined_period_strings` flags year-qualified quarterly tokens (`303-2026-1T`) in PEER test files (`test_review_package*`, `test_prorrata_regularizacion`, `test_data_prep`, `test_parser_boundary_m131`) I did not author or touch; the gate does not reference this step's enum and my transaction-test additions carry no such tokens. Recorded as peer test-debt, not this step's regression.
