---
tags:
  - '#exec'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-07-01'
step_id: 'S04'
related:
  - "[[2026-07-01-determinism-replay-residual-plan]]"
---

# Add a determinism-conformance test axis: opt-in enrolment, per-command byte-identical envelope proof under frozen_clock+injected identity against real repositories, and a visible uncovered-gap report

## Scope

- `enrol the ledger-add retried-no-op as the first state-transition case asserting db_sha256 identity after the idempotent second add against a hermetic synthetic var root.`
- `src/aeat/core/observability/tests/test_determinism_conformance.py`

## Description

- Add `test_determinism_conformance.py` at the entrypoints CLI test surface (the command-envelope layer, avoiding a core→entrypoints import inversion): an opt-in determinism-conformance axis over the `register_schema` `--format json` surface.
- Declare `ENROLLED_REPLAYABLE_COMMANDS` (opt-in, grows deliberately) enrolling `ledger.add` (state-transition case) and `ledger.evidence.add` (the D1 golden case), plus `uncovered_replayable_commands()` introspection.
- Enrolled-determinism proof (ledger.add): capture the retried-no-op envelope twice under `frozen_clock` with the hermetic bucket identity against real repositories (real service, real payload helpers, real registered schema, real emit), canonicalise+mask via the shared substrate primitive, and assert byte-identical full-envelope equality with zero differing paths.
- State-transition proof (ledger.add): create a keyed row, then retry the identical add (guarded idempotent no-op, empty `bucket_event_ids`), and assert the bucket's committed at-rest fingerprint is identical before and after the retry — the concrete proof the clock-free identity is a true post-state no-op, against a hermetic synthetic var root.
- D1 golden proof (ledger.evidence.add): capture the evidence-add `--format json` envelope across two fresh-bucket runs (same synthetic PDF, same fields, same injected profile identity, same frozen instant) and assert byte-identical with ZERO residual differing fields — so the content-addressed evidence_id needs no mask; the parent anti-tautology proof stays exactly {snapshot_id, run_id}.
- Coverage discipline: `test_enrolled_commands_are_all_registered` fails on a stale enrolment; `test_uncovered_commands_are_reported_not_silently_passed` warns (visible, never silent) enumerating the uncovered registered commands, so the axis grows deliberately (opt-in visible ratchet).

## Outcome

- All 5 axis tests pass; the coverage warning surfaces "2 of 54 registered --format json commands enrolled; 52 uncovered (opt-in)". Ruff clean; collect-only clean.
- The state-transition tier uses the substrate's `compute_db_sha256` (the ADR's named db_sha256 tier) over a committed-files snapshot: before and after the retry the committed bucket files (main `.db` + committed `-wal`) are copied into a temp tree excluding the volatile `-shm` WAL read-index, and `compute_db_sha256` fingerprints that snapshot. This is the ADR-faithful realization of the named tier (operator-accepted, no doc-note divergence to reconcile). The live var tree cannot be hashed directly in-session because the `-shm` read-marks flap on every read (not a state change) and its mmap handle cannot be removed on Windows after `engine.dispose()`; the snapshot lets `compute_db_sha256` run over the committed bytes exactly as it would at a between-process replay boundary where no connection is open. The main `aeat.db` is provably byte-identical across the idempotent retry.

## Notes

- All storage operations run inside one `frozen_clock` block (a write under a frozen clock resets the bucket session idle deadline to the frozen instant; a later real-clock op would see the session expired — the same constraint recorded for P02).
- The ledger-evidence golden scenario the ADR pairs with Decision 1 is realized HERE by enrolling `ledger.evidence.add` in this axis (per the ADR Consequences), not as a duplicate standalone test. The axis grows by adding a command to `ENROLLED_REPLAYABLE_COMMANDS` plus its determinism proof — the visible ratchet the coverage test reports.
- Review LOW#3 — ACCEPTED-negligible (no code fix): the in-session committed fingerprint is theoretically susceptible to a SQLite WAL auto-checkpoint firing between the two reads (folding `-wal` frames into the main `.db`), which would change the on-disk byte layout without changing committed content. In practice the test databases hold a single tiny row, far below the default `wal_autocheckpoint` (1000 pages) threshold, so no checkpoint fires between the paired reads; the risk is negligible and left unguarded rather than adding checkpoint-pinning machinery.
