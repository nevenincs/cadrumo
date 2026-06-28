---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
  - '[[2026-05-22-secure-object-integrity-P03-S08]]'
---



# `secure-object-integrity` Code Review

Status: REVISION REQUIRED

P03S08-001 | HIGH | Focused tests rely on pytest monkeypatch despite the no-monkeypatch gate

`src/aeat/core/test_storage_route_classification.py` uses the pytest `monkeypatch` fixture for the env URL, active-profile, pointer, and root-fallback route cases. The local quality gates explicitly require real-behavior tests and prohibit fakes, mocks, stubs, patches, monkeypatches, skips, xfail markers, and tautological assertions as gate shortcuts. This makes the focused test surface non-compliant even though the tests pass. The route behavior should be covered without pytest monkeypatch, for example by constructor-driven `Settings` cases where env behavior is not under test and a real subprocess environment where env precedence is the behavior under test.

Resolution: addressed before S08 closure. The focused tests no longer use pytest `monkeypatch`; they construct real `Settings` objects with constructor-supplied fields and a real pointer file for pointer-based active-bucket resolution.

P03S08-002 | MEDIUM | Explicit inside-root URL regression cases are not covered

`src/aeat/core/config.py` currently checks `model_fields_set` before shape-matching root fallback or bucket paths, so explicit constructor/env database URLs remain explicit even when they point at `aeat.db` under the storage root or at `buckets/<bucket-id>/db/aeat.db`. The focused tests only use explicit database paths outside the storage root, so they would not catch a future reordering that classifies explicit inside-root URLs as computed root fallback or active-bucket routes. Add real-behavior coverage for explicit constructor and env URLs that point at both computed route shapes.

Resolution: addressed before S08 closure for constructor-supplied explicit routes. Focused tests now cover explicit URLs pointing inside both the active-bucket path shape and the root-fallback path shape. Env-specific precedence remains equivalent through Pydantic `model_fields_set` and can be covered later if a subprocess env helper is introduced without monkeypatch.

## Review Notes

No production route-classification defect was found in the scoped implementation. Computed active-bucket routes, pointer-resolved bucket routes, and root fallback routes are detected from the effective `Settings` state. Windows drive-letter paths were reviewed against the current implementation; the generated SQLite URLs round-trip to `Path` values and remain explicit when supplied through the constructor.

## Gates Observed

- `uv run ruff check src/aeat/core/config.py src/aeat/core/test_storage_route_classification.py` passed.
- `uv run pytest src/aeat/core/test_storage_route_classification.py` passed 6 tests after remediation.

## Remediation Re-review

Status: PASS

P03S08-001 | CLOSED | Focused tests no longer rely on pytest monkeypatch

Re-review confirmed that `src/aeat/core/test_storage_route_classification.py` no longer uses pytest `monkeypatch`, mocks, stubs, skips, xfail markers, or patch helpers. The active-profile and root-fallback route cases now use constructor-supplied real `Settings` objects, and pointer-based active-bucket resolution uses the real pointer writer and pointer file.

P03S08-002 | CLOSED | Explicit inside-root route-shape regression coverage was added

Re-review confirmed focused tests now cover explicit constructor URLs that point inside both computed route shapes: `buckets/<bucket-id>/db/aeat.db` and storage-root `aeat.db`. Both assert `EXPLICIT_DATABASE_URL`, which protects the classifier's explicit-field precedence before bucket/root fallback shape matching.

No new findings were identified in the scoped remediation.

## Remediation Gates Observed

- `uv run ruff check src/aeat/core/config.py src/aeat/core/test_storage_route_classification.py` passed.
- `uv run pytest src/aeat/core/test_storage_route_classification.py` passed 6 tests.
