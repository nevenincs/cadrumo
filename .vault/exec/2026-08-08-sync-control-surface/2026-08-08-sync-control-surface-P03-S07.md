---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:a62d95308a4b16b9dde807eb8da22861037a347ddf13666e12a6b0a402ad3bcd'
step_id: 'S07'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# Introduce the application-layer export service the workbook-export CLI calls, so the sync-run record can be persisted on that surface at all. This row exists because the sibling persistence row assumed both surfaces have an application-layer completion point and only one does. The filed sweep completes inside the application layer with the bucket id already in scope, so its record is one call. The workbook export completes inside the CLI handler, which calls the outbound Google adapter directly, and there is no application function between them. Persisting from the entrypoint would make it the first CLI site writing to a secure-object namespace, and persisting from the adapter would have an outbound adapter reach back into application storage and invert the dependency direction, which is a cycle rather than a layering preference. Both are refused outright rather than weighed. The remaining option is to move plan build and apply orchestration into an application service the CLI then calls, which touches a shipped verb's path and is why this is its own row rather than a clause inside persist the record on completion. Note additionally that failure on this surface RAISES rather than returns, so recording on partial failure as well as success needs the write in the failure path too, and doing that from the CLI would put the partial-failure semantics of a persistence contract inside an entrypoint. The record and its writer already exist and are verified, so this row introduces no new storage concept and only gives the second surface a legal place to call from

## Scope

- `src/cadrumo/application/storage/calc_sheets/_export_service.py`
- `src/cadrumo/application/storage/calc_sheets/__init__.py`
- `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`

## Description

`export_modelo_to_sheets` is the new application-layer seam, added to the
EXISTING `application/storage/calc_sheets` package (matching `P03.S01`'s own
correction that this package, not a namespace-container parent, is the
record's home) rather than a new subpackage — the row's premise was that no
application function sat between the CLI and the adapter, and the fix is to
introduce exactly that one function, not a new package around it.

It takes an ALREADY-BUILT `SheetExportPlan` rather than building one from a
snapshot: the CLI's dry-run branch (`P02.S05`) needs the identical plan for
its preview, and building the plan twice — once for the preview, once for the
service — would let the two branches drift on what they describe. So the CLI
still builds the plan once, then branches on `dry_run` to either
`_emit_calc_export_preview` (which never calls this service) or
`export_modelo_to_sheets` (the real write).

Failure handling follows the row's own reasoning to the letter: `apply_export_plan`
RAISES rather than returns a failure value, so the `except Exception` arm
persists a `succeeded=False` record with `_SingleExportCoverage(reached=False)`
and then RE-RAISES the original exception unchanged — the CLI's existing
`except (GoogleAuthError, OutboundStorageError)` handling around the call site
is untouched and still converts it to the same operator-facing refusal it did
before this row.

`_SingleExportCoverage` is a new, narrow `SyncRunCoverageSource`: unlike the
filed sweep, which walks many declarations and can genuinely complete some
while failing others, one export call materialises exactly one
modelo+period+year workbook in a single write — there is no population to
walk WITHIN it. `reached_count` is `1` once the write completes and `0` when
it never got there; `divergences` is always empty, because detecting whether
a written value diverges from anything is `verify`'s concern (its own
scenario, its own AEAT oracle), never the export's — the export overwrites
its target unconditionally rather than comparing against it.

## Outcome

`aeat config google sync calc export` (the real, non-dry-run branch) now
calls `export_modelo_to_sheets(plan, credentials=..., root_folder_id=...,
sync_run_repository=SyncRunRecordRepository())` instead of calling
`apply_export_plan` directly. The CLI's own result-building and rendering are
unchanged; only the call site moved, and the record it now writes closes the
gap `P03.S01`'s exec record named as the row's largest scope correction.

See `P03.S02`'s completion record for the persistence-half verification
(real-store failure-path proof, the coverage-floor gate) — this row's own
scope is the seam, that row's is the completed persistence contract across
both surfaces.

## Notes

`export_modelo_to_sheets` imports `apply_export_plan` from
`adapters.outbound.google` lazily, inside the function body, matching the
existing pattern in `application.live._filed_data_capture` (which imports
`adapters.outbound.aeat.sede` directly) — application importing a concrete
outbound adapter is the accepted direction in this tree; only DOMAIN must
stay adapter-independent. No Protocol indirection was introduced because none
of the sibling application-layer callers of an outbound adapter use one
either.
