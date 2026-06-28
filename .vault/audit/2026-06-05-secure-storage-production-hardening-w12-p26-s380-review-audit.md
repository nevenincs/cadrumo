---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S380]]'
---

# `secure-storage-production-hardening` `W12.P26.S380` Review

## S380-001 | FIXED | Plan row referenced retired profile census path

`AFR-278` and `W12.P26.S380` still named `_profile_census.py`, but the live command
surface is `_profile_censo.py` after the Spanish-domain rename. The plan now tracks the
current file and closes the register entry against the implementation that exists.

## S380-002 | PASS | Active profile resolution stays centralized

`_profile_censo.py` resolves the active profile through `resolve_active_bucket_id()`,
then validates the bucket manifest through `read_profile_bucket_by_id()`. Missing
active-profile or missing-manifest cases raise `CliRefusedBoundaryError` with the
existing localized `cli.config.errors.no_active_profile` message key.

## S380-003 | FIXED | Censo event writes used ambient active-bucket repository construction

`_emit_censo_event()` received a resolved `bucket_id` but constructed
`BucketEventHistoryRepository()` through its default active-bucket factory. The code now
passes `secure_object_repository_for_bucket(bucket_id)` into the event repository so the
event catalogue is explicitly bound to the same bucket used in the censo command flow.

## S380-004 | PASS | Censo persistence remains application-owned

The CLI delegates snapshot capture, profile comparison, and profile application to
`CensoSyncService`. Snapshot persistence uses the live censo secure-object namespace,
profile record writes use the user-profile lifecycle repository, and the CLI does not
parse bucket manifests beyond pointer verification or reimplement censo modelo
foundation decisions.

## S380-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/_config/_profile_censo_payloads.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py` passed.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py` passed with 11 tests.
- `uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S380 slice.

Disposition: close `AFR-278` as `bootstrap-custody`.
