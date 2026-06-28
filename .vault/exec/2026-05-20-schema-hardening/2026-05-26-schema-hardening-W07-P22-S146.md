---
tags:
  - "#exec"
  - "#schema-hardening"
date: "2026-05-26"
modified: '2026-05-26'
step_id: "W07.P22.S146"
related:
  - "[[2026-05-20-schema-hardening-plan]]"
---

# schema-hardening W07.P22.S146 — hardcoded revision-id silent-regression fix

## Execution summary

Replaced all 9 hardcoded `"2019-y-siguientes"` (M130) and `"2024-y-siguientes"` (M123) revision-id literals in 4 test files with live snapshot derivation so tests remain correct if a registry revision is renamed.

## Files changed

**Priority sites (M130 silent-regression class):**

- `src/aeat/adapters/outbound/google/test_compute_from_pull.py` — 1 assertion site: `result.revision == "2019-y-siguientes"` replaced with `result.revision == snapshot.revision.id`; `snapshot` was already in scope.
- `src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py` — 6 input-data sites: all `"aeat_revision_id": "2019-y-siguientes"` in `pairs` dicts replaced with `"aeat_revision_id": snapshot.revision.id`; `snapshot` was already in scope in every test function.
- `src/aeat/application/filing/test_build_draft_identity.py` — 1 assertion site: `draft.snapshot_ref.revision_id == "2019-y-siguientes"` replaced with `draft.snapshot_ref.revision_id == snapshot.revision.id`; added `from datetime import date` and `from ...core.resources import resources` imports; snapshot derived via `resources().modelos.authority.snapshot("130", filing_year=2026, period="1T", on=date(2026, 4, 1))`.

**Additional M123 silent-regression sites in test_filing.py:**

- `src/aeat/application/filing/test_filing.py` — 2 assertion sites: both `schema_version == "registry:123:2024-y-siguientes"` replaced with `f"registry:123:{snapshot.revision.id}"`; added `from ...core.resources import resources` import; snapshot derived once per test via the same authority pattern.

**Pre-existing allowlist regression (no-out-of-scope-consolidation):**

- `src/aeat/adapters/outbound/google/test_package_module_allowlist.py` — enrolled `test_session_store_roundtrip.py` into `_ALLOWED_MODULES`; file was added by commit `af7300986` and caused a pre-existing failure in the targeted test scope.

## Verification

`uv run --no-sync pytest src/aeat/adapters/outbound/google/ src/aeat/application/filing/ -q --tb=line` — 312 passed (pre-existing allowlist failure was repaired as part of this step); targeted suite 44 / 44 after consolidation.

Ruff: all checks passed on all 5 modified files.
