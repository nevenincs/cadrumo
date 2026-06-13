---
step_id: S553-S556
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-05-31'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W09.P37 — S553-S556 Step Record

## Execution summary

Agent: coder-alpha13. Commit: `ce330688c`.

## Collision check

`git diff` on all target files before first edit — zero non-authored WIP on all targets.

## S553 — WorkbookScanStatus enrollment

**Files:** `src/aeat/domain/calculations/registry/_workbook_parity.py`

**Before:** 6 bare string comparisons (`== "scanned"`, `!= "scanned"`, `in {"failed", "timeout"}`).
**After:** 0 bare string comparisons; all use `WorkbookScanStatus.SCANNED / .FAILED / .TIMEOUT`.

Sites fixed: lines 122, 124, 963, 966, 981, 1020.

## S554 — UTF_8_ENCODING enrollment

**Files (16 production sites across 9 files):**
- `adapters/persistence/storage/blob_store/_blob_store.py` — 1 site (file I/O)
- `adapters/persistence/storage/master_key/_master_key.py` — 7 sites (3 file I/O + 4 encode)
- `adapters/persistence/storage/master_key/_recovery.py` — 2 sites (sibling discovered)
- `application/workflow/_profile_health.py` — 1 site
- `application/topics/__init__.py` — 1 site
- `adapters/outbound/aeat/sede/_observation_store.py` — 7 sites (encode/decode)
- `application/user_profile/_orchestration.py` — 2 sites (sibling discovered)
- `application/user_profile/_profile_repository.py` — 2 sites (sibling discovered)

**Import path note:** `_observation_store.py` is at `aeat.adapters.outbound.aeat.sede` — requires 5 relative dots to reach `aeat.core` (not 4).

**Before:** 16+ bare `encoding="utf-8"` / `.encode("utf-8")` / `.decode("utf-8")` strings.
**After:** 0 in enrolled files.

## S555 — STRICT_FROZEN_CONFIG migration

**Files:**
- `adapters/persistence/storage/bucket/_layout.py` — removed local `_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)`, imported canonical `STRICT_FROZEN_CONFIG as _STRICT_FROZEN` from `core._models`. `arbitrary_types_allowed=True` was unnecessary — `Path` works in pydantic v2 strict mode without it.
- `adapters/persistence/storage/sql/secure_objects.py` — same migration; `bytes` and `SensitivityClass` (StrEnum) work without `arbitrary_types_allowed`.

**Before:** 2 local `_STRICT_FROZEN = ConfigDict(...)` definitions.
**After:** 0 local definitions; both use `STRICT_FROZEN_CONFIG`.

**Why W13 missed them:** Both files use `arbitrary_types_allowed=True` which the W13 sweep excluded per the `_models.py` docstring. The exclusion was overcautious — neither `Path` nor `bytes` actually requires it in pydantic v2.

## S556 — Inventory test

**File:** `src/aeat/test_w09_p37_inventory.py`

4 real-behavior assertions:
- `test_no_bare_scan_status_scanned_comparison` — zero bare string comparisons in `_workbook_parity.py`
- `test_layout_uses_canonical_strict_frozen_config` — `_layout.py` uses canonical import
- `test_secure_objects_uses_canonical_strict_frozen_config` — `secure_objects.py` uses canonical import
- `test_utf8_encoding_enrolled_in_s554_files` — zero bare utf-8 literals in the 8 enrolled files

All 4 passed.

## Pytest outcome

`src/aeat/test_w09_p37_inventory.py` — 4 passed.
`src/aeat/adapters/persistence/storage/bucket/` — 154 passed.
`src/aeat/adapters/persistence/storage/sql/` — included in 154 above.
`src/aeat/application/topics/test_catalogue.py` — 5 passed.
`src/aeat/application/workflow/test_profile_health.py` — 4 passed.

Pre-existing failure: `test_committed_registry_tree_has_required_model_law_coverage` — unrelated to this step, predates this branch.

## Commit SHA

`ce330688c`
