---
tags:
  - '#exec'
  - '#draft-approval-staleness'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-plan]]'
---

# `draft-approval-staleness` `implementation` summary

Implemented persisted draft approval and deterministic stale detection for issue
#230.

- Modified: `src/aeat/application/filing/_schema.py`
- Modified: `src/aeat/application/filing/_validator.py`
- Created: `src/aeat/application/filing/_review.py`
- Created: `src/aeat/entrypoints/cli/review/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`

## Description

The implementation extends `FilingDraftStatus` with `APPROVED` and
`APPROVAL_STALE`, persists approval provenance directly on `FilingDraft`, and
computes a canonical approval basis from the draft payload, validation surface,
transaction catalogue, category profiles, and schema/formula provenance. New
review CLI commands approve, unapprove, inspect, and scan for stale drafts.
Existing filing CLI surfaces now refresh persisted review state when reading
real filing drafts so stale approvals are surfaced and persisted without manual
JSON editing. The review-domain implementation is intentionally isolated from
the submission package because no live write mechanism is allowed on this
surface. Follow-up manual verification also closed a Windows console encoding
regression in the filing success output and added explicit next-step guidance so
the CLI tells operators when to `review show`, `review approve`, `submission
preflight`, and `submission dry-run`. A further compliance pass removed the last
non-env `monkeypatch`/behavior-patching tests, replaced one host-dependent unit
`pytest.skip(...)` with a real assertion, and taught `aeat submission
preflight|dry-run` to accept `draft_id` directly so the operator can stay on
the filing/review identifier model end to end.

## Tests

Verified with targeted unit and CLI coverage:

- `uv run pytest src/aeat/application/filing/test_filing.py src/aeat/entrypoints/cli/review/test_review_cli.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/adapters/outbound/aeat/export/test_preflight.py src/aeat/entrypoints/cli/submission/test_cli.py`
- `uv run pytest src/aeat/application/filing/test_filing.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/review/test_review_cli.py src/aeat/entrypoints/cli/submission/test_cli.py src/aeat/adapters/outbound/aeat/export/test_preflight.py src/aeat/application/workflow/test_engine.py src/aeat/entrypoints/cli/workflow/test_cli.py src/aeat/entrypoints/cli/workflow/test_cli_runtime.py src/aeat/adapters/outbound/aeat/export/test_engine.py src/aeat/adapters/outbound/aeat/export/test_live_submission.py src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py src/aeat/adapters/outbound/aeat/export/test_safety_helpers.py`
- `uv run ruff check src/aeat/entrypoints/cli/filing/__init__.py src/aeat/entrypoints/cli/review/__init__.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/review/test_review_cli.py`
- `uv run pytest src/aeat/entrypoints/cli/browser/test_health.py src/aeat/domain/schema/test_fetch.py src/aeat/domain/financial/invoices/test_reconciliation.py`
- `uv run pytest src/aeat/entrypoints/cli/submission/test_cli.py src/aeat/adapters/outbound/aeat/export/test_preflight.py src/aeat/application/filing/test_filing.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/review/test_review_cli.py`
- `uv run ruff check src/aeat/entrypoints/cli/browser/health.py src/aeat/entrypoints/cli/browser/test_health.py src/aeat/domain/schema/test_fetch.py src/aeat/domain/financial/invoices/_service.py src/aeat/domain/financial/invoices/test_reconciliation.py src/aeat/entrypoints/cli/submission/_helpers.py src/aeat/entrypoints/cli/submission/preflight.py src/aeat/entrypoints/cli/submission/dry_run.py src/aeat/entrypoints/cli/submission/__init__.py`
- `uv run ty check src/aeat/entrypoints/cli/browser/health.py src/aeat/domain/financial/invoices/_service.py src/aeat/entrypoints/cli/submission/_helpers.py`
- Manual CLI flow covering `aeat filing build` -> `aeat review approve` -> `aeat filing validate` -> transaction-catalogue drift -> `aeat review show` -> `aeat review stale` -> `aeat submission preflight`

Related audit records: `2026-04-18-draft-approval-staleness-adr-audit`,
`2026-04-18-draft-approval-staleness-plan-audit`,
`2026-04-18-draft-approval-staleness-review`.
