---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S322
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W09.P41.S322+S326+S327+S334 — W09 hygiene batch

## Steps covered

- `W09.P41.S322` — FU-W05-F: remove dead code + lint in `test_fx_conversion.py`
- `W09.P41.S326` — FU-S306-A: tighten `all_calendars` annotation in `_overview.py`
- `W09.P41.S327` — FU-S318-A: remove redundant `casillas_by_id` lookup in `_actions.py`
- `W09.P41.S334` — FU-S278-B: tighten `classified_by` type in ledger payload models

## Commit

`d4880c35f` — W09 hygiene batch: S322+S326+S327+S334

## Changes

**S322** (`src/aeat/application/aggregation/test_fx_conversion.py`):

Removed the dead shadowed `CurrencyNormalizationService` construction that was
left from a prior review refactor (the variable was immediately overwritten by the
inline `_NoRateProvider` class below it). Also removed the now-unused
`ExchangeRateProvider` import (F401). Fixed four pre-existing lint violations in
the touched file: RUF002/RUF003 (Unicode multiplication sign `×` in docstring and
comment replaced with `*`), SIM300 (Yoda condition in oracle assert swapped to
`Decimal("92.01") == _EXPECTED_EUR`), and RUF015 (`list(...)[0]` replaced with
`next(iter(...))`). All 5 FX-conversion tests pass.

**S326** (`src/aeat/entrypoints/cli/_overview.py`):

`all_calendars: list[dict]` narrowed to `list[dict[str, object]]`. The bare
`list[dict]` annotation was flagged in review #131 as an UNTYPED_BOUNDARY signal;
the values are JSON-deserialized calendar objects so `dict[str, object]` is the
correct boundary type.

**S327** (`src/aeat/application/modelo/_actions.py`):

In `_collect_revision_verification_findings`, the `casillas_by_id` dict was built
at function entry solely to feed `casilla_def=casillas_by_id.get(casilla_id)` in
the missing-required-casilla path. The dict was keyed by `str(casilla.id)` and the
lookup key was `str(casilla.id)` — guaranteed to hit because the iteration is over
`snapshot.revision.casillas` directly. Passing `casilla_def=casilla` (the loop
variable) is semantically identical and removes the O(n) allocation. The one
remaining caller of `casillas_by_id` did not exist; the dict was dead after removal.

**S334** (`src/aeat/application/ledger/_models.py`):

`classified_by: str | None = None` tightened to `classified_by: str =
Field(min_length=1)` in both `LedgerTransactionPayload` and
`LedgerTransactionReviewPayload`. The source field `Transaction.classified_by` is
`str = Field(min_length=1)` (non-nullable), so the `None` default in the payload
models was a type imprecision that hid the constraint from callers. All 170 ledger
tests pass.

## Pre-existing failure noted

`test_amend_refuses_without_external_evidence` in `test_amend_flow.py` fails with
`WorkflowAbortSignalError: UNHANDLED_EXCEPTION` in HEAD before and after this
batch. Pre-existing; not introduced by this commit.
