---
tags:
  - '#exec'
  - '#live-justificante-reconcile'
date: '2026-06-10'
related:
  - '[[2026-06-10-live-justificante-reconcile-plan]]'
---

# `live-justificante-reconcile` `P02` summary

Phase P02 (live capture orchestration) is complete. All three Steps landed as
atomic explicit-path commits with their gates green; the offline test sweep is
12 passed and the live test is correctly deselected by default.

- Modified: `src/aeat/application/live/__init__.py`
- Modified: `src/aeat/application/live/_justificante.py`
- Created: `src/aeat/application/live/tests/test_justificante_capture_resolution.py`
- Created: `src/aeat/application/live/tests/test_justificante_capture_live.py`

## Description

P02 delivers the live read path and resolves the feature's primary risk. The
pure `resolve_period_expediente` resolver cross-references the period-bearing
declarations register against the procedure tree by `expediente_id`, because the
tree `Expediente` carries no period and cannot disambiguate quarters on its own.
The resolver refuses (rather than falling back to a wrong-quarter receipt) when
no declaration matches the period or the matched expediente is absent from the
tree, and picks the latest filing when a period was re-filed.

The `require_live_read`-gated async `capture_justificante_snapshot` orchestrator
wires resolution, `capture_justificante`, and service persistence, exposing four
seam providers that default to the live sede implementations so the wiring is
exercised offline with real typed records (S04 commit `15debafc8`, typing
follow-up `bf76b73e2`). The disambiguation gate is pinned by `S05` — 1T and 2T
resolve to distinct expedientes and never collapse — and the end-to-end live
pull is covered by the opt-in `aeat_live` test in `S06`.

Verification status: 13 offline tests pass; pyright strict and ruff are clean on
all four files; the live test is env-gated via `requires_live_enabled()` and the
`aeat_live` marker (deselected by default), never xfail or skip. The service and
resolver are promoted to the `application.live` top-level re-exports per the
service-imports-via-top-level-reexports rule, ready for the P05 CLI verb.

Code review (vaultspec-code-reviewer) returned one HIGH finding: the
within-period tiebreak ranked only on `presented_at`, so a later cancellation
(non-`ALTA` `estado`) row could outrank the accepted filing and pull the
wrong-state receipt — diverging from the two sibling period-resolution surfaces
that rank `ALTA` first. Resolved in commit `d049e8d25`: the tiebreak is now
`(estado == ALTA, presented_at, expediente_id)` and a regression test proves a
later `Anulada` row does not win over the earlier `ALTA` filing. All other
review axes passed. P03 (the official-evidence stamp) and P04 (the
reconcile-from-persisted seam) build on this orchestrator and may proceed in
parallel.
