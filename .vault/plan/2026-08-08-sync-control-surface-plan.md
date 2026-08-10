---
tags:
  - '#plan'
  - '#sync-control-surface'
date: '2026-08-08'
modified: '2026-08-10'
body_hash: 'sha256:f4107ff4d4fdfd3e5cb6b0b0c15fbae31082627011360f4390855007a69eaaa5'
tier: L2
related:
  - '[[2026-08-08-sync-control-surface-adr]]'
  - '[[2026-08-08-sync-control-surface-reference]]'
---

# `sync-control-surface` plan

## Description

Executes the `sync-control-surface` ADR. That record rules on the shape of sync
controls across the Google Sheets calculation export and the AEAT filed-history
sweep; none of it is implemented, and this plan is the row set that carries the
implementation debt the ruling created.

The ADR is a ruling on code and is not self-executing. Without these rows the
record reads as in force while HEAD carries none of it, and a later reader
believes it shipped. Grounding for every Step — the exact modules, the existing
differs to relocate, and the write mechanics — lives in the feature's reference
document.

Phase `P01` is independent of the ruling and should not wait for it: it closes a
live defect that can empty an operator's workbook today.

## Steps

### Phase `P01` - Close the Sheets torn-write window

An interruption between the batch clear and the batch update empties the operator's workbook today. This is a live defect and the precondition for any cancellation affordance.

- [x] `P01.S01` - gate the ordering property offline - the whole-tab clear is gone and the stale set never names a written cell - since an interruption between two live Sheets calls cannot be reproduced without a forbidden online write; `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_apply_no_empty_window.py`.
- [x] `P01.S02` - make the tab surface survive an interruption between the two calls, so a partial apply never leaves the operator's workbook empty; `src/cadrumo/adapters/outbound/google/_calc_sheets_apply.py`.

### Phase `P02` - Dry-run on both sync surfaces

One flag spelled the same way on both mutating verbs, with the preview payload declared per write shape: cell-level for the Sheets overwrite, record-level for the filed upsert.

- [x] `P02.S01` - relocate the recapture divergence computation to run BEFORE the upsert instead of after it, preserving the existing notice; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P02.S02` - add the dry-run short-circuit to the filed sweep, returning the divergence set the upsert would introduce without writing; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `P02.S03` - expose the filed sweep dry-run flag and carry its state as primary result data on the envelope, never as a notice; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [x] `P02.S04` - reuse the verify parity comparison to build the export preview, rather than growing a second differ; `src/cadrumo/application/storage/calc_sheets/_parity_harness.py`.
- [ ] `P02.S05` - add the dry-run short-circuit and flag to the Sheets export, reporting the ranges it would clear and the cells that would change; `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`.
- [ ] `P02.S06` - prove a dry-run writes nothing on either surface, by asserting the store and the remote plan are byte-identical across a preview run; `src/cadrumo/application/live/tests/`.

### Phase `P03` - Last-sync provenance and scope honesty

A local typed sync-run record replacing the remote developer-metadata stamp as the provenance authority, plus a truncation notice so a limited sweep cannot read as complete coverage.

- [ ] `P03.S01` - define the typed sync-run record carrying surface, resolved scope, completion instant, unit counts and divergence count; `src/cadrumo/application/storage/`.
- [ ] `P03.S02` - persist the sync-run record on completion of each surface, on partial failure as well as success, with a strict roundtrip through the real encrypted store; `src/cadrumo/application/storage/`.
- [ ] `P03.S03` - emit a truncation notice when a sweep is limited, so a partial run cannot read as complete coverage; `src/cadrumo/entrypoints/cli/_app_live.py`.

## Parallelization

Phase `P01` carries no dependency on the other two and should be executed first
and independently; it closes a live defect.

Phases `P02` and `P03` share no hard interdependency and may run in parallel.
Within `P02`, the filed-sweep chain (`S01` through `S03`) and the Sheets chain
(`S04`, `S05`) are independent of each other; `S06` depends on both.

`P02.S01` must land before `P02.S02`: the dry-run has nothing to report until
the divergence computation runs ahead of the write.

## Verification

- The window is closed structurally rather than by reproduction: no code path
  clears a bare tab range, and the stale set is derived from what the write
  returned so it can never name a cell the write covered. An interruption
  reproduction is deliberately absent -- it would need a write-shaped online
  test against a real account, which is forbidden here -- so nothing in this
  plan should be read as claiming one exists.
- A dry-run on each surface leaves the observation store and the remote
  spreadsheet byte-identical, asserted against the real store rather than a
  mock.
- The dry-run state is present as primary result data on both envelopes and
  absent from the notices channel, per the CLI envelope contract.
- A sync-run record exists after both a successful and a partially-failed sweep,
  and survives a strict roundtrip with every defaultable field populated
  non-default.
- A limited sweep emits the truncation notice; an unlimited one does not.
