---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]'
---

# `cli-workflow-redesign-W61-P305-S1825` Code Review

Reviewer: `vaultspec-code-reviewer` persona.

Status: PASS after re-review.

Scope reviewed: manual transaction creation under `aeat app ledger` as a thin CLI adapter over the existing active-bucket ledger backend. Files reviewed: `src/aeat/entrypoints/cli/_ledger.py`, `src/aeat/entrypoints/cli/test_cli_surface.py`, `src/aeat/locales/en.yml`, `src/aeat/locales/es.yml`, `src/aeat/locales/ca.yml`, `src/aeat/locales/hu.yml`.

Verification: `.\.venv\Scripts\python.exe -m pytest src/aeat/entrypoints/cli/test_cli_surface.py -q` passed with 12 tests. `uv run pytest src/aeat/entrypoints/cli/test_cli_surface.py -q` could not start because `.venv\Scripts\aeat.exe` was locked by another process.

S1825-001 | HIGH | Public `app ledger edit` remains as a refusal placeholder before the planned edit lifecycle step

`src/aeat/entrypoints/cli/_ledger.py:475` still registers `aeat app ledger edit`, while `src/aeat/entrypoints/cli/_ledger.py:497` unconditionally raises `typer.BadParameter` with the hard-coded message "ledger review annotations cannot store ledger mutations; use backend ledger mutation services" after parsing legacy review-overlay options. The locale help still advertises the command as manual ledger editing at `src/aeat/locales/en.yml:285`, `src/aeat/locales/es.yml:317`, `src/aeat/locales/ca.yml:310`, and `src/aeat/locales/hu.yml:306`, and `src/aeat/entrypoints/cli/test_cli_surface.py:276` locks the refusal behavior in.

This violates the S1825 scope and the ADR prohibition on compatibility, deprecation, shim, and placeholder command surfaces. `W61.P305.S1825` is only the manual transaction creation exposure; edit/classify/allocate is explicitly deferred to `W61.P305.S1827`. Keeping a public edit command that cannot perform the advertised operation is a stub surface, and the hard-coded message points users at "backend ledger mutation services" rather than a canonical operator command. Remove the public edit command until the S1827 backend-backed adapter lands, or implement it in S1827 as a thin adapter over the centralized backend mutation service with localized help and error text.

S1825-R001 | RESOLVED | Previous HIGH finding cleared on re-review

Re-review date: 2026-05-14.

The public `aeat app ledger edit` placeholder has been removed from `src/aeat/entrypoints/cli/_ledger.py`, along with the CLI-only edit parsing helpers and stale review-overlay imports. The CLI surface test now asserts that `app ledger edit` is not registered, and the stale `cli.ledger.edit`, `edit_requires_one`, `invalid_skip`, split, match, and set-parse locale/error keys were removed from the English, Spanish, Catalan, and Hungarian locale files.

Fresh scans returned no matches for `app ledger edit`, `ledger edit`, `cli.ledger.edit`, `edit_requires_one`, `invalid_skip`, `invalid_split_format`, `invalid_split_value`, `set_parse_error`, or `match_both_required` under `src/aeat/entrypoints/cli` and `src/aeat/locales`; no `@app.command("edit"` registration remains in `src/aeat/entrypoints/cli/_ledger.py`.

The remaining S1825 create path is still a thin transport adapter: it parses CLI date/decimal transport values, resolves the active bucket transaction repository, constructs `ManualLedgerTransactionCommand`, delegates mutation to `create_manual_transaction`, and emits the backend result. Backend validation, active-bucket persistence, event emission, evidence validation, usage-ratio policy, direction/sign policy, and AeatError-compatible transaction errors remain owned by the application/domain services.

Verification: `.\.venv\Scripts\ruff.exe check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py` passed; `.\.venv\Scripts\ty.exe check src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py` passed; `.\.venv\Scripts\python.exe -m pytest src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/application/ledger/test_actions.py -q` passed with 46 tests; locale YAML parsing for `en.yml`, `es.yml`, `ca.yml`, and `hu.yml` passed.

Re-review status: PASS. No remaining blocker found for `W61.P305.S1825`.
