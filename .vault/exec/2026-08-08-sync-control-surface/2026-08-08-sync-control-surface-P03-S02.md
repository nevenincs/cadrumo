---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:ccc9a7aa57604eb162d9a0f74ddb58f5517457349b1a96cffdfec90acaf414d5'
step_id: 'S02'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# Persist the sync-run record on completion of each surface, on partial failure as well as success, with a strict roundtrip through the real encrypted store. Partial failure means a run that TRIED to write and got partway, which is a different event from a run that declined to write by design, so the clause binds the real path at full strength and does not reach the preview branch. A DRY RUN WRITES NO RECORD and that absence is declared rather than accidental. A preview reads the remote surface and persists nothing, so it has no last-sync provenance because nothing was synced, and a provenance record is itself a persist that would defeat the guard whose entire purpose is leaving no trace. Delivered in ONE commit with the sibling row and one exec record covering both, because a typed record whose persistence is unwritten is the design-only implementation shell the architecture rules prohibit and its roundtrip is what proves the field types are right. The co-write uses the secure-object batch save with the record repository and the catalogue repository bound to the SAME repository instance so both writes share one session scope, which is the canonical pattern rather than a per-repository wrapper method, and the surface-level event is emitted IN ADDITION to the primitive's lifecycle event rather than instead of it. The roundtrip populates every defaultable field with a non-default value and carries an anti-tautology proof that mutates the on-disk payload and asserts refusal

## Scope

- `src/cadrumo/application/storage/sync_runs and src/cadrumo/application/live and src/cadrumo/application/storage/calc_sheets`

## Description

COMPLETION RECORD. `P03.S01`'s exec record already covers the filed-sweep
half of this row in full — the co-write mechanics, the roundtrip proof, the
anti-tautology proof — and states explicitly that it was "delivered for one
of the two surfaces", with the second (Sheets export) blocked on `P03.S07`
introducing an application-layer call site to persist from. That record is
left standing rather than rewritten: it is accurate for what was true when it
was authored.

`P03.S07` closes that gap. `export_modelo_to_sheets`
(`application/storage/calc_sheets/_export_service.py`) now calls
`record_sync_run` on BOTH the success path and the failure path, using the
SAME `record_sync_run` / `coverage_of` primitives the filed sweep already
uses — no second persistence mechanism, matching the row's own "one
canonical mechanism" framing.

## Outcome

Both surfaces are now covered:

- Filed declarations: `capture_filed_data_bulk`, via
  `_persisted_bulk_filed_capture_report`, unchanged from `P03.S01`.
- Calc-sheets export: `export_modelo_to_sheets`, new in `P03.S07`, records on
  success (`succeeded=True`, `SyncRunCoverage` derived from
  `_SingleExportCoverage(reached=True)`) and on failure (`succeeded=False`,
  `_SingleExportCoverage(reached=False)`, then re-raises unchanged) — because
  `apply_export_plan` RAISES on refusal rather than returning a failure
  value, so recording partial failure needs the write in the `except` arm,
  which is exactly what `P03.S01`'s exec record flagged as the row's second,
  larger scope gap.

A dry run still persists nothing on either surface: the filed preview branch
returns before reaching `record_sync_run` (`P03.S01`'s ordering, unchanged),
and the Sheets preview (`preview_export_plan`, `P02.S05`) never calls
`export_modelo_to_sheets` at all — the CLI branches to the preview function
BEFORE the real-apply branch that owns the sync-run call, so the two paths
are structurally disjoint rather than guarded by a flag inside one function.

`test_a_failed_apply_still_persists_a_sync_run_record_and_reraises` in
`application/storage/calc_sheets/tests/test_export_service.py` proves the
failure-path co-write against the real encrypted store (not a mock): a blank
`root_folder_id` fails inside `apply_export_plan`'s own first line, before any
network call, which is what makes the failure deterministic and
offline-triggerable while still being the SAME exception class a live refusal
would raise. The test asserts the record's `surface`, `succeeded=False`,
`unit_count=0`, `divergence_count=0`, and that its named bucket event exists
alongside it with `BucketEventType.SYNC_RUN_CALC_SHEETS_EXPORT_COMPLETED`.

The success path is not exercised in tests: it requires a real Google
account, and write-shaped online tests are project-forbidden for this
adapter (see `P02.S05`'s and `P02.S06`'s records for the same limit applied
to the preview). `record_sync_run`'s own roundtrip proof, populated with a
non-default `SyncSurface.CALC_SHEETS_EXPORT` value and covered by an
anti-tautology corruption test, already lives in `P03.S01`'s scope
(`application/storage/sync_runs/tests/test_sync_run_record_store.py`) and is
unchanged — this row adds a second real CALLER of that already-proven store,
not a second store.

## Notes

`test_every_production_run_record_derives_its_coverage_from_a_source`
(`sync_runs/tests/test_sync_run_record_store.py`) walks every production
`record_sync_run` call site and requires `coverage=coverage_of(...)`; the two
new call sites in `_export_service.py` pass that floor unchanged, so a
lying-coverage regression on the Sheets surface would fail the same
tree-wide gate the filed surface is already held to.
