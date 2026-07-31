---
tags:
  - '#adr'
  - '#audit-concerns-2026-05'
date: '2026-05-08'
modified: '2026-07-10'
body_hash: 'sha256:93725c07965f87fde14312032534d816ba0c51c90f18b9d80d657ca2f457a32e'
related:
  - '[[2026-05-08-audit-concerns-2026-05-plan]]'
  - '[[2026-05-08-renta-cuota-integra-state-scale-adr]]'
  - '[[2026-05-08-renta-cuota-integra-autonomic-scale-adr]]'
  - '[[2026-04-16-live-write-test-audit-research]]'
  - '[[2026-06-04-audit-concerns-2026-05-research]]'
---

# `audit-concerns-2026-05` adr | (**status:** `accepted`)

## Context

An external `aeat-audit` run surfaced four cross-cutting concerns that
did not collapse onto one underlying change. The branch needs an in-repo
decision record that explains why these findings are resolved as separate,
re-auditable slices instead of one blended remediation batch.

## Decision

- Mirror the external audit concerns inside this vault as independent
  execution slices with explicit acceptance gates.
- Prioritize concerns by deliverability and measurable re-audit outcome,
  not by forcing an artificial shared dependency graph.
- Keep resolved concerns linked to the concrete follow-on ADRs and plans
  that closed them.

## Consequences

- Audit remediation remains traceable to the external findings that
  motivated it.
- Unrelated concern streams can land independently without hidden coupling.
- Re-audits have a clear baseline for judging whether each concern is
  actually closed.
