---
tags:
  - '#exec'
  - '#size-budget-refactor'
date: '2026-07-09'
modified: '2026-07-17'
body_hash: 'sha256:f6c9ad7a6bdaa61ce3052d2a439512e439b3aac7315acfae0e3d1a23e7116aa3'
step_id: 'S05'
related:
  - "[[2026-07-09-size-budget-refactor-plan]]"
---

# Extract the identified cohesive chunk into a new sibling module and re-wire build_overview_calendar to call it, preserving the public API and behavior exactly

## Scope

- `src/aeat/application/overview/_calendar.py`
- `src/aeat/application/overview/_calendar_evidence.py`

## Description

- Created `_calendar_evidence.py` with the extracted dedup pair and filing-evidence-reconciliation surface (748 body lines plus a module docstring and imports, 825 lines total), preserving every function body byte-for-byte.
- Removed the moved ranges from `_calendar.py` (lines 696-1417, 356-382, 113-134) and the 3 module constants that moved with them.
- Added an import block in `_calendar.py` pulling the 8 moved private symbols the staying code still calls back from `._calendar_evidence`, plus a self-aliased re-export of the public `calendar_filing_evidence_from_sources` symbol so the package `__init__.py` facade needed zero changes.
- Trimmed `_calendar.py`'s top-of-file imports to drop `UTC`, `datetime`, `MappingProxyType`, and the `FiledDeclaracionObservation` TYPE_CHECKING import, confirmed via grep that none were used outside the moved ranges.
- Further split `build_overview_calendar` itself (still 202 lines after the module split) by extracting its per-year schedule computation into `_schedules_for_calendar_range` and its per-obligation applicability-filtering loop into `_entries_and_suppressed_from_schedules`, both private helpers placed immediately before the callable.
- Ran `ruff check --fix` (one auto-fixed import-ordering violation, zero remaining).
- Confirmed `import aeat.application.overview` succeeds and both `calendar_filing_evidence_from_sources` and `build_overview_calendar` remain resolvable on the package facade.

## Outcome

`_calendar.py` shrank from 1677 to 945 lines (module-line override 1667); `build_overview_calendar` shrank from 202 to 145 lines (callable-line override 192). `_calendar_evidence.py` is a new 825-line sibling, well under the default 1250-line budget. Public API and package facade unchanged; `ruff check` clean on both files.

## Notes

The Step's originally-planned filename (`_calendar_sections.py`, chosen before reading the module) was revised to `_calendar_evidence.py` once the actual cohesive boundary (filing-evidence reconciliation, not per-section calendar building) was confirmed by reading the file in full during S04 -- the plan Step's scope text still names the original filename, but the delivered module and its content are what this record and the landed commit describe.
