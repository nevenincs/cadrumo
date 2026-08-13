---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:bd45c386b5b6eae2c6d2272812bac43a1e07e32bfde2f7937832054aa0b461d8'
step_id: 'S44'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `M720OperationKindCode` and `M720AssetClassCode` as `StrEnum`s in `core/` sourced from registry TOML if enumerated there, and retype `operation_kind_code` / `asset_class_code` onto them, explicitly NOT as `IdentifierNamespace` members

## Scope

- `src/cadrumo/core/_foreign_asset_obligation.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/domain/calculations/registry/_detail_record_bindings.py`
- `src/cadrumo/application/aggregation/_foreign_assets.py`
- `src/cadrumo/application/calculations/_row_set_assembly.py`
- `src/cadrumo/domain/calculations/registry/tests/test_detail_record_row_builders.py`
- `src/cadrumo/domain/calculations/registry/tests/test_detail_record_observations.py`

Neither `domain/modelos/` (the row's own file annotation) nor
`domain/transactions/` (`W05.P08.S43`'s file) contains either field; both
genuine fields live in `domain/calculations/registry/` and its consumers.

## Description

- **`M720OperationKindCode` is a misnomer the row's own text carries: no
  such field exists.** Grepped every `operation_kind_code` declaration in
  the tree before writing anything. Found exactly one bare-`str` site,
  `RefundOperationObservation.operation_kind_code` in
  `_detail_record_bindings.py` — and its own surrounding section header
  reads "Refund operation source bindings (**modelo 360**)", not 720.
  Modelo 720's own observation model
  (`Modelo720RowObservation`) has no `operation_kind_code` field anywhere;
  `Modelo232`'s own `operation_kind_code` (`_row_set_assembly.py:277`) is
  ALREADY typed `TipoOperacionVinculada`, done before this row started.
  The row's premise conflated three different modelos' same-named field
  into one.
- Checked whether Modelo 360's `operation_kind_code` is enumerated in
  registry TOML, per the row's own conditional ("sourced from registry
  TOML if enumerated there"): its one registry binding
  (`modelo-360-refund-row-operation-kind`) routes the row field but
  declares no value catalogue anywhere in the Modelo 360 authoring tree.
  Sampled every literal value assigned to it in the tree: only `"01"` and
  `"02"` appear, in synthetic test fixtures, with no bundled AEAT
  publication (Orden EHA/789/2010 Anexo) grounding a complete set. Per
  the row's own conditional and this campaign's grounding discipline
  (never fabricate a closed set from thin synthetic evidence), did NOT
  declare a Modelo 360 code enum — the premise for building it is not
  met.
- **`M720AssetClassCode` is real and well-evidenced.** Traced
  `Modelo720RowObservation.asset_class_code` (bare `str`,
  `_detail_record_bindings.py`) to its producer,
  `_asset_class_code()` in `application/aggregation/_foreign_assets.py`,
  which maps the ALREADY-existing `ForeignAssetClass` semantic enum
  through `MODELO_720_FOREIGN_ASSET_CLASS_CODES` to the raw AEAT
  position-102 clave. That mapping's own docstring states the bundled
  AEAT record design closes the set at exactly five one-character values
  (`C`/`V`/`I`/`S`/`B`) — the same evidence the mapping itself already
  carried, not invented for this row.
- Declared `M720AssetClassCode(StrEnum)` in `core/_foreign_asset_obligation.py`
  (the file that already owned the source-of-truth mapping), narrowed
  `MODELO_720_FOREIGN_ASSET_CLASS_CODES`'s value type from `str` to the
  new enum, and re-exported through `core/__init__.py`'s lazy
  `TYPE_CHECKING` block, `__all__`, and `__getattr__` dispatch (the
  package's established lazy-facade pattern — added to all three, not
  just one). Retyped `Modelo720RowObservation.asset_class_code` and
  `_asset_class_code()`'s return type onto it.
- **Found and fixed a real strict-mode interaction the retype
  surfaced.** `Modelo720RowObservation` (and every detail-record
  observation model) uses `STRICT_FROZEN_CONFIG` (`strict=True`). Under
  strict validation a `StrEnum` field requires an actual enum INSTANCE,
  not a bare string that merely matches a member's value — a real pydantic
  v2 behaviour, not a defect in this row's design. One production call
  site (`_row_set_assembly.py`, row-set reassembly for the pull-ingest
  path) constructed the observation with a bare string and started
  failing. Fixed it with the SAME `_hydrate_coded_field` helper the
  module already uses for Modelo 232's `operation_kind_code` — the
  established, tested pattern for exactly this widen-raw-token-to-enum
  step, not a new mechanism. Fixed five test-fixture construction sites
  across two test files
  (`test_detail_record_row_builders.py`,
  `test_detail_record_observations.py`) that constructed with a bare
  `"C"`/`"V"` string, three of which were silently passing anyway (their
  `pytest.raises(match=...)` substring check did not care about an
  incidental extra validation error) but were fixed for correctness
  rather than left carrying a silently-broken construction.

## Outcome

**COMPLETE, ADJUDICATED.** `M720AssetClassCode` declared and retyped end
to end (producer, model field, both production call sites, both affected
test files). `M720OperationKindCode` correctly NOT declared: the field
the row named does not belong to Modelo 720 at all, Modelo 232's
same-concept field is already typed, and Modelo 360's is not enumerated
in registry TOML with sufficient grounding to build a closed set safely —
exactly the row's own stated condition for skipping it.

`ruff check`, `ruff format --check` clean on every touched file;
`basedpyright` clean on the three gated files
(`_detail_record_bindings.py`, `_foreign_assets.py`,
`_row_set_assembly.py`); `core/_foreign_asset_obligation.py` and
`core/__init__.py` sit outside basedpyright's configured `include`. Real
tests green: 97 passed across `test_foreign_assets.py`,
`test_modelo_720_foreign_asset_producer_join.py`,
`test_row_set_assembly.py`, `test_detail_record_observations.py`,
`test_detail_record_row_builders.py` — the exact suites that caught the
strict-mode defect before it shipped.

## Notes

No incidents. The strict-mode `StrEnum` finding generalises: any future
row in this campaign that retypes a field on a `STRICT_FROZEN_CONFIG`
model onto a `StrEnum` must sweep every construction site (not just the
declaration) for a bare-string literal that strict validation will now
refuse, and reach for `_hydrate_coded_field` (or the equivalent
established pattern in the target module) rather than inventing a new
coercion each time.
