---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S150'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P05.S150`

Added real-behaviour parametrised tests asserting cross-format rejection for the two date parser variants.

- Created: `src/aeat/core/parsing/test_dates.py`

## Description

`test_dates.py` covers both parsers with three test groups each: valid inputs, absent/empty returns `None`, and foreign-format rejection via `pytest.raises(ValueError)`. The cross-rejection tests are the core contract:

- `_parse_iso8601_date` rejects `"31/12/2024"` (dd/mm/yyyy slash), `"31-12-2024"` (dd/mm/yyyy dash), and other non-ISO-8601 strings.
- `_parse_ddmmyyyy_date` rejects `"2024-12-31"` (ISO-8601), `"2024/12/31"`, and other non-day-first strings.

Invalid calendar dates (e.g. `"31-02-2024"`) are also covered for the ddmmyyyy variant.

No mocks, no skips, no xfail markers. All assertions derived from the wire-format specifications documented in `_dates.py`.

## Tests

25 parametrised test cases all pass. Commit `bea715105`.
