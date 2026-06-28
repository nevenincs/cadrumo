---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S17'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-active-profile-storage-runtime-discovery-audit]]'
---



# `secure-storage-production-hardening` `W02.P04.S17`

Enrolled the live census snapshot repository in runtime-created, bucket-attached secure storage and regrounded live snapshot and IVA wallet backend tests on active-profile runtime settings.

## Changes

- Routed `CensoSnapshotRepository` default secure-object construction through the runtime bucket repository factory while preserving explicit object injection for controlled tests.
- Kept `Borrador100SnapshotRepository` on its existing runtime-backed lazy construction and moved its roundtrip coverage from direct database routing to active `BucketSession` runtime setup.
- Regrounded census snapshot, borrador snapshot, IVA wallet capture backend, and filed-calculation-history tests on `override_settings(aeat_local_storage_root=...)` plus active bucket sessions instead of explicit database URLs or ephemeral-provider setup.
- Preserved injection-only live tests for snapshot base and borrador repository behavior; those remain controlled repository tests rather than production default-construction paths.
- Left JSONL notification and expediente snapshot stores unchanged because their plain-file migration is tracked by later live snapshot storage migration rows.

## Validation

- `uv run ruff check src/aeat/application/live/_censo.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py`
- `uv run pytest src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py -q`
- `uv run pytest src/aeat/application/live/test_borrador_100.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_snapshot_base.py -q`
- `uv run ruff check src/aeat/application/live/_censo.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py`
- `uv run pytest src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py -q`
- `uv run pytest src/aeat/application/live -q`
- `uv run python -m aeat.locales audit`
- `rg 'EphemeralMasterKeyProvider|SecureObjectRepository\(|get_engine|AEAT_DATABASE_URL|monkeypatch|aeat_database_url|Base\.metadata' src/aeat/application/live/_censo.py src/aeat/application/live/test_census_snapshot.py src/aeat/application/live/test_borrador_100_roundtrip.py src/aeat/application/live/test_iva_wallet_capture_backend.py src/aeat/application/live/test_filed_capture_calculation_history.py -n`

## Review

The S17 surface no longer has production direct `SecureObjectRepository()` construction inside `src/aeat/application/live`. Remaining direct construction matches injection-oriented tests. The mandatory S17 review raised one low anti-tautology test-quality finding; it was resolved before closeout and documented in `2026-05-26-secure-storage-production-hardening-W02-P04-S17-review-audit`. Notification and expediente JSONL stores remain visible plain-file state and are intentionally deferred to later live snapshot migration steps.
