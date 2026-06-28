---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
  - '[[2026-05-08-cli-backend-boundary-adr]]'
---

# `cli-workflow-redesign` Code Review

S1829-001 | MEDIUM | `aeat app ledger review` still owns filtering and review row projection
`src/aeat/entrypoints/cli/_ledger.py` parses `LedgerReviewFilterSpec`, loads all transactions with `list_manual_transactions`, filters `period` and `status` in the CLI, and manually shapes review rows instead of delegating the review query/projection to the ledger backend. This keeps business/read-model behavior in the entrypoint boundary and has visible drift: `period=2026-Q1` is reduced to `canonical[:4]`, so every 2026 row matches regardless of quarter or month, while supported filter behavior is not covered by the CLI real-behavior tests. The same command emits `id` / `status` shaped rows instead of the centralized `ledger_transaction_review_payload` schema used by `ledger list`, creating two JSON contracts for the same ledger review concept.

S1829-002 | MEDIUM | Ledger export reuses command-local `--format` despite root output format ownership
`src/aeat/entrypoints/cli/_ledger.py` registers `aeat app ledger export --format` for export serialization while the redesign ADR says root `--format json|text` is the only output format selector. The focused CLI test has to invoke two different `--format` flags in one command line, one before `app` for `_emit` output and one under `export` for file serialization. Even though the command result itself goes through `_emit`, this preserves a command-local format flag in the retained surface and risks confusing output rendering with export serialization. Rename or move the serialization selector behind a backend-owned command field with a non-rendering option name, for example `--export-format`.

S1829-VERIFY-001 | INFO | Focused verification passed with existing venv Python
Reviewed the S1829 scope against the W61.P305.S1829 plan row and the three CLI backend/output/manual-ledger ADRs. No residual CLI-owned provider resolution was found: provider detection, validation, ingestion, source verification, direction resolution, and source import persistence live in `src/aeat/application/ledger/_actions.py`. Manual ledger mutations use Pydantic backend commands/results, real SQL-backed tests cover service behavior, legacy ratio aliases are not registered, and scoped CLI emissions route through `_emit`. `uv run pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py` could not start because Windows reported `.venv\Scripts\aeat.exe` locked by another process. Retried with `.venv\Scripts\python.exe -m pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py`; result: 53 passed.

## Remediation

S1829-001 remediation added application-owned `LedgerReviewQuery`, `LedgerReviewRow`, `LedgerReviewQueryResult`, and `query_ledger_review_rows`. `aeat app ledger review` now delegates filtering and row projection to that backend service, including exact period-prefix filtering such as `2026-05`.

S1829-002 remediation renamed the ledger export artifact selector from command-local `--format` to `--export-format`, leaving root `--format` reserved for output rendering.

Additional S1829 hardening moved import provider selection, provider validation, source-file hashing, and source import result construction into `import_ledger_source` with `LedgerSourceImportCommand` and `LedgerSourceImportResult`. The CLI now binds options, calls the application service, and renders through `_emit`.

Final verification after remediation:
- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py`
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_cli_surface.py`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/usage_ratios/test_model.py src/aeat/domain/usage_ratios/test_service.py -q` (`88 passed`)
- `uv run --no-sync python -m aeat.locales audit`

S1829-003 | MEDIUM | `ledger review` accepts quarter periods that the backend query cannot match
`src/aeat/application/review/_filter.py` continues to accept documented ledger review period filters such as `period=2026-Q1`, and `src/aeat/entrypoints/cli/_ledger.py` canonicalizes them to `2026Q1` before constructing `LedgerReviewQuery`. The backend-owned query in `src/aeat/application/ledger/_actions.py` filters by checking whether an ISO transaction date starts with the query period, so no transaction date can match a quarter token such as `2026Q1`. The remediation test only covers `2026-05`, leaving the supported quarter filter path broken at the new backend boundary.

S1829-004 | MEDIUM | `ledger review` still accepts advertised filters that are silently dropped before the backend query
`src/aeat/application/review/_filter.py` parses `issue=` and `import=` ledger review filters, and the locale help still advertises `status`, `period`, `issue`, and `import`. `src/aeat/entrypoints/cli/_ledger.py` only forwards `period` and `status` into `LedgerReviewQuery`; `issue` and `import_id` are ignored, and `src/aeat/application/ledger/_models.py` has no backend query fields for them. This means accepted operator filters become no-ops rather than backend-owned validation/filter semantics, and no CLI behavior test covers the advertised keys.

S1829-VERIFY-002 | INFO | Targeted remediation re-review completed with remaining findings
Reviewed the S1829 scoped files against the W61.P305.S1829 plan row and the manual-ledger, output-rendering, and CLI-backend-boundary ADRs. Provider detection, provider validation, source hashing, source import persistence, and export serialization now live behind application services; `aeat app ledger export` uses `--export-format` for artifact serialization while root `--format` remains output rendering only; no command-local `--json` or legacy ledger ratio aliases were found in the scoped ledger CLI. Verification commands run: `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py -q` (`54 passed`) and `uv run --no-sync python -m aeat.locales audit` (`ca.yml`, `en.yml`, `es.yml`, `hu.yml` ok).

## Second Remediation

S1829-003 remediation replaced review period prefix matching with the centralized aggregation `Period` parser, so `YYYY`, `YYYY-MM`, `YYYYQn`, and `YYYY-Qn` review filters use inclusive date bounds in the backend query.

S1829-004 remediation made advertised `issue=` and `import=` filters backend-owned. Ledger source imports now produce an import batch id, emit persisted bucket events for import diagnostics, and `query_ledger_review_rows` filters rows by import batch and diagnostic kind through bucket event history. File-level diagnostics such as `gap` are recorded against the batch transaction ids so review filters return inspectable ledger rows. The CLI only forwards the typed filter fields into `LedgerReviewQuery`.

The boundary inventory was updated so CLI-002 points at the live backend-owned ledger import service symbols rather than the removed CLI helper.

Verification after second remediation:
- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`80 passed`)
- `uv run --no-sync python -m aeat.locales audit`

The broader `uv run --no-sync ruff check src/aeat/application/review ...` command still reports the pre-existing `N813` alias in `src/aeat/application/review/_models.py`; that file is outside the S1829 implementation and was not changed by this remediation.

## Third Remediation

S1829-005 remediation changed `query_ledger_review_rows` so `transaction_id` is an intersection filter rather than an override. The backend still validates the requested transaction id exists in the bucket, then applies the already parsed `period`, `status`, `issue`, and `import` filters before returning the single-row projection. A regression test asserts that a mismatched period plus `transaction_id` returns no rows.

Verification after third remediation:
- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`80 passed`)

S1829-005 | MEDIUM | `ledger review --id` still makes accepted review filters inert
`src/aeat/entrypoints/cli/_ledger.py` accepts `--id` together with `--filter`, forwards `period`, `status`, `issue`, and `import` into `LedgerReviewQuery`, and renders the resulting single-row payload as filtered review output. The backend query in `src/aeat/application/ledger/_actions.py` applies period/status/import/issue filtering first, but then replaces the filtered row set with `_require_transaction(...)` whenever `transaction_id` is present. As a result, `aeat app ledger review --id <tx> --filter issue=duplicate --filter import=<batch>` returns the row by id even when the persisted bucket event history would not match those filters. This leaves advertised review filters accepted but ineffective in single-row review mode. Either reject `--id` plus filters at the boundary or make the backend transaction-id predicate intersect with the other filters.

S1829-VERIFY-003 | INFO | Final targeted remediation review completed with one remaining finding
Reviewed the latest worktree state for the S1829-scoped files after the second remediation and the additional diagnostic tightening. Quarter and year review filters now route through backend `Period` semantics, monthly filters still use exact month bounds, and file-level import diagnostics such as `gap` are now persisted as transaction-scoped `LEDGER_IMPORT_DIAGNOSTIC_RECORDED` events carrying the `import_batch_id` payload. Provider detection, validation, source hashing, and import persistence remain application-owned; `aeat app ledger export` uses `--export-format` for artifact serialization while command output still uses root `--format`; scoped locale help advertises the current filter and export vocabulary. Verification commands run: `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`80 passed`) and `uv run --no-sync python -m aeat.locales audit` (`ca.yml`, `en.yml`, `es.yml`, `hu.yml` ok).

S1829-006 | MEDIUM | `ledger review --id` empty filtered results can raise an index error
`query_ledger_review_rows` now correctly treats `transaction_id` as an intersection with `period`, `status`, `issue`, and `import`, which means a single-row review query can legitimately return zero rows. `src/aeat/entrypoints/cli/_ledger.py` still indexes `result.rows[0]` whenever `--id` is supplied, so a filtered-out id result can raise `IndexError` instead of rendering an empty review result.

## Fourth Remediation

S1829-006 remediation updated the `aeat app ledger review --id` branch to render an empty filtered result through `_emit` when the backend returns zero rows. A CLI regression now invokes `review --id <transaction> --filter period=2026-06` against a May transaction and asserts a JSON payload with empty `rows` and the applied filters.

Verification after fourth remediation:
- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py`
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`80 passed`)
- `uv run --no-sync python -m aeat.locales audit`
S1829-006 | MEDIUM | `ledger review --id` crashes when intersection filters exclude the requested row
`query_ledger_review_rows` now correctly treats `transaction_id` as an intersection with `period`, `status`, `issue`, and `import` filters, and `src/aeat/application/ledger/test_actions.py` covers mismatched `period + transaction_id` returning no rows. The CLI single-row branch in `src/aeat/entrypoints/cli/_ledger.py` still assumes `result.rows[0]` exists whenever `--id` is supplied, so a valid filtered-out single-row review can raise an unexpected `IndexError` instead of rendering the same empty/no-match semantics or a typed boundary error.

S1829-REVIEW-004 | INFO | Final S1829 remediation review clean
