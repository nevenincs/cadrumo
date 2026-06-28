---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W61.P305.S1830'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-14-cli-workflow-redesign-w61-p305-s1830-code-review-audit]]"
  - "[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-output-rendering-normalization-adr]]"
  - "[[2026-05-08-cli-backend-boundary-adr]]"
---

# `cli-workflow-redesign` `W61.P305.S1830`

Closed plan rows:

- `W61.P305.S1830`

## Description

Validated the manual ledger command vocabulary help text and backend-boundary inventory for `aeat app ledger`.

The boundary tests now derive the active ledger command set from `_ledger.app.registered_commands`, so accepted lifecycle names are checked against live Typer registration instead of loose help-text substrings. The accepted registered commands are `allocate`, `archive`, `attach`, `classify`, `create`, `edit`, `export`, `import`, `list`, `read`, `remove`, `reset`, `review`, `stash`, `status`, and `track`.

Generated Click help is rendered for the ledger group and every nested ledger command. The help guard rejects legacy vocabulary including `set-ratio`, `unset-ratio`, `split`, `sanitize`, and `financial` across the generated help surface.

Ledger export serialization remains named `--export-format`. Root `--format` remains the command-output rendering switch through `_emit`; the guard proves this with a real `aeat --format json app ledger import ... --dry-run` invocation and JSON payload parse.

Review filter help is tied to the backend-owned `LedgerReviewFilterKey` enum from `src/aeat/application/review/_filter.py`, so backend filter catalogue changes require corresponding visible operator help.

The backend ownership guard verifies provider detection, source hashing, direction resolution, and review-row status logic stay out of the CLI while `import_ledger_source`, `_direction_from_amount`, `query_ledger_review_rows`, and `LedgerReviewQuery` remain anchored in `src/aeat/application/ledger/_actions.py`.

## Modified Paths

- `src/aeat/entrypoints/cli/test_backend_boundary.py`
- `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1830-code-review-audit.md`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

- `uv run --no-sync ruff check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`
  - All checks passed
- `uv run --no-sync ty check src/aeat/application/ledger src/aeat/domain/buckets src/aeat/entrypoints/cli/_ledger.py src/aeat/entrypoints/cli/test_backend_boundary.py`
  - All checks passed
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py -q`
  - 11 passed
- `uv run --no-sync pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_backend_boundary.py -q`
  - 87 passed
- `uv run --no-sync python -m aeat.locales audit`
  - `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` passed

Coverage includes live Typer command registration, generated ledger help across nested commands, export artifact format naming, root `_emit` rendering through a real CLI path, backend-owned review filter key exposure, and the manual ledger import/review backend-boundary inventory.

## Review

Formal review recorded S1830-001 through S1830-003 in `.vault/audit/2026-05-14-cli-workflow-redesign-W61-P305-S1830-code-review-audit.md`.

The remediation replaced substring-only command checks with live command registry assertions, scanned generated nested command help for rejected vocabulary, added a real root `--format json` dry-run import check, and derived review help expectations from `LedgerReviewFilterKey`.

Final re-review appended `S1830-REREVIEW-001 | INFO | Formal post-remediation re-review found no remaining findings` to the audit log.

## Outcome

`W61.P305.S1830` is complete. The manual ledger command vocabulary and boundary inventory now enforce the accepted CLI surface, reject legacy wording in generated help, preserve root output rendering semantics, and keep ledger import/review behavior owned by backend services instead of CLI handlers.
