# Calendar obligations checkpoint

Status: partial. Session `calendar-obligations`; provider, lead model, cc number and UUID remain pending because the operator did not assign them. Worktree `Y:\code\cadrumo-worktrees\tui-modelo`, branch `tui/modelo`. Consumed CALENDAR-01 revision 0.1, session-policy revision 1.6 and ACCEPTANCE-01 revision 1.5.

Approved plan: `2026-09-21-calendar-obligations-plan`, feature `calendar-obligations`. Next open Step: P02.S05. Governing accepted decisions are linked from the plan. Live AEAT access, environment setup, authentication, notification content opening, acknowledgement, response and filing submission remain excluded.

Discovery: Luna Max `calendar_discovery` inspected the bounded calendar delta at HEAD `f72ef01f760f87bbe36e83016ed6393921335090` against anchor `bbbc47407efa8fb41ff16126c9fb08aea11ee723`. It found no calendar-path delta, identified raw-versus-adjusted status, historical applicability and cessation risks, and reported shared TUI composition collisions. No tests were run by discovery.

Completed commits:

- `07fdfc70b1` P01.S01: effective adjusted deadline status, recovery and exact overdue age; 125 focused tests passed.
- `c3de610489` P01.S02: explicit evaluation date in applicability; 62 calendar tests passed.
- `2557bc2c38` plus `34f36da` P01.S03 and phase-review correction: period-based cessation and conservative inactive-legal-entity handling; 54 engine/lifecycle tests passed. Audit `2026-09-21-calendar-obligations-audit` records the resolved high finding and repeated P01 PASS.
- `09d48b4e45` P02.S04: safe declarations projection of original/effective closes, shift, evaluation date, overdue age and conflict presence while retaining source coverage/freshness and separate evidence axes; 21 application plus 18 TUI tests passed.

No live paths were exercised. Repository-wide Vaultspec check still has unrelated legacy errors; feature-local plan/schema/markdown checks were clean at the recorded Steps. The RAG service could not start because its installed interpreter lacks a supported accelerator; no environment repair was attempted.

Next bounded actions:

1. P02.S05: inspect the existing event/document taxonomy only around notification-to-filing association; keep messages explicitly unlinked unless structured coordinates exist, and prove metadata projection cannot upgrade filing evidence or derive response deadlines.
2. P02.S06: reuse `work_plazo` conditional surcharge posture; do not assess liability or conflate parsed sanction amounts.
3. Run the P02 phase-close review, then P03 CLI, TUI and isolated synthetic parity Steps.

Deferred capability: persistent notification-to-filing association remains outside
this plan. P02.S05 requires notifications without authoritative filing coordinates
to remain independent message observations; it does not introduce association
records, matching heuristics, confirmation states, or correction persistence.

Preserve concurrent income, IVA, retenciones and assets edits. In particular, shared TUI composition and modelo lifecycle files were already dirty and are not owned by this session.
