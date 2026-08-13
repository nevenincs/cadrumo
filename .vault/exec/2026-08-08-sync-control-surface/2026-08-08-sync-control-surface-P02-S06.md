---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:46987bb4817c45e12cafd1549232420acbc74ff2a1828a6788ab42691ea99fe7'
step_id: 'S06'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# prove a dry-run writes nothing on either surface, by asserting the store and the remote plan are byte-identical across a preview run

## Scope

- `src/cadrumo/application/live/tests/test_filed_capture_dry_run_writes_nothing.py`
- `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_preview.py`

## Description

SCOPE CORRECTION from the row's own text. The row names
`src/cadrumo/application/live/tests/` as the sole scope, which fits the filed
sweep but has no analogue for the Sheets surface — the Sheets proof has to
live beside the adapter it proves, under
`src/cadrumo/adapters/outbound/google/tests/`, matching where every other
proof for that adapter already lives (see `test_calc_sheets_apply_no_empty_window.py`
for the same shape against the write-ordering fix).

The two surfaces need two different KINDS of proof, and this row keeps that
difference explicit rather than forcing one test shape onto both.

**Filed surface: a real encrypted store, before and after.** The store this
surface writes to is `secure_object_repository_for_active_bucket()` — genuine
encrypted SQLite, not a mock — so "byte-identical" is checked literally, via
`read_db_at_rest_bytes` (the project's own at-rest-scan helper, repurposed
here for equality rather than plaintext-leak scanning) against the real
bucket database file. The one hazard: opening a secure-object repository for
the FIRST time in a fresh bucket can itself write schema DDL, regardless of
whether any row is ever inserted, so snapshotting before that first touch
would make an untouched-vs-bootstrapped diff masquerade as a dry-run write.
The test warms the exact read path `_CaptureAccumulator.absorb` exercises
(`recapture_divergence_notices`) BEFORE taking its baseline snapshot, so only
the `absorb(dry_run=True)` call under test can move the needle. A positive
control — a second `absorb(dry_run=False)` call against the same store —
proves the equality assertion is not vacuous by showing the bytes DO move
when a real write happens.

**Sheets surface: no live account exists to write to, so the proof is
structural plus a pure positive control.** Every test in this package's
`tests/` directory is offline by written policy (write-shaped online tests
are project-forbidden here); this row does not carve an exception. The
`TestPreviewNeverWrites` class parses `preview_export_plan`'s own source with
`ast`, strips its docstring (which legitimately narrates the write helpers it
must never reach, so leaving the docstring in would produce a false positive
against prose), and asserts none of the eight write-capable helper names or
six write-shaped Sheets/Drive action labels appear in the remaining code, plus
that only the two read-only Drive lookups are called. The pure positive
control (`TestPreviewComputationReusesTheRealAdaptersOwnDiffPrimitives`)
confirms `stale_addresses` returns nothing to clear when the plan's written
set is compared against itself as the occupied set — the "already
byte-identical" case a real re-apply-the-same-plan run would present.

## Outcome

Both proofs are green (see `P02.S05`'s exec record for the full offline suite
run covering the Sheets half's twelve tests). The filed-surface test alone:

```
pytest src/cadrumo/application/live/tests/test_filed_capture_dry_run_writes_nothing.py
1 passed
```

It additionally asserts, alongside the byte-identical database check, that
the accumulator's `absorbed_count` still increments under `dry_run=True`
(the reached tally the sync-run record depends on must not go blind on a
preview) while `observation_paths` and `filing_record_ids` stay empty (no
manifest persisted, no filing stamped).

## Notes

Nothing here claims a reproduction of an interrupted Sheets write — that
class of test needs a real account and is forbidden here, matching `P01`'s
own disclosed limit. What is proven is the property the row actually asks
for: no code path in either surface's dry-run branch reaches a write.

Ran locally, both files, real behaviour throughout: no mocks, no fakes, no
skipped tests. `ruff` / `ty` green.
