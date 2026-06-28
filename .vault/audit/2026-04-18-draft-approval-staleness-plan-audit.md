---
tags:
  - '#audit'
  - '#draft-approval-staleness'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-plan]]'
  - '[[2026-04-18-draft-approval-staleness-adr]]'
---

# `draft-approval-staleness` Code Review

PLAN-000 | info | No blocking findings in the implementation plan
The plan stays within issue #230 scope, targets the actual draft, CLI, and
submission surfaces present on the branch, and explicitly avoids assuming a
nonexistent export command. The main execution risk is protocol drift between
`src/aeat/adapters/outbound/aeat/export/_protocols.py` and the filing review helpers, so the
implementation should either align or remove duplicate status assumptions
instead of layering a second source of truth.
