---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S252'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s252-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S252`

Closed `AFR-150` for the review operator projection.

## Description

- Reviewed `src/aeat/application/review/_operator.py` as a manifest-bucket projection layer.
- Sanitized operator errors so unknown review-kind, reserved-kind, and item-not-found failures do not render raw operator-supplied values.
- Kept accepted-kind diagnostics as static string context rather than echoing the rejected token.
- Routed review CLI `ReviewError` handling through the central `resolve_error_message` renderer instead of raw `str(exc)`.
- Repaired review operator locale strings through `python -m aeat.locales set`.
- Added real operator projection and CLI-boundary tests for sanitized review selector errors.
- Closed `S252` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-150` is closed as `manifest-discovery`. The operator projection still delegates storage discovery to `ReviewQueue.collect` and uses the active bucket id supplied by the core profile pointer, while user-facing errors no longer expose arbitrary kind tokens, reserved kind tokens, or requested review item ids. The accepted review-kind table is immutable at module load.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/review/_operator.py src/aeat/application/review/_errors.py src/aeat/application/review/test_operator.py src/aeat/entrypoints/cli/_review.py src/aeat/entrypoints/cli/test_review_operator_errors.py`
- `uv run --no-sync pytest -q src/aeat/application/review/test_operator.py src/aeat/entrypoints/cli/test_review_operator_errors.py src/aeat/entrypoints/cli/test_error_registry_contract.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

No secure-object write path lives in the operator projection. The code change required for S252 was diagnostic redaction/localization hardening plus central CLI error rendering enrollment.
