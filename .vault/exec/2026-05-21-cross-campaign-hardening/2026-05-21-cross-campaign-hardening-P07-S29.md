---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P07.S29'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P07.S29`

Closed WCLI-5 and WCLI-6.

- Verified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_config/test_bucket_history_parsing.py`
- Verified: `src/aeat/entrypoints/cli/_ledger.py`
- Modified: `src/aeat/entrypoints/cli/test_invoice_link_error_disposition.py`
- Verified: `src/aeat/locales/ca.yml`
- Verified: `src/aeat/locales/en.yml`
- Verified: `src/aeat/locales/es.yml`
- Verified: `src/aeat/locales/hu.yml`

## Description

WCLI-5 was already implemented in the worktree: `_parse_bucket_event_types`
catches the failing token and raises the localized
`cli.config.bucket.history.invalid_event_type` refusal instead of raw
Python enum text. Added direct parser coverage proving typed values are
accepted and an unknown value names the bad token plus valid event values
without exposing `BucketEventType`.

WCLI-6 was already implemented in the worktree: the `ledger link`
`InvoiceLinkError` arm wraps the failure through the registered
invoice-link CLI message instead of `_bad(str(exc))`. Added focused
coverage for the helper so the CLI disposition remains the registered
message and does not leak the domain catalogue detail.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_config/test_bucket_history_parsing.py src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_invoice_link_error_disposition.py` passed.

`uv run pytest -q src/aeat/entrypoints/cli/_config/test_bucket_history_parsing.py src/aeat/entrypoints/cli/test_invoice_link_error_disposition.py` passed with 3 tests in 2.24s.

`uv run pytest -q src/aeat/entrypoints/cli/test_ledger_link_check_verbs.py src/aeat/entrypoints/cli/_config/test_repair_reset_state.py` passed with 9 tests in 5.16s.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S29` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/_ledger.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed.
