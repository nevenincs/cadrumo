# Calendar obligations checkpoint

Status: complete. Session `calendar-obligations`; provider, lead model, cc number and UUID remain pending because the operator did not assign them. Worktree `Y:\code\cadrumo-worktrees\tui-modelo`, branch `tui/modelo`. Consumed CALENDAR-01 revision 0.1, session-policy revision 1.6 and ACCEPTANCE-01 revision 1.5.

Approved plan: `2026-09-21-calendar-obligations-plan`, feature `calendar-obligations`. All nine Steps are closed and the final integrated review is PASS. Governing accepted decisions are linked from the plan. Live AEAT access, environment setup, authentication, notification content opening, acknowledgement, response and filing submission remain excluded and NOT EXERCISED.

Discovery: Luna Max `calendar_discovery` inspected the bounded calendar delta at HEAD `f72ef01f760f87bbe36e83016ed6393921335090` against anchor `bbbc47407efa8fb41ff16126c9fb08aea11ee723`. It found no calendar-path delta, identified raw-versus-adjusted status, historical applicability and cessation risks, and reported shared TUI composition collisions. No tests were run by discovery.

Completed commits:

- `07fdfc70b1` P01.S01: effective adjusted deadline status, recovery and exact overdue age; 125 focused tests passed.
- `c3de610489` P01.S02: explicit evaluation date in applicability; 62 calendar tests passed.
- `2557bc2c38` plus `34f36da` P01.S03 and phase-review correction: period-based cessation and conservative inactive-legal-entity handling; 54 engine/lifecycle tests passed. Audit `2026-09-21-calendar-obligations-audit` records the resolved high finding and repeated P01 PASS.
- `09d48b4e45` P02.S04: safe declarations projection of original/effective closes, shift, evaluation date, overdue age and conflict presence while retaining source coverage/freshness and separate evidence axes; 21 application plus 18 TUI tests passed.

No live paths were exercised. Repository-wide Vaultspec check still has unrelated legacy errors; feature-local plan/schema/markdown checks were clean at the recorded Steps. The RAG service could not start because its installed interpreter lacks a supported accelerator; no environment repair was attempted.

Completion evidence:

1. `7303c28b91` closes P02.S05 with unlinked-notification and replay regressions.
2. `e0d2d10681` closes P02.S06 with shared, unassessed conditional surcharge guidance.
3. `b8518c1801` and `2ef234bd50` close the CLI and TUI projections.
4. `4bc2828a49` plus `fc0a8e9766` close offline CLI/TUI parity and its ledger evidence.
5. The bounded integrated run passed 97 application/CLI/acceptance tests and 18 TUI tests; the final audit commit is `f32d555a56`.

Deferred capability: persistent notification-to-filing association remains outside
this plan. P02.S05 requires notifications without authoritative filing coordinates
to remain independent message observations; it does not introduce association
records, matching heuristics, confirmation states, or correction persistence.

Preserve concurrent income, IVA, retenciones and assets edits. In particular, shared TUI composition and modelo lifecycle files were already dirty and are not owned by this session.
