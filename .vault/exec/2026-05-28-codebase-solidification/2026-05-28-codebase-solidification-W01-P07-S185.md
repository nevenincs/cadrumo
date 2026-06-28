---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S185'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P07.S185

Introduce `FilingStatus.FILED` and replace bare `"filed"` literals in `_app_live.py` and `_contract.py`.

- Created: `src/aeat/application/overview/_status.py`
- Modified: `src/aeat/application/overview/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_app_live.py`
- Modified: `src/aeat/application/operator_surface/_contract.py`

## Description

`overview/__init__.py:132` already held `FILED = "filed"` inside `OverviewPeriodState(StrEnum)` — a
calendar-view status enum, not a command-name registry.  The step required a distinct
`FilingStatus(StrEnum)` whose sole member is `FILED = "filed"` and whose purpose is to own the
`"filed"` CLI command token across the operator surface.

Created `src/aeat/application/overview/_status.py` with `FilingStatus(StrEnum)` defining `FILED = "filed"`.
Re-exported from `overview/__init__.__all__`.  Replaced:

- `name="filed"` and `app.add_typer(filed_app, name="filed")` in `_app_live.py` with
  `FilingStatus.FILED` (StrEnum members ARE `str` instances; no `.value` needed for Typer).
- `commands=("filed",)` in the `LIVE` `MountedCommandFamily` in `_contract.py` with
  `(FilingStatus.FILED,)`.

Commit: `e9ed05094`
