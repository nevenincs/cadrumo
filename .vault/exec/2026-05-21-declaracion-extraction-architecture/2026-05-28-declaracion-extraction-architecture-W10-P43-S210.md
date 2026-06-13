---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S210'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W10.P43.S210`

Extended `BorradorParseError` with the structured attributes (`missing`, `malformed`, `ambiguous`, `coverage`) that match the established discipline on `DeclaracionParseError`, `JustificanteParseError`, and `BankStatementParseError`. Updated the coverage-failure raise site in the extractor to populate `missing` and `coverage`. Added a `TestBorradorParseErrorAttributes` class with four typed-attribute tests.

- Modified: `src/aeat/adapters/inbound/borrador/_errors.py`
- Modified: `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`
- Modified: `src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`

## Description

`BorradorParseError.__init__` now accepts `missing`, `malformed`, `ambiguous` (all `tuple[str, ...]`, default empty), and `coverage` (`Decimal | None`, default `None`) as keyword-only parameters, mirroring the exact signature used by `DeclaracionParseError`. The docstring documents each attribute.

The coverage-failure path in `Modelo100ObservedV2025Extractor.extract` was the only existing raise site that carries enough context to populate structured attributes. The raise now passes `missing=missing_ids` (a sorted tuple of unmatched casilla IDs) and `coverage=coverage`. All other raise sites (`_require_match`, `DECLARACION`-without-CSV, `parse_borrador` mode guard) produce plain message-only errors; their attribute defaults of empty tuples and `None` are consistent with the class contract.

## Tests

Four tests in the new `TestBorradorParseErrorAttributes` class:

- `test_coverage_failure_populates_missing_and_coverage` — asserts `missing == ("0700",)` and `coverage == Decimal("1") / Decimal("2")` on the coverage-failure path.
- `test_coverage_failure_missing_sorted_tuple` — asserts two absent IDs arrive sorted when three are required and only one is found.
- `test_default_raise_has_empty_structured_attributes` — constructs a bare `BorradorParseError` and asserts all structured attributes are at their defaults.
- `test_explicit_population_of_all_attributes` — round-trip population of all four keyword arguments.

Result: `15 passed` (11 pre-existing + 4 new) in 1.85 s.
