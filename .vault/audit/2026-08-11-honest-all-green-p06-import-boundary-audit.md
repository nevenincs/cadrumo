---
tags:
  - '#audit'
  - '#honest-all-green'
date: '2026-08-11'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:a292d408c89126c0c6302974d6eb2e201d2bafc35cfec65c72977f6a18ebc2d7'
related:
  - "[[2026-07-14-honest-all-green-adr]]"
---

# `honest-all-green` audit: `P06 import-boundary review`

## Scope

## Findings

### sync-run-repository-nullability | high | the new application port is still optional at its required write site

`capture_filed_data_bulk` rejects a missing `sync_run_repository` for a non-preview capture, but the later `record_sync_run` call receives the unchanged `SyncRunRecordRepositoryProtocol | None` variable. Targeted `basedpyright` therefore rejects `src/cadrumo/application/live/_filed_data_capture.py:901` because the writer requires a non-optional protocol. This is P06-owned and prevents the strict type lane from reaching green, despite the focused real-stack behavior tests passing. The concrete `SyncRunRecordRepository` remains adapter-owned, the application imports only `SyncRunRecordRepositoryProtocol`, and the CLI composition root supplies the concrete adapter; no persistence implementation leaked back into application.

#### Resolution

The non-preview preflight remains before any capture write, and the post-preview persistence boundary now repeats the missing-port refusal immediately before finalization and `record_sync_run`. That second guard narrows the value to `SyncRunRecordRepositoryProtocol` at the required call without a cast or assertion. Targeted `basedpyright` reports zero errors; the real sync-record and supported filed-capture suite reports 11 passed; scoped Ruff and `check-imports` are green.

#### Closure disposition

Resolved. Independent review confirms the second refusal occurs after the preview return and before either finalization or the provenance write, so a persisted capture cannot reach `record_sync_run` with a missing port. The exact targeted `basedpyright` command reports zero errors, and the real encrypted sync-run persistence suite passes 10 tests. The remediation retains the concrete repository in the persistence adapter and construction at the CLI composition root.

## Recommendations

- Resolve the non-preview guard into a non-optional local before `record_sync_run`, then rerun the targeted type check and the existing real persistence and filed-capture suites. Retain concrete construction exclusively at the entrypoint composition root.
