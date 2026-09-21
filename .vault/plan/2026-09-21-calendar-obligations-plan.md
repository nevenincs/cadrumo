---
tags:
  - '#plan'
  - '#calendar-obligations'
date: '2026-09-21'
tier: L2
related:
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
  - '[[2026-06-05-calendar-live-operational-hardening-adr]]'
  - '[[2026-06-05-live-censo-calendar-reconciliation-adr]]'
  - '[[2026-09-17-filing-chain-reconciliation-adr]]'
modified: '2026-09-21'
body_schema: body-v2
body_hash: 'sha256:eff69a232cd869ae328bca1b098c3d735c0307998f28d656faf9da56064cec0f'
---

# `calendar-obligations` plan

Make calendar, agenda, backlog, CLI, TUI and filing-evidence review answer the next, due, overdue, filed and unresolved-obligation questions from one explicit evaluation context.

## Description

Approved 2026-09-21 by the operator's instruction to read CALENDAR-01 revision 0.1 and action its plan.

Implement the bounded offline outcomes in CALENDAR-01 using session-policy revision 1.6 and ACCEPTANCE-01 revision 1.5. Phase P01 is governed by the accepted calendar integration, filing-semantics and live-censo reconciliation decisions: preserve the canonical deadline authority, one explicit evaluation context, provenance and uncertainty while correcting demonstrated date and lifecycle defects. Phase P02 is governed by the accepted filing-chain reconciliation and operational-hardening decisions: preserve separate local, AEAT and receipt axes, reuse the existing reconciler and keep calendar review local-only. Phase P03 projects those shared contracts into the existing CLI and TUI without cross-entrypoint imports or frontend deadline arithmetic.

No new costly decision is required. The accepted decisions already settle ownership, evidence meaning, local-only overview behavior and reconciliation. Unsupported notification association or prospective monetary assessment remains explicit rather than being invented in this plan. Live AEAT access, environment setup, authentication, notification content opening, acknowledgement, response and filing submission are excluded.

## Steps

### Phase `P01` - effective dates and obligation identity

Prove and correct one effective deadline, evaluation date, authority provenance and lifecycle contract before adding presentation fields.

- [x] `P01.S01` - Align effective-deadline status, recovery and overdue duration across calendar and agenda with explicit shift uncertainty; `src/cadrumo/domain/deadlines/engine.py, src/cadrumo/application/overview/calendar_models.py, src/cadrumo/application/overview/calendar.py, src/cadrumo/application/overview/agenda.py and owning tests`.
- [ ] `P01.S02` - Thread the evaluation date through historical applicability and special-regime resolution; `src/cadrumo/application/overview/calendar.py, src/cadrumo/domain/calculations/registry/applicability.py and owning tests`.
- [ ] `P01.S03` - Preserve final-period and annual residual obligations across cessation boundaries; `src/cadrumo/domain/deadlines/engine.py and src/cadrumo/domain/deadlines/tests`.

### Phase `P02` - filing evidence and recovery

Expose existing evidence strength, query coverage, reconciliation and safe recovery semantics without adding live reads or a second reconciliation owner.

- [ ] `P02.S04` - Expose filing evidence grade, query coverage, freshness and recovery actions without collapsing local, AEAT or receipt state; `src/cadrumo/application/overview/calendar_models.py, src/cadrumo/application/overview/calendar_evidence.py, src/cadrumo/application/modelo/declarations_calendar.py and owning tests`.
- [ ] `P02.S05` - Keep ungrounded notifications explicitly unlinked and incapable of proving filing or response deadlines; `src/cadrumo/application/overview/calendar.py, src/cadrumo/application/overview/calendar_models.py and owning tests`.
- [ ] `P02.S06` - Project the existing conditional surcharge guidance without assessing liability or conflating sanction amounts; `src/cadrumo/application/modelo/declarations_calendar.py, src/cadrumo/application/modelo/work_plazo.py and owning tests`.

### Phase `P03` - CLI and TUI task completion

Project the settled calendar and evidence contracts into independent CLI and TUI surfaces, then prove parity with synthetic acceptance journeys.

- [ ] `P03.S07` - Render typed scope, as-of context, payment cutoff, overdue age, evidence notices and recovery actions in CLI output; `src/cadrumo/entrypoints/cli/_overview_payloads.py, src/cadrumo/entrypoints/cli/_overview_rendering.py and owning tests`.
- [ ] `P03.S08` - Render the shared calendar context, age, evidence and drilldown actions in the declarations TUI without duplicating business logic; `src/cadrumo/entrypoints/tui/declarations/calendar.py, src/cadrumo/entrypoints/tui/declarations/controller.py, src/cadrumo/entrypoints/tui/declarations/models.py and owning tests`.
- [ ] `P03.S09` - Prove CLI and TUI calendar parity with isolated synthetic stores and record live paths as not exercised; `dev/acceptance/calendar and owning tests`.

## Parallelization

Phases are ordered P01, P02, P03 because the shared evaluation and evidence contracts must be stable before frontend projection. Within P01, the historical-profile and lifecycle Steps may proceed independently after the effective-deadline contract is fixed if their file ownership remains disjoint. P02 is serialized around shared calendar evidence and reconciliation owners. P03 CLI and TUI Steps may proceed independently only after shared payload fields are stable and only when their files do not overlap active income, IVA, retenciones or assets work; otherwise serialize them. One writer owns each shared file.

## Verification

Focused domain, application, CLI and TUI tests prove CA1 through CA11 with synthetic data and explicit markers. The same as-of date and effective deadline produce consistent status, days overdue and recovery posture across calendar, agenda, backlog, work posture and frontend projections. Historical profile and cessation fixtures preserve residual obligations and refuse incomplete coverage. Evidence tests preserve local, AEAT, receipt, query-coverage and authenticity distinctions; notifications without grounded structured coordinates remain unlinked and never prove filing. CLI JSON retains typed evaluation context, provenance and actionable notices, while human CLI and TUI make scope, as-of, payment cutoff, overdue age and recovery actions readable without enum or color interpretation. Offline review performs no network access. CA12 compares canonical CLI/TUI meanings through independent synthetic stores under ACCEPTANCE-01; live reconciliation is reported NOT EXERCISED. A final integrated review must pass before plan completion.
