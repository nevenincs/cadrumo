---
tags:
  - '#audit'
  - '#draft-approval-staleness'
date: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-plan]]'
  - '[[2026-04-18-draft-approval-staleness-adr]]'
---

# `draft-approval-staleness` Code Review

REVIEW-000 | info | No blocking findings in the implemented diff
The shipped change set now carries explicit `APPROVED` and
`APPROVAL_STALE` statuses on `FilingDraft`, persists approval provenance on the
draft record, recomputes deterministic approval-basis fingerprints against the
current transaction/category/schema context, and exercises those transitions
through filing, review, and submission boundary tests.

REVIEW-001 | low | Export gating remains a downstream integration point
Issue #230 references refusal in `aeat submission export`, but the export
surface from issue #201 is not present on this branch. The current change set
establishes the status contract and stale-detection machinery that export must
consume, but the explicit export refusal path cannot be wired until that command
exists.
