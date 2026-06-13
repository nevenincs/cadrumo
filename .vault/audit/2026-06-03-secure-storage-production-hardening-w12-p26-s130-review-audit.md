---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S130]]'
---

# `secure-storage-production-hardening` `W12.P26.S130` Review

## S130-001 | PASS | Calc-sheets pull is gated remote readback, not local persistence

The reviewed module reads operator-edited Google Sheets values back into typed `PullResult` records. It is a remote-provider boundary, but it does not mutate local state, construct secure-object repositories, route SQL storage, select a local storage provider, or write local files.

The safety gates are explicit before local compute can consume pulled data: `_verify_ownership()` refuses Drive files without the app ownership marker, `_classify_metadata_match()` marks workbooks stale or missing unless registry coordinates and registry SHA match the supplied snapshot, and `compute_from_pull()` raises `OutboundStorageConflictError` unless the pull metadata still binds to the snapshot.

Google API and validation failures stay on typed outbound storage exceptions. The reviewed module does not use naked environment access.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/google/test_calc_sheets_apply.py` passed with 38 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/google/_calc_sheets_pull.py src/aeat/adapters/outbound/google/test_calc_sheets_pull_typing.py src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/adapters/outbound/google/test_calc_sheets_apply.py` passed.
- A source scan found no naked environment reads, DB route setup, secure-object repository constructors, local storage provider constructors, or direct local file read/write calls in `_calc_sheets_pull.py`.

Disposition: close `AFR-028` as `remote-mirror`.

## S130-002 | MEDIUM | RESOLVED | Duplicate workbook identity metadata could collapse by API order

The live workbook already carried duplicate developer metadata from repeated exports. The previous pull implementation merged metadata into a dict with last-write-wins behavior, so conflicting duplicate values for `aeat_registry_sha`, modelo, revision, year, or period would make stale/conflict classification depend on Google API ordering.

Resolution: duplicate sensitive identity metadata and relation metadata now raise `OutboundStorageConflictError` when values conflict. The refusal carries the `adapters.google.calc_sheets.errors.conflicting_duplicate_metadata` translated-message key and a `tr()`-resolved re-export suggestion. Repeated `aeat_exported_at` stamps for the same registry slice remain tolerated because timestamps do not define workbook identity.

Validation:

- `test_pull_adapter_helpers.py` now proves conflicting duplicate `aeat_registry_sha` entries are refused, repeated `aeat_exported_at` entries are accepted, and the conflict exposes a locale-backed message/suggestion.
- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- The focused Google adapter suite passed with 131 tests.
- The live pull/compute command still succeeds for the existing same-slice duplicate workbook.

## S130-003 | MEDIUM | RESOLVED | Remaining pull refusals lacked localized operator messages

Follow-up review found that blank spreadsheet id, foreign Drive ownership, and metadata/snapshot compute mismatch refusals still lacked localized messages or `tr()` remediation. Those refusal paths now carry translated-message keys under `adapters.google.calc_sheets.errors`; the ownership and compute guidance resolves through `tr()` suggestions.

Validation:

- `uv run --no-sync -q python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py` passed.
- Targeted Ruff passed for `_calc_sheets_pull.py` and the focused tests.

ADR grounding: the 2026-06-03 modelo export evidence/workbook parity ADRs were reviewed. This step remains a Google Sheets transport hardening step only; it does not claim the new evidence-bundling surface, official-layout parity gate, or offline/online workbook parity contract.
