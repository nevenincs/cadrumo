---
step_id: "S147"
plan: "[[2026-05-20-schema-hardening-plan]]"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#schema-hardening"
related:
  - "[[2026-05-20-schema-hardening-plan]]"
  - "[[2026-05-18-schema-hardening-adr]]"
---

# schema-hardening W07.P23.S147 - M036 period case alignment

## Outcome

M037 grounding investigation revealed that the codebase already encodes M037
correctly as a **historically-suppressed** censo model — the domain contract in
`_censo_modelos.py` explicitly enforces that `"037"` must NOT have an active
registry TOML file, and the suppression is grounded by the
`boe-modelo-037-historical-suppression` source ref in `census.toml`, backed by
`orden-hac-1526-2024:df-unica` (BOE-A-2025-410).

The investigation uncovered a related M036 bug: `period_selector.periods` and
`filing_schedules[...].periods` in `036.toml` were authored with uppercase
`["ALTA", "MODIFICACION", "BAJA"]` but `CENSUS_MODELO_EVENT_KINDS` in
`_censo_modelos.py` declares lowercase `("alta", "modificacion", "baja")`.
This caused `RegistrySnapshotError` on every censo-foundation snapshot call
(7 tests failing in `test_modelo_036_registry.py` and
`test_census_modelo_registry_data.py`).

## Changes

- `src/aeat/_data/registry/aeat/modelos/036.toml`: changed `period_selector.periods`
  from `["ALTA", "MODIFICACION", "BAJA"]` to `["alta", "modificacion", "baja"]`
  and `filing_schedule.periods` from `["ALTA", "MODIFICACION", "BAJA"]` to
  `["alta", "modificacion", "baja"]`. No other changes.

## M037 domain contract analysis

The domain model enforces the following invariant for M037 (from
`_censo_modelos.py` `_historical_037_ownership_from_registry`):

1. `authority.validate_modelo("037")` **must** raise `RegistrySnapshotError`
   with the text "is not present in the calculation registry"
2. `boe-modelo-037-historical-suppression` **must** be present in the
   source catalogue
3. Result role = `HISTORICAL_METADATA`, `active_work_unit_allowed = False`,
   `superseded_by = "036"`

Adding a `037.toml` registry file would **violate** invariant (1) and cause
`RegistryValidationError("historical census modelo 037 must not have an active
registry definition")`. The test `test_no_committed_modelo_037_toml_can_revive_active_support`
in `test_census_modelo_registry_data.py` (line 102-104) enforces this.

M037 has NO extraction profile, NO fixture, and NO round-trip test, by correct
domain design. Bottom line: M037 state is **HISTORICALLY-GROUNDED** — registry
absence is the correct encoded state, backed by `orden-hac-1526-2024:df-unica`.

## Verification

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_036_registry.py src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py` — **13/13 passed**.
