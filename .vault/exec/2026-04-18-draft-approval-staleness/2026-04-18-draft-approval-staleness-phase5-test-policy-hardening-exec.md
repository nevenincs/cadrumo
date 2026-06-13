---
tags:
  - '#exec'
  - '#draft-approval-staleness'
date: '2026-04-20'
modified: '2026-04-20'
related:
  - '[[2026-04-18-draft-approval-staleness-plan]]'
---

# `draft-approval-staleness` `phase5` `test-policy-hardening`

Started the branch-wide hardening pass required to make the test surface match
the project's no-shortcuts policy instead of only proving #230 locally.

- Modified: `.vault/plan/2026-04-18-draft-approval-staleness-plan.md`
- Modified: `.vault/audit/2026-04-18-draft-approval-staleness-audit.md`
- Modified: `.vault/exec/2026-04-18-draft-approval-staleness/2026-04-18-draft-approval-staleness-implementation-summary-exec.md`
- Modified: `src/aeat/entrypoints/cli/browser/health.py`
- Modified: `src/aeat/entrypoints/cli/browser/test_health.py`
- Modified: `src/aeat/domain/schema/test_fetch.py`
- Modified: `src/aeat/domain/financial/invoices/_service.py`
- Modified: `src/aeat/domain/financial/invoices/test_reconciliation.py`
- Modified: `src/aeat/entrypoints/cli/submission/_helpers.py`
- Modified: `src/aeat/entrypoints/cli/submission/preflight.py`
- Modified: `src/aeat/entrypoints/cli/submission/dry_run.py`
- Modified: `src/aeat/entrypoints/cli/submission/__init__.py`

## Description

This step closed the last known non-env behaviour-patching tests by replacing
runtime patching with explicit production seams and real filesystem behaviour.
It also tightened the operator flow so submission surfaces accept draft ids
directly and refresh persisted review state before preflight or dry-run.

The accompanying audit pass then widened from the #230 seam to the broader
branch and catalogued the remaining policy violations. During the same phase the
browser unit tests were also rewritten to use real Playwright sessions and real
Chromium process lifecycle checks, eliminating the previous `Stub*` browser test
classes entirely. The remaining hard blockers are now the skip-gated
live/deferred tests rather than unit-test doubles.

## Tests

- `uv run ruff check src/aeat/entrypoints/cli/browser/health.py src/aeat/entrypoints/cli/browser/test_health.py src/aeat/domain/schema/test_fetch.py src/aeat/domain/financial/invoices/_service.py src/aeat/domain/financial/invoices/test_reconciliation.py src/aeat/entrypoints/cli/submission/_helpers.py src/aeat/entrypoints/cli/submission/preflight.py src/aeat/entrypoints/cli/submission/dry_run.py src/aeat/entrypoints/cli/submission/__init__.py`
- `uv run ty check src/aeat/entrypoints/cli/browser/health.py src/aeat/domain/financial/invoices/_service.py src/aeat/entrypoints/cli/submission/_helpers.py`
- `uv run pytest src/aeat/entrypoints/cli/browser/test_health.py src/aeat/domain/schema/test_fetch.py src/aeat/domain/financial/invoices/test_reconciliation.py`
- `uv run pytest src/aeat/entrypoints/cli/submission/test_cli.py src/aeat/adapters/outbound/aeat/export/test_preflight.py src/aeat/application/filing/test_filing.py src/aeat/entrypoints/cli/filing/test_filing_cli.py src/aeat/entrypoints/cli/review/test_review_cli.py`
- `uv run python -m playwright install chromium`
- `uv run pytest src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_evasion.py`
- `uv run pytest src/aeat/domain/schema/test_cli.py src/aeat/domain/schema/test_boe_extractor.py`
- `uv run ruff check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_evasion.py src/aeat/domain/schema/test_cli.py src/aeat/domain/schema/test_boe_extractor.py`

Related audit state is recorded in `2026-04-18-draft-approval-staleness-audit`.
