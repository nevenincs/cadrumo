---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P06.S25'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P06.S25`

Closed EXIM-4: Google Sheets is documented and guarded as a one-way
export mirror.

- Verified: `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`
- Verified: `src/aeat/adapters/outbound/google/_calc_sheets_pull.py`
- Verified: `src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py`

## Description

The apply adapter carries a module-level one-way contract: Google
Sheets is an export mirror of registry-grounded engine output, not an
authority for tax data, and no path writes sheet content into local
storage, the registry, or AEAT submission.

The malformed-sheet guard exists in the pull-helper suite:
`test_classify_metadata_returns_stale_for_drifted_registry_sha`
constructs a workbook metadata shape whose modelo, revision, year, and
period align but whose registry SHA diverges. The pull adapter
classifies it as `stale`, which makes `compute_from_pull` refuse the
workbook instead of treating it as authoritative.

No duplicate documentation or tests were added.

## Tests

`uv run ruff check src/aeat/adapters/outbound/google/_calc_sheets_apply.py src/aeat/adapters/outbound/google/_calc_sheets_pull.py src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py` passed.

`uv run pytest -q src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py` passed with 23 tests in 22.01s.

`uv run pytest -q src/aeat/adapters/outbound/google/test_verify_pull_coverage.py` passed with 5 tests in 1.10s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S25` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P06-S25.md src/aeat/adapters/outbound/google/_calc_sheets_apply.py src/aeat/adapters/outbound/google/_calc_sheets_pull.py src/aeat/adapters/outbound/google/test_pull_adapter_helpers.py src/aeat/adapters/outbound/google/test_compute_from_pull.py src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only existing CRLF normalization warnings for locale files.
