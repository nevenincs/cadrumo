---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:324bf77845bb2d6c4e2da34d8b93d2129fd320d55dcd6f990fb72c3205b07f3c'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# `deadline-window-revision-authority` audit: `consumer canonical API`

## Scope

- Overview calendar, agenda, backlog, explain, workflow deadline gates, and filing-window posture.
- Semantic discovery with Vaultspec RAG followed by exact-symbol confirmation.
- Distinction between legal-obligation multiplicity and observational evidence reconciliation.

## Findings

### workflow-first-match-mask | high | workflow exact-target lookup masked duplicate obligations

`resolve_deadline_stage_obligation` selected `matches[0]`, allowing an invalid canonical schedule with duplicate modelo-period obligations to reach workflow as one row. Commit `73346a8654` routes exact target narrowing through `_target_obligation_from_schedule`, which raises `ScheduleComputationError` when more than one canonical row matches. This finding is resolved.

### evidence-dedupe-boundary | low | observational event dedupe does not alter obligation multiplicity

`_calendar_evidence.py` reconciles duplicate local/live evidence for the same filing event after legal obligations have already been produced by `DeadlineEngine`. It does not collapse `Schedule.obligations` and is retained.

### canonical-consumer-chain | low | application deadline projections use canonical domain APIs

Vaultspec RAG and exact confirmation found overview calendar/agenda/backlog consuming `DeadlineEngine`, work posture consuming `resolve_filing_closes_on`, qualified M210 notices consuming `resolve_filing_window`, and explain/workflow consuming schedules. No application-local revision selector, qualifier matcher, cadence generator, deadline catalogue, or period parser remains.

## Recommendations

- Keep multiplicity-sensitive regressions at workflow and overview boundaries.
- Treat evidence reconciliation separately from legal obligation identity in future audits.
