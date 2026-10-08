# Workbook materialization and sync-run provenance

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-099` · **Topic:** [Authentication and storage management](../topics/authentication-and-storage-management.md)

<!-- preserved:article -->
**Scope:** 4 files under `src/cadrumo/application/storage/calc_sheets` and `src/cadrumo/application/storage/sync_runs`, totaling 659 lines, 29,153 bytes, and 6,222 measured `o200k_base` proxy tokens. Both bounded-reader pages and all assigned ranges were read. Static inspection only; no workbook was materialized and no application execution or tests were run.

## Capabilities and mechanisms

`export_modelo_workbook` resolves one Modelo/period snapshot from the bundled indexed authority, builds one canonical sheet plan, passes only that plan to an injected materializer, and returns the resulting bytes with the facts that identify them. The result validates its byte count and SHA-256 against the actual payload. It also reports the plan’s revision and period, declared tab order, and count of distinct casillas carried as input/value cells or formulas. This seam returns bytes but does not choose a path or write a file; that decision belongs to the caller’s destination surface. Published snapshot resolution (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`), plan and optional relation prefills (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`), materialization and payload facts (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`)

Cross-revision relation prefilling is opt-in. When enabled, the plan builder resolves the workbook’s required relation values from this installation’s own local filings and records their provenance; when disabled, it supplies an empty relation set so the workbook does not imply unsupported facts. The caller can inject the snapshot resolver, plan builder, and materializer, keeping the export orchestration transport-neutral while still defaulting to the published registry and canonical engine. Local-only relation choice (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`), materializer port (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`)

The sync-run store records completed synchronization attempts separately for each declared surface. Each run stores its profile bucket, surface, resolved scope, success flag, unit count reached, divergences among those units, completion time, and the ID of its paired bucket event. Both success and partial failure are recordable; a dry run intentionally has no sync record. `record_sync_run` validates UTC time, maps the surface through a closed event table, creates the event and record together, and calls one repository method to save them atomically. Run record fields and semantics (`src/cadrumo/application/storage/sync_runs/records.py`), atomic record/event write (`src/cadrumo/application/storage/sync_runs/persist.py`)

Coverage is derived from one source object exposing both reached units and divergences, rather than accepting two unrelated counters at the call site. Both coverage construction and persisted-record validation require divergence count not to exceed reached count. Scope descriptions are capped at 256 characters; when the full enumeration does not fit, the helper summarizes the member count and first/last member instead of truncating to a misleading prefix. Storage keys include both the surface and the unique bucket-event identity, retaining multiple historical runs per surface rather than overwriting a single “last sync” value. Single-source coverage (`src/cadrumo/application/storage/sync_runs/records.py`), scope bound and coverage checks (`src/cadrumo/application/storage/sync_runs/records.py`), bounded scope and record keys (`src/cadrumo/application/storage/sync_runs/records.py`)

## Knowledge, security, and implementation assessment

The workbook wrapper trusts the registry snapshot and plan builder to define the workbook content, then validates that returned bytes match the accompanying digest and size. The workbook may contain taxpayer figures, so the export result is returned to its caller and is not written or logged in this layer. The transport receives no separate registry, ledger, or configuration capability; it materializes the already-resolved plan. Sync-run knowledge is an application-side account of what the run actually reached, while the paired bucket event gives history a compact reference to the fuller encrypted record. Payload validation and handling (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`), transport restriction (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`), sync-run storage contract (`src/cadrumo/application/storage/sync_runs/records.py`)

The main quality strength is that bytes and identity facts travel together, and that sync provenance survives partial failure without conflating a run’s success with divergence: a clean run may find divergences, and an unsuccessful run may have found none before stopping. Bound scopes and reached-unit counts let a later reader distinguish partial from complete coverage. Co-writing the record and event through the same persistence transaction prevents an orphan record or an unresolvable history event. Record/event pairing (`src/cadrumo/application/storage/sync_runs/persist.py`), coverage and success are independent (`src/cadrumo/application/storage/sync_runs/records.py`)

One failure-path detail needs verification. If the caller’s materializer fails, the workbook wrapper propagates that exception and writes no bytes. If recording the failed sync attempt then also raises, Python will expose the persistence exception in place of the original materializer exception; the caller may lose the first failure unless persistence or the surrounding error boundary preserves it. Test this double-failure behavior and decide which error should be primary. The record protocol documents atomicity but leaves the concrete secure-object transaction to the adapter, outside these files. Workbook return contract (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`), repository transaction boundary (`src/cadrumo/application/storage/sync_runs/records.py`)

## Dependencies and follow-up

Follow the injected materializer to both Google Sheets and XLSX implementations and confirm that neither writes outside its declared destination contract. Trace `resolve_relations_from_local_store` to ensure it returns only the intended local profile’s evidence and retains complete source grounding. Inspect the sync-run encrypted adapter for atomic co-write behavior, retention, and history projection. Add focused checks for payload digest/length mismatch, exact tab and casilla counts, opted-in versus blank relation cells, success and failed-run records, event/record rollback, and simultaneous apply plus provenance-write failure. No assigned tests or outbound writes were performed.

## Complete assigned-file coverage

All 4 assigned files were read fully across pages 1–2; no portions remain unread.

- calc_sheets/workbook_export.py (`src/cadrumo/application/storage/calc_sheets/workbook_export.py`)
- sync_runs/__init__.py (`src/cadrumo/application/storage/sync_runs/__init__.py`)
- sync_runs/persist.py (`src/cadrumo/application/storage/sync_runs/persist.py`)
- sync_runs/records.py (`src/cadrumo/application/storage/sync_runs/records.py`)
<!-- /preserved:article -->
