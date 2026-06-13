---
tags:
  - "#exec"
  - "#codebase-solidification"
date: "2026-05-31"
modified: '2026-05-31'
step_id: "W07.P32.S517"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-adr]]"
---

# codebase-solidification W07.P32.S517-S527 — A1 exception sweep + MRO finishers

## Outcome

Closed 11 steps in a single session commit `7011ff7e4`. All bare `ValueError` /
`TypeError` raises in the 10 named target files migrated to registered `AeatError`
subclasses. Two new `CoreError` subclasses introduced and registered.
Grep-post-condition gate: zero `raise (ValueError|TypeError|RuntimeError)(` in all
target files after the sweep.

### Per-step summary

- **S517** — `FinancialValidationError` `ValueError` mixin dropped from MRO in
  `financial/providers/_base.py`. Three caller sites (`_csv.py`, `_xlsx.py`,
  `_ofx.py`) updated to `except (ValueError, FinancialValidationError)` to preserve
  catch semantics. Fourth `except ValueError` in `_base.py:430` left (intentional
  datetime.strptime format guard).

- **S518** — Five `raise TypeError(...)` in `_encrypted_columns.py` (lines 125, 154,
  190, 257, 274 — SQLAlchemy processor type guards) migrated to
  `raise StorageValidationError(...)`. Import already present.

- **S519** — `DecimalFormatError(CoreError)` introduced in `aeat.core.errors`. Registry
  entry `ERROR_DECIMAL_FORMAT` added in `core/errors/registry/_core.py`. One
  `raise TypeError` in `decimal/_format.py:55` migrated.

- **S520** — `RedactionError(CoreError)` introduced in `aeat.core.errors`. Registry
  entry `ERROR_REDACTION` added. Two `raise TypeError` in `redaction/__init__.py` (lines
  274, 430) migrated using deferred local import inside each function body to avoid
  circular import (`_registry.py` → `redaction` → `errors` → `_registry`).

- **S521** — `_coerce_date` raises in `domain/invoices/_models.py` kept as `ValueError`
  per pydantic-validator-context rule: pydantic validators require `ValueError` or
  `AssertionError`; no migration performed.

- **S522** — One `raise ValueError` in `application/overview/_agenda.py:108` migrated
  to `raise OverviewAgendaError(...)` (class already existed and was registered).

- **S523** — One `raise ValueError("bucket_id must not be blank")` in
  `application/user_profile/_censo_sync.py:147` migrated to `raise CensoSyncError(...)`.

- **S524** — Three `raise ValueError(...)` in `domain/portals/_entries/_common.py`
  (lines 48, 93, 96 — `_resolve_host` and `build_entry` guards) migrated to
  `raise PortalValidationError(...)`.

- **S525** — Four `raise ValueError(...)` in `domain/profile/_descendant_facts.py`
  (parse_descendiente_flag) plus one in `_marriage_facts.py` and one in `_ccaa.py`
  all migrated to `raise ProfileAnswerTypeError(...)`. EN-DASH in `"0–12"` message
  also corrected to ASCII hyphen (RUF001).

- **S526** — Two `raise ValueError(...)` in `domain/calculations/registry/_m232_row_bindings.py`
  (lines 53, 65) migrated to `raise RegistryValidationError(...)`. Two pre-existing broken
  imports also corrected (wrong relative-dot-count reaching `aeat.domain.domain.modelos`
  instead of `aeat.domain.modelos`; `CasillaObservation` imported from `_schema` instead
  of `_bindings`).

- **S527** — 25 real-behavior tests at `src/aeat/test_w07_p32_exceptions.py`. Covers:
  MRO invariants for all new/migrated error classes, `ERROR_REGISTRY` registration check,
  raise-and-catch at every migrated call site, `ErrorEnvelope` roundtrip for
  `DecimalFormatError` and `RedactionError`. All 25 pass. No mocks, no skips, no
  tautological assertions.

## Locale keys added

- `errors.error.error_decimal_format` (en, es, ca, hu)
- `errors.error.error_redaction` (en, es, ca, hu)

## Files touched

- `src/aeat/adapters/inbound/financial/providers/_base.py` — S517 MRO fix
- `src/aeat/adapters/inbound/financial/providers/_csv.py` — S517 caller
- `src/aeat/adapters/inbound/financial/providers/_xlsx.py` — S517 caller
- `src/aeat/adapters/inbound/financial/providers/_ofx.py` — S517 caller
- `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py` — S518
- `src/aeat/core/errors/__init__.py` — S519, S520 (DecimalFormatError, RedactionError)
- `src/aeat/core/errors/registry/_core.py` — S519, S520 registry entries
- `src/aeat/core/decimal/_format.py` — S519
- `src/aeat/core/redaction/__init__.py` — S520
- `src/aeat/application/overview/_agenda.py` — S522
- `src/aeat/application/user_profile/_censo_sync.py` — S523
- `src/aeat/domain/portals/_entries/_common.py` — S524
- `src/aeat/domain/profile/_descendant_facts.py` — S525
- `src/aeat/domain/profile/_marriage_facts.py` — S525
- `src/aeat/domain/profile/_ccaa.py` — S525
- `src/aeat/domain/calculations/registry/_m232_row_bindings.py` — S526 + pre-existing import fixes
- `src/aeat/test_w07_p32_exceptions.py` — S527 (new)
- `src/aeat/locales/en.yml` — locale keys
- `src/aeat/locales/es.yml` — locale keys
- `src/aeat/locales/ca.yml` — locale keys
- `src/aeat/locales/hu.yml` — locale keys

## Commit

`7011ff7e4` — `exceptions(W07.P32.S517-S527): A1 exception sweep + MRO finishers`
