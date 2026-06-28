---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S149'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P05.S149`

Co-located two intentionally-distinct date parser variants under `src/aeat/core/parsing/_dates.py`. Migrated callers to delegate to the canonical functions while preserving their domain-specific error types.

- Created: `src/aeat/core/parsing/_dates.py`
- Modified: `src/aeat/core/parsing/__init__.py`
- Modified: `src/aeat/domain/deadlines/_profiles.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_censo.py`

## Description

Two date-parsing variants existed as local `_parse_date` functions in unrelated modules, each handling a different wire format:

- `_parse_iso8601_date` (YYYY-MM-DD): extracted from `_profiles.py`. Raises `ValueError`; the local wrapper converts to `ProfileError`.
- `_parse_ddmmyyyy_date` (DD-MM-YYYY / DD/MM/YYYY): extracted from `_censo.py`. Raises `ValueError`; the local wrapper converts to `CensoParseError`.

The `_dates.py` module sits at the `core` layer with no domain dependencies. Both functions use `get_logger`. The `_DATE_RE` constant was removed from `_censo.py` since the regex logic is now internal to `_dates.py`. The `__init__.py` exports both new names alongside `_parse_bool`.

## Tests

Covered by S150 (`test_dates.py`). All 350+ targeted tests pass. Pre-existing failures in `test_engine.py`, `test_extemporaneidad.py`, and `test_declarations.py` are unrelated to this change.
