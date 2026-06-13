---
tags:
  - '#exec'
  - '#core-authority'
step_id: S82
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W09.P25.S82 - core-to-domain edges enumeration and fix

## Outcome

Enumerated all 36 core-to-domain import edges per MIGRATE-006, RELOC-025, Rule 1.

The import-reference audit shows the 36 count breaks down as:
- **25 production edges** — all in `core/resources/_repos/*.py` (apoderamientos, category_profiles, holiday_calendars, iva_catalogues, iva_rate_tables, legal_parameters, manuals, modelos, normatives, recargo_bands, user_profile)
- **11 test edges** — in core/test_*.py files (function-body lazy imports)

**Production edges decision:** All 25 production edges use `TYPE_CHECKING` blocks (zero runtime cost) or lazy `local_scope` imports inside `_load()` / `_settings()` methods. This is the ADR protect-list pattern: "conditional imports guarding optional packages" + "lazy `__getattr__` cycle-breakers." The `core/resources/_repos/` layer is a thin caching adapter over domain loaders that ships bundled resources (PDFs, JSONs, TOMLs). Moving the domain loader calls out of `core/resources/_repos/` would dissolve this layer into the domain — a larger structural change beyond S82 scope.

**Test edges fixed (1 module-level → lazy):**
- `core/resources/_repos/test_normatives.py:L18` — moved top-level `from aeat.domain.normatives.errors import NormativeParseError` inside the test function that uses it.

**Test edges not changed (10 already lazy):** All other test violations are lazy function-body imports in `test_manuals.py`, `test_singletons.py`, `test_external_constants.py`, `test_logging.py`, `test_profile.py` — all already at `local_scope` context. No module-level edge introduced.

**Output-language integration test:** Moved `core/i18n/test_output_language.py` (which had 2 module-level application/adapters imports) to `src/aeat/tests/test_output_language.py` — the correct location for full-stack integration tests. 5 tests continue to pass in the new location.

## Commit

`8f10fa9ea` — refactor(core): W09.P25.S82-S84 - eliminate core outbound module-level import edges

## Files touched

- `src/aeat/core/resources/_repos/test_normatives.py` — NormativeParseError import made lazy
- `src/aeat/core/i18n/test_output_language.py` — DELETED (moved)
- `src/aeat/tests/test_output_language.py` — CREATED (canonical integration-test location)

## Verification

Core suite: 588 pass, 8 fail (all 8 are pre-existing, unrelated to W09). 0 new failures.
