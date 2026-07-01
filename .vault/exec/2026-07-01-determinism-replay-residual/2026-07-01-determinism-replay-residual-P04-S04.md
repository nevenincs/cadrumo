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

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace determinism-replay-residual with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-01-determinism-replay-residual-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Add a determinism-conformance test axis: opt-in enrolment, per-command byte-identical envelope proof under frozen_clock+injected identity against real repositories, and a visible uncovered-gap report and ## Scope

- `enrol the ledger-add retried-no-op as the first state-transition case asserting db_sha256 identity after the idempotent second add against a hermetic synthetic var root.`
- `src/aeat/core/observability/tests/test_determinism_conformance.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a determinism-conformance test axis: opt-in enrolment, per-command byte-identical envelope proof under frozen_clock+injected identity against real repositories, and a visible uncovered-gap report

## Scope

- `enrol the ledger-add retried-no-op as the first state-transition case asserting db_sha256 identity after the idempotent second add against a hermetic synthetic var root.`
- `src/aeat/core/observability/tests/test_determinism_conformance.py`

## Description

- Add `test_determinism_conformance.py` at the entrypoints CLI test surface (the command-envelope layer, avoiding a core→entrypoints import inversion): an opt-in determinism-conformance axis over the `register_schema` `--format json` surface.
- Declare `ENROLLED_REPLAYABLE_COMMANDS` (opt-in, grows deliberately) enrolling `ledger.add` as the first case, plus `uncovered_replayable_commands()` introspection.
- Enrolled-determinism proof: capture the ledger-add retried-no-op envelope twice under `frozen_clock` with the hermetic bucket identity against real repositories (real service, real payload helpers, real registered schema, real emit), canonicalise+mask via the shared substrate primitive, and assert byte-identical full-envelope equality with zero differing paths.
- State-transition proof: create a keyed row, then retry the identical add (guarded idempotent no-op, empty `bucket_event_ids`), and assert the bucket's committed at-rest fingerprint is identical before and after the retry — the concrete proof the clock-free identity is a true post-state no-op, against a hermetic synthetic var root.
- Coverage discipline: `test_enrolled_commands_are_all_registered` fails on a stale enrolment; `test_uncovered_commands_are_reported_not_silently_passed` warns (visible, never silent) enumerating the uncovered registered commands, so the axis grows deliberately (opt-in visible ratchet).

## Outcome

- All 4 axis tests pass; the coverage warning surfaces "1 of 54 registered --format json commands enrolled; 53 uncovered (opt-in)". Ruff clean; collect-only clean.
- The state-transition tier uses the substrate's `compute_db_sha256` (the ADR's named db_sha256 tier) over a committed-files snapshot: before and after the retry the committed bucket files (main `.db` + committed `-wal`) are copied into a temp tree excluding the volatile `-shm` WAL read-index, and `compute_db_sha256` fingerprints that snapshot. The live var tree cannot be hashed directly in-session because the `-shm` read-marks flap on every read (not a state change) and its mmap handle cannot be removed on Windows after `engine.dispose()`; the snapshot lets `compute_db_sha256` run over the committed bytes exactly as it would at a between-process replay boundary where no connection is open. The main `aeat.db` is provably byte-identical across the idempotent retry.

## Notes

- All storage operations run inside one `frozen_clock` block (a write under a frozen clock resets the bucket session idle deadline to the frozen instant; a later real-clock op would see the session expired — the same constraint recorded for P02).
- The ledger-evidence `--format json` golden scenario the ADR pairs with Decision 1 enrols here in principle (this axis is its home per the ADR Consequences); only `ledger.add` is enrolled this cycle as the mandated first case. The axis is structured so further commands (evidence-add, invoice verbs) enrol by adding to `ENROLLED_REPLAYABLE_COMMANDS` plus a determinism proof — the visible ratchet the coverage test reports.
