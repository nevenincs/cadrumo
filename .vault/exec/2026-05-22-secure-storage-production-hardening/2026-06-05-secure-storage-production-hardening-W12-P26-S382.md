---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S382'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S382 - Close AFR-280 for ledger manifest discovery

Scope: close `AFR-280` for `src/aeat/entrypoints/cli/_ledger.py` with signals
`active-profile, manifest-bucket`, target `manifest-discovery`, and owner
`W12.P22.S90`.

## Description

- Audited the current ledger CLI after concurrent extraction of the ratios subgroup
  into `src/aeat/entrypoints/cli/_ledger_ratios_cli.py`.
- Cross-committed the ratios extraction because `_ledger.py` now delegates the active
  profile ratios surface to that module and the S382 fixes were validated through that
  path.
- Confirmed the main ledger command surface continues to obtain bucket-scoped
  transaction repositories through `_tx_repo()` and passes repository bucket ids into
  application services rather than opening raw storage routes.
- Hardened the extracted ratios event emission so `LEDGER_RATIOS_SET`,
  `LEDGER_RATIOS_UNSET`, and censo override-warning events use
  `secure_object_repository_for_bucket(bucket_id)` instead of ambient active-bucket
  repository construction.
- Restored the localized ledger decimal refusal in the extracted ratios parser and
  added a CLI regression that asserts the `cli.ledger.errors.invalid_decimal` message
  through `tr()`.
- Added a debug breadcrumb when a censo ratio mismatch is intentionally surfaced as an
  operator-visible warning row instead of aborting the list command.
- Closed `W12.P26.S382` through `vaultspec-core vault plan step check` and updated the
  `AFR-280` register status to `closed`.

## Outcome

`AFR-280` is closed as `manifest-discovery`. Ledger remains the intended active-profile
CLI surface for transaction management; ratio override mutations now live in a smaller
module but still resolve active buckets through the core active-profile authority,
persist through application/domain services, and emit bucket events through an explicit
bucket-bound secure-object repository.

Validation passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/_ledger_ratios_cli.py src/aeat/entrypoints/cli/tests/test_ratios_verbs.py src/aeat/entrypoints/cli/tests/test_ledger_ratios_verbs.py`
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_ratios_verbs.py src/aeat/entrypoints/cli/tests/test_ledger_ratios_verbs.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

The `_ledger.py` extraction existed as shared dirty work before this slice. Because the
tested S382 behavior depended on that extraction, the step record treats it as an
intersecting cross-commit rather than an unrelated local edit.
