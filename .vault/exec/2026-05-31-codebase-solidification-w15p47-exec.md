---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S614'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W15.P47.S614-S619

Closed all 6 steps in the W15.P47 maintenance batch: 5 low-volume structural markers/constants + 1 aggregate test.

- Modified: `src/aeat/application/registry/_corpus.py`
- Modified: `src/aeat/core/config.py`
- Modified: `src/aeat/application/user_profile/_censo_sync.py`
- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Created: `src/aeat/test_w15_p47_maintenance_closure.py`

## Description

S614: Added `BROAD-EXCEPT-RATIONALE-CORPUS-LOOKUP-BOUNDARY` inline comment on the `except Exception` at `_corpus.py:334`. Rationale documents that `find_reference`/`find_articulo` surface heterogeneous catalogue-specific exceptions; warning-and-continue is the lookup boundary contract.

S615: Added `BROAD-EXCEPT-RATIONALE-POINTER-READ-FALLBACK` inline comment on `config.py:999`. Rationale documents that `read_pointer` raises `OSError`, `json.JSONDecodeError`, and `ValidationError` on filesystem/encoding/schema drift; degrades to `None` for best-effort active-bucket resolution.

S616: Extracted `_HOME_OFFICE_DEDUCTION_YEAR: Final[int] = 2025` module-level constant in `_censo_sync.py` (after the existing `CENSUS_SOURCE_TAG`). Migrated the bare `year=2025` at the `derive_home_office_ratios_from_census` call-site to reference the constant.

S617: Added `from datetime import date` and `Final` to `diagnostics.py` imports. Extracted `_REGISTRY_INTEGRITY_PROBE_YEAR: Final[int] = 2025` and `_REGISTRY_INTEGRITY_PROBE_DATE: Final[date] = date(2025, 12, 31)` after `_log`. Migrated the two bare literals in `authority.snapshot(...)` to reference the constants.

S618: Chose option (b) — `_registry_tree_fingerprint` uses relative-path keying (distinct from filename-keyed canonical `file_stat_fingerprint`); refactoring to option (a) would require a canonical signature change rippling through 4 existing callers. Added `ALT-FINGERPRINT-RATIONALE-REGISTRY-TREE` inline marker on the function definition.

S619: Created `src/aeat/test_w15_p47_maintenance_closure.py` with 11 real-behavior tests asserting all 5 structural closures landed and 4 W14 ratchets remain intact. All 25 tests (11 new + 14 existing W14) pass.

## Tests

`pytest src/aeat/test_w15_p47_maintenance_closure.py src/aeat/test_w14_p46_survivor_closure.py` — 25 passed, 0 failed.
