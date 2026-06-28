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
  - '[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]'
  - '[[2026-05-08-cli-backend-boundary-adr]]'
---

# `cli-workflow-redesign` Code Review

S1830-001 | MEDIUM | Ledger lifecycle help test does not prove command inventory or rejected nested vocabulary
`src/aeat/entrypoints/cli/test_backend_boundary.py` checks accepted lifecycle names with substring searches against `aeat app ledger --help`. That can pass when a command name appears only in descriptive text, and it does not prove the Typer command is registered or invokable. The rejected-name checks are also scoped only to the ledger group help, so a regression that reintroduces legacy vocabulary such as `--split` on `aeat app ledger edit --help` or another nested ledger help surface would not be caught. This leaves the S1830 vocabulary guard weaker than the stated requirement to cover accepted lifecycle names plus rejected legacy names.

S1830-002 | MEDIUM | Export help test does not prove root `--format` remains rendering-only
`src/aeat/entrypoints/cli/test_backend_boundary.py` asserts that `aeat app ledger export --help` contains `--export-format` and does not contain `--format`. That proves the subcommand help avoids a local `--format` spelling, but it does not prove the root `--format` option is still available for `_emit` rendering or that it remains independent from artifact serialization. A regression that removes root output formatting for ledger export, or lets root `--format` affect the exported artifact format, could still pass this test.

S1830-003 | LOW | Backend-owned review filter help keys are hardcoded rather than tied to the backend catalogue
`src/aeat/entrypoints/cli/test_backend_boundary.py` checks for the literal strings `status`, `period`, `issue`, and `import` in `aeat app ledger review --help`. Those are the current backend-owned keys, but the test will not fail when `LedgerReviewFilterKey` gains a new backend key and help is not updated. Since S1830 is specifically guarding that all backend-owned filter keys remain visible, the assertion should derive the expected key set from the backend enum or another single source of truth.

S1830-VERIFY-001 | INFO | Targeted review verification completed
Reviewed the S1830 boundary test changes against the W61.P305.S1830 plan row and the requested manual-ledger, ledger transaction, ratios, output-rendering, and CLI-backend-boundary ADRs. The boundary inventory no longer tracks the resolved ledger import helper as a live CLI violation, and the scoped test slice passes. Verification command: `uv run pytest src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`9 passed`).

S1830-REMEDIATION-001 | INFO | Remediated S1830-001 command inventory and nested vocabulary guard
`src/aeat/entrypoints/cli/test_backend_boundary.py` now derives the active ledger command set from `_ledger.app.registered_commands`, asserts the accepted lifecycle verbs are actually registered, and asserts rejected legacy command names are absent from the registered command set. A second guard renders the generated Click help for the ledger group and every nested ledger command, then scans each generated help surface for rejected legacy vocabulary.

S1830-REMEDIATION-002 | INFO | Remediated S1830-002 root rendering format guard
The export help guard now verifies the artifact option remains `--export-format`. A separate real dry-run import invokes `aeat --format json app ledger import ... --dry-run` against a temporary CSV source and parses the emitted JSON payload, proving root `--format` still controls `_emit` rendering independently of export artifact serialization.

S1830-REMEDIATION-003 | INFO | Remediated S1830-003 review filter catalogue drift
The review help guard now derives the expected keys from `LedgerReviewFilterKey` instead of duplicating the literals in the test, so backend-owned filter-key additions fail unless ledger review help exposes the new key.

S1830-VERIFY-002 | INFO | Post-remediation verification completed
Commands passed: `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`; `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py`; `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`87 passed`); `uv run --no-sync python -m aeat.locales audit` (`ca/en/es/hu ok`).

S1830-REREVIEW-001 | INFO | Formal post-remediation re-review found no remaining findings
Re-reviewed the S1830 remediation against the scoped test, audit, implementation files, W61.P305.S1830 plan row, and the requested ledger/output/backend-boundary ADRs. S1830-001 is covered by actual ledger Typer command registration plus generated Click help scans for the ledger group and every nested ledger command. S1830-002 is covered by `--export-format` help validation plus a real root `--format json` CLI invocation that exercises `_emit` and parses the emitted payload. S1830-003 is covered by deriving expected review filter keys from `LedgerReviewFilterKey`. The scoped tests do not introduce fake, stub, mock, monkeypatch, skip, or xfail shortcuts, and the remediation entries above accurately describe the implemented guards. Verification commands passed during re-review: `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`; `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py`; `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`11 passed`); `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q` (`87 passed`); `uv run --no-sync python -m aeat.locales audit` (`ca/en/es/hu ok`).
