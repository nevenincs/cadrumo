---
step_id: S349-S357
feature: codebase-solidification
phase: P17
wave: W03
date: 2026-05-30
modified: '2026-05-30'
agent: coder-epsilon7
commit: 4c2f9c77e
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W03.P17 — canonical parsing enrollment S349-S357

## Collision check

`git diff` on all nine target files returned no output — no non-authored WIP on
any of the nine files.

## Steps executed

- **S349** `_notifications.py`: deleted local `_DATE_RE` regex constant; imported
  `_parse_ddmmyyyy_date` from `core.parsing._dates`; `_parse_date` now delegates
  to it inside `try/except ValueError → None`.
- **S350** `_row_set_assembly.py`: `_coerce_iso_date` string branch replaced
  `date.fromisoformat(value)` with `_parse_iso8601_date(value) or default`.
- **S351** `_marriage_facts.py`: two call sites migrated — `parse_marriage_date_from_facts`
  return and `parse_marriage_date_flag` inner try block both use `_parse_iso8601_date`.
- **S352** `_descendant_facts.py`: four call sites migrated — `birth_date` and
  `adoption_date` in the fact-reload loop, `birth_date` and `adoption_date` in
  `parse_descendiente_flag`.
- **S353** `family.py`: three `_parse_date` field-validator classmethods (`DescendantInfo`,
  `RentaDescendantProfile`, `RentaAscendantProfile`) all replaced with `_parse_iso8601_date`.
- **S354** `_export_parse.py`: Wave 2 S231 option-b design audited and confirmed correct.
  `_REGISTRY_TRUTHY`/`_REGISTRY_FALSY` constants cover domain-specific tokens ("X", "S", "SI");
  `_core_parse_bool` is delegated to for out-of-set tokens; unrecognised tokens raise
  `RegistryValidationError`. No code change required.
- **S355** `_setup_answers.py`: `_parse_unidad_familiar_descendientes_exclusivos` inline
  `value.lower() == "true"/"false"` replaced with `_parse_bool` (checked via
  `isinstance(_bool_candidate, bool)` to catch `False`). Three date validators
  (`_validate_taxpayer_marriage_date`, `_validate_activity_start_date`,
  `_validate_irpf_special_regime_start_date`) migrated to `_parse_iso8601_date`.
  Local `from datetime import date` deferred imports removed.
- **S356** `_values.py`: JSON boolean promotion in `_coerce_profile_fact_value`
  migrated to `_parse_bool`. Pattern narrowed to `value in ("true", "false")` guard
  before calling `_parse_bool` to preserve Decimal coercion for `"0"` and `"1"`.
- **S357** `test_parsing_enrollment_inventory.py`: new real-behavior inventory test
  using `ast.walk` for `date.fromisoformat` detection and text-scan for
  `value.lower() == "true"/"false"` patterns. Exclusions: `test_*.py` files and
  all `core/` modules (the `core/config.py` validator uses `date.fromisoformat` directly
  to avoid a circular import through `get_logger → config → parsing._dates`). Both
  tests pass with zero violations.

## Additional sites migrated (discovered by S357 inventory test)

Five additional production files had `date.fromisoformat` or inline bool patterns:
- `application/aggregation/_registry_provider.py` — transaction_date parse migrated
- `application/modelo/_profile_binding.py` — birth date parse and bool-to-Decimal
  coercion both migrated (`_parse_iso8601_date` + `_parse_bool`)
- `application/user_profile/_validation.py` — date validation call migrated
- `domain/invoices/_models.py` — `_coerce_date` helper migrated; added `None` guard
  since `_parse_iso8601_date` returns `None` for empty strings
- `domain/profile/__init__.py` — two field validators (`_parse_effective_from`,
  `_parse_since`) migrated

## S354 design choice — option (b) rationale

The `_parse_boolean` wrapper in `_export_parse.py` retains its own `_REGISTRY_TRUTHY`
and `_REGISTRY_FALSY` frozensets because the registry export format carries uppercase
affirmative tokens ("X", "S", "SI") that are not in `core._utils._TRUTHY`. Merging
them would pollute the core truthy set with domain-specific tokens. Option (b) is
correct: check registry-specific sets first, delegate to `_core_parse_bool` for
overlap coverage, and raise `RegistryValidationError` for anything unrecognised.

## Circular import note

`core/config.py` cannot import from `core/parsing/_dates.py` because `_dates.py`
calls `get_logger(__name__)` at module level, which triggers `configure_logging()`
which imports `config.py` — a circular chain. The `core/` layer exclusion in the
inventory test documents this intentional exception with an inline comment.

## Inventory test result

`test_no_bare_date_fromisoformat`: **PASSED** (0 violations)
`test_no_inline_bool_lower_comparison`: **PASSED** (0 violations)

## pytest outcome

All targeted module tests passed. Pre-existing test_declarations.py PDF fixture
failures (3) are unrelated to this P17 work and pre-date it.

## Commit

`4c2f9c77e` — solidification(W03.P17.S349-S357): canonical date/bool parsing enrollment — P17
