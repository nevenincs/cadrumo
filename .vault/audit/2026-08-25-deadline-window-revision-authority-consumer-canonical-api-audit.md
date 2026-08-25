---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fc1ad22b55c90366b2e7b1e18895a9ce7d0f4d91220907b34695c3480f5c341f'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Audit canonical deadline API consumption across application surfaces

## Scope

- Overview calendar, agenda, backlog, explain, workflow deadline gates, and filing-window posture.
- Semantic discovery with Vaultspec RAG followed by exact-symbol confirmation.
- Distinction between legal-obligation multiplicity and observational evidence reconciliation.

## Findings

### consumer-canonical-api | high | workflow exact-target lookup masked duplicate obligations

`resolve_deadline_stage_obligation` selected `matches[0]`, allowing an invalid canonical schedule with duplicate modelo-period obligations to reach workflow as one row. Commit `73346a8654` routes exact target narrowing through `_target_obligation_from_schedule`, which raises `ScheduleComputationError` when more than one canonical row matches.

### consumer-canonical-api | resolved | observational event dedupe is not obligation dedupe

`_calendar_evidence.py` reconciles duplicate local/live evidence for the same filing event after legal obligations have already been produced by `DeadlineEngine`. It does not collapse `Schedule.obligations` and is retained.

### consumer-canonical-api | resolved | all application deadline projections consume canonical domain APIs

Vaultspec RAG and exact confirmation found overview calendar/agenda/backlog consuming `DeadlineEngine`, work posture consuming `resolve_filing_closes_on`, qualified M210 notices consuming `resolve_filing_window`, and explain/workflow consuming schedules. No application-local revision selector, qualifier matcher, cadence generator, deadline catalogue, or period parser remains.

## Recommendations

- Keep multiplicity-sensitive regressions at workflow and overview boundaries.
- Treat evidence reconciliation separately from legal obligation identity in future audits.
