---
tags:
  - '#exec'
  - '#draft-approval-staleness'
date: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-plan]]'
---

# `draft-approval-staleness` `implementation` summary

Implemented persisted draft approval and deterministic stale detection for issue
#230.

- Modified: `src/aeat/filing/_schema.py`
- Modified: `src/aeat/filing/_validator.py`
- Created: `src/aeat/filing/_review.py`
- Created: `src/aeat/cli/review/__init__.py`
- Modified: `src/aeat/cli/filing/__init__.py`
- Modified: `src/aeat/cli/submission/_helpers.py`
- Modified: `src/aeat/submission/_preflight.py`

## Description

The implementation extends `FilingDraftStatus` with `APPROVED` and
`APPROVAL_STALE`, persists approval provenance directly on `FilingDraft`, and
computes a canonical approval basis from the draft payload, validation surface,
transaction catalogue, category profiles, and schema/formula provenance. New
review CLI commands approve, unapprove, inspect, and scan for stale drafts.
Existing filing and submission CLI surfaces now refresh persisted review state
when reading real filing drafts so stale approvals are surfaced and persisted
without manual JSON editing.

## Tests

Verified with targeted unit and CLI coverage:

- `uv run pytest src/aeat/filing/test_filing.py src/aeat/submission/test_preflight.py src/aeat/cli/review/test_review_cli.py src/aeat/cli/filing/test_filing_cli.py src/aeat/cli/submission/test_cli.py`
- `uv run pytest src/aeat/cli/test_smoke.py`

Related audit records: `2026-04-18-draft-approval-staleness-adr-audit`,
`2026-04-18-draft-approval-staleness-plan-audit`,
`2026-04-18-draft-approval-staleness-review`.
