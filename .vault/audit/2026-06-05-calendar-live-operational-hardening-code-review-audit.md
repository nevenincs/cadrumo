---
tags:
  - '#audit'
  - '#calendar-live-operational-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-calendar-live-operational-hardening-plan]]'
---

# `calendar-live-operational-hardening` Code Review

## CAL-LIVE-001 | MEDIUM | Bulk filed capture does not classify unsupported registry/live combinations before remote reads
`src/aeat/application/live/__init__.py` only treats modelo `721` as a local unsupported boundary via `_DECLARATIONS_REGISTER_UNSUPPORTED_MODELOS`, then sends every other requested registry modelo to the AEAT declarations register. That does not match the plan's unsupported-boundary contract: a modelo with no `authenticated_read_surface` / filed-declarations live cross-reference can be silently omitted when the register has no rows, or fail only later per declaration when `_read_guard_policy_from_snapshot` cannot find exactly one read surface. The report message also says the registry declares no filed-declarations surface, but the implementation is a hard-coded modelo list rather than a registry-derived check. The bulk path should derive support from the resolved registry revision for each `(modelo, year)` and append a structured failure without remote contact when the revision lacks the filed-declarations read surface.

## CAL-LIVE-002 | MEDIUM | `expedientes capture-all` makes bucket-global `latest` snapshots misleading
`src/aeat/application/live/__init__.py` persists one expedientes snapshot for every successful `(modelo, year)` query and stamps each snapshot independently with `now()`. `src/aeat/application/live/_expedientes.py` defines `latest()` as the bucket-wide max `captured_at`, so after `capture-all` the latest snapshot is just whichever modelo/year happened to run last, often an empty or unrelated query, not a coherent latest register refresh. The CLI now exposes a bulk refresh surface, but the existing latest contract remains single-snapshot oriented. Either `capture-all` needs an aggregate snapshot/manifest, or `latest` needs model/year-aware semantics so operators do not inspect the tail query as if it represented the full refresh.

## CAL-LIVE-003 | LOW | New CLI tests stop at help registration instead of payload behavior
`src/aeat/entrypoints/cli/test_registry_cli.py` verifies that `notifications latest` and `expedientes capture-all` help resolves and that Click commands exist, but it does not execute either command in `--format json` mode against real local persisted snapshots. That leaves the new `NotificationsLatestResult` and `ExpedientesCaptureAllResult` payload shapes, empty-state behavior, and text/json command names unpinned by focused tests. Given the global schema conformance gate is currently noisy with pre-existing failures, these new surfaces need direct behavior tests so regressions are attributable to this slice.

## CAL-LIVE-004 | LOW | Expedientes live reads reuse the filed-read operation label
`capture_expedientes_bulk` calls `_active_verified_session()` without an operation override, so auth/session diagnostics classify the command as `live-filed-read`. The existing single expedientes capture path has the same shape, but the new operator-facing bulk facade increases the visibility of this mismatch. Use a distinct operation such as `live-expedientes-read` for accurate auth logs, timeout diagnostics, and future audit filtering.

## Verification Notes

No HIGH or CRITICAL findings were identified.

Reviewed the scoped plan and the listed files only. The user-provided verification results were accepted as the authoritative test/live run record for this dirty shared worktree. An additional targeted schema-key probe was attempted with `uv run python`, but the local environment tried to reinstall `torch` and failed with an access-denied rename under `.venv`; no further environment repair was attempted during review.

## CAL-LIVE-005 | INFO | Review findings resolved after follow-up patch

CAL-LIVE-001 was resolved by deriving unsupported filed-capture rows from registry revisions and filed-declarations live cross-references per `(modelo, year)`, then proving the behavior with Modelos 151 and 721. CAL-LIVE-002 was resolved by changing `expedientes capture-all` to persist one aggregate snapshot for the whole refresh. CAL-LIVE-004 was resolved by using `live-expedientes-read` as the auth operation label. CAL-LIVE-003 remains a LOW residual because command registration tests now cover the new facades, but deeper JSON persisted-state behavior coverage is still future work while the broad schema conformance gate remains noisy.

## CAL-LIVE-006 | LOW | Single expedientes capture still uses the filed-read auth operation label

Follow-up review confirmed CAL-LIVE-001 is resolved for unsupported filed bulk capture: `capture_filed_data_bulk` derives local unsupported failures from the registry revision live cross-references before opening an authenticated session, and the focused test exercises Modelos 151 and 721 without live auth. CAL-LIVE-002 is resolved for `expedientes capture-all`: `capture_expedientes_bulk` accumulates declarations across successful queries and persists one aggregate snapshot. The bulk side of CAL-LIVE-004 is also resolved because `capture_expedientes_bulk` passes `operation="live-expedientes-read"`. However, `capture_expedientes` still calls `_active_verified_session()` without an operation override, so `aeat app live expedientes capture` continues to emit the default `live-filed-read` auth/session label. Either set the same `live-expedientes-read` operation on the single-capture path or explicitly document that CAL-LIVE-004 was scoped only to `capture-all`.

## CAL-LIVE-007 | INFO | Follow-up residual resolved

CAL-LIVE-006 was resolved by updating the single `capture_expedientes` path to pass `operation="live-expedientes-read"` to the shared auth/session acquisition helper. Ruff and the 61 focused tests passed after the patch.
