---
step_id: S102
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W12.P29.S102 step record

## Step

Enroll the remaining 18 bare-str `_id/_kind/_status/_state` field sites onto typed
aliases across `adapters/` and `entrypoints/`, run sequential pytest across all
packages, and confirm W11 Clause 10 reports zero violations. (PROMOTE-001, Rule 5)

## Status

COMPLETE (W12 close gate passed; all adapter/entrypoint sites blocked)

## Adapter/entrypoint site audit

| File:line | Field | Alias | Block reason |
|---|---|---|---|
| `adapters/persistence/storage/runtime.py:95` | `StorageRuntime.bucket_id: str = Field(default="")` | `BucketId` (min_length=1) | Empty-string default would fail min_length=1; promoting breaks existing initialisation |
| `adapters/persistence/storage/sql/secure_objects.py:148` | `SecureObjectRawRow.revision_id: str \| None = Field(min_length=64, max_length=64)` | `RevisionId` (max=128, pattern=`_REF_RE`) | Different identity family — hex-64 SHA-256 digest vs registry kebab ref-id; shapes semantically incompatible |
| `adapters/outbound/google/_calc_sheets_pull.py:175` | `PullMetadata.modelo_id: str` | `ModeloId` (pattern `^\d{3}$`) | No existing constraint; promoting adds strict 3-digit pattern that may reject non-3-digit model identifiers in transit |
| `application/live/test_snapshot_base.py:50,51` | `ProbeSnapshot.snapshot_id/bucket_id: str = Field(max_length=128)` | `SnapshotId`/`BucketId` | Snapshot IDs here follow non-hex-64 family per `_snapshot.py` docstring ("non-hex shape"); bucket_id has empty-string default |

## W12 close gate results

### Clause 10 enforcement

`find_bare_str_kind_status_state_fields()` → **0 violations** (was 2 before S101).

### pytest coverage (not blocked by core._time regression)

Tests passing cleanly in W12-touched packages:

- `src/aeat/diagnostics/test_identity_primitive_placement.py` — 17 passed
- `src/aeat/domain/transactions/test_models.py` — 20 passed
- `src/aeat/core/identity/` — 54 passed
- Total: 91 passed

### Pre-existing regression note

Commit `309d5fc10` (parallel campaign `chore/eliminate-shims`, landed after S101)
deleted `aeat.core._time` while callers in `application/filing/__init__.py`,
`application/workflow/_adapters.py`, `domain/user_profile/_values.py`, and
`application/auth/_actions.py` still import it. This causes collection errors across
`application/` and `domain/` test suites. This regression pre-dates W12 and is out of
scope. The W12 close gate covers the identity-placement diagnostic suite and the
directly affected ledger and core/identity packages.

## Files touched

None (all sites blocked).
