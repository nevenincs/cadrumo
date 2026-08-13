---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:2c1829326e8128265c3d76b44be46416b7808f28eeae7cf40548dab966e5df34'
step_id: 'S09'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# RETROACTIVE ROW for a correctness defect shipped by P03.S02 and closed across four commits, opened after the fix rather than before it so the history does not live only in a chat message. WHAT SHIPPED WRONG. The filed sweep fed the record's bounded count pair from two different populations. A recapture advisory is raised once per observation ABSORBED, while the count it was paired against was observations successfully ENROLLED. Enrolment narrows twice against absorption, by the latest-per-period collapse in select_latest_filed_observations_in_history_order and by a BEST_EFFORT enrolment failure diverting its observation into failures. So divergence_count could exceed unit_count and the record refused ITSELF at the very end of a real sweep, after every unit had already been fetched and persisted, destroying the partial-run report and failing worst precisely when the run went worst. A second quieter bug rode with it. unit_count silently meant enrolled rather than reached, against its own field docstring, so a run that reached ten and enrolled three recorded three and was indistinguishable from a run that reached three. That is the partial-reads-as-complete lie inside the store built to stop it. HOW IT WAS FOUND, which is the reusable part. Not by a gate. By re-reading HEAD before starting the next row. A peer's revert at 3612f729fa landed AFTER db8c87fd52, deleted the redeclared carrier, and correctly repointed this writer onto a same-shaped but differently-bounded field. It compiled and type-checked clean, because nothing static owns this class. The revert row's own verification claim, that the only consumer is the report field it also removes, was true when authored and FALSE when executed, because db8c87fd52 added a second consumer in between. The executor re-ran it and caught the drift. A row's verification claim is re-run at execution time, never trusted from authoring time. SECOND REUSABLE LESSON, a misread by this row's own author. The behavioural gate was first reported unbuildable offline on the strength of the sibling capture test's docstring. That docstring records that CAPTURE FROM AEAT is unreachable, because per-row capture fetches the cotejo PDF through context.request where route interception never runs. What the gate needed was a PERSISTED OBSERVATION, which is separable and which persist_filed_calculation_observation seeds directly. A negative claim inherits the scope of the thing actually checked and then travels at full width. Structural-only coverage would have shipped behind a disclosure reading as honest and complete. CLOSED BY four commits. 2b10626f59 repoints both counts onto the accumulator's canonical reached-tally, which already drives the sweep limit and is the only counter incremented in every mode. 22a7262ba6 makes the invalid pair unrepresentable, because record_sync_run now takes a SyncRunCoverage derived through coverage_of which reads BOTH numbers off ONE source, so pairing two populations requires an object that misreports itself rather than a call site that pairs two numbers, and it adds an AST floor requiring every production writer to derive while asserting a non-empty call-site floor before checking offenders. e9d49e0a08 adds the behavioural gate reproducing the defect state through production code with a positive control. f3eb0f3c6e adds the vacuity floor so a collapse of enrolment to zero cannot satisfy the narrowing assertion. The bound deliberately lives in two places. SyncRunCoverage guards CONSTRUCTION where the invalid pair is authored, and SyncRunRecord guards LOAD where a corrupted payload never passed through coverage at all. Gate is unrun by the author and verification belongs to gatekeeper

## Scope

- `src/cadrumo/application/storage/sync_runs and src/cadrumo/application/live/_filed_data_capture.py and src/cadrumo/application/live/tests/test_recapture_divergence_coverage.py`

## Description

FOUND ALREADY CLOSED. This record was authored retroactively; the defect,
its discovery, and its fix are fully narrated in the plan row text itself
(the row was opened AFTER the fix, by design, per its own opening line), and
all four closing commits were already on `main` before this record existed.

- `2b10626f59` — repoint both counts onto the accumulator's canonical
  reached-tally.
- `22a7262ba6` — make the invalid `unit_count < divergence_count` pair
  unrepresentable via `SyncRunCoverage` / `coverage_of`, plus the AST floor
  requiring every production `record_sync_run` writer to derive.
- `e9d49e0a08` — behavioural gate reproducing the defect state through
  production code with a positive control.
- `f3eb0f3c6e` — vacuity floor so a collapsed-to-zero enrolment cannot
  satisfy the narrowing assertion.

## Outcome

Verified present at HEAD by reading, not by running:

- `_CaptureAccumulator.reached_count` and `.divergences` are the sole source
  `coverage_of` reads for the filed sweep (`application/live/_filed_data_capture.py`),
  both properties documented as reading off ONE object rather than two
  independently-narrowing populations.
- `SyncRunCoverage` refuses `divergence_count > unit_count` at construction
  (`application/storage/sync_runs/_records.py`), and `SyncRunRecord` carries
  the same bound at LOAD, so a corrupted persisted payload that never passed
  through `coverage_of` is still caught.
- `test_every_production_run_record_derives_its_coverage_from_a_source`
  (`sync_runs/tests/test_sync_run_record_store.py`) walks every production
  `record_sync_run` call site by AST and refuses one that passes raw
  `unit_count` / `divergence_count` or builds `coverage=` without a
  `coverage_of(...)` call, with a non-empty-call-site floor so the walk
  cannot pass by finding nothing. This module's own two new call sites (in
  `P03.S07`'s `_export_service.py`) pass this same gate unchanged.
- `application/live/tests/test_recapture_divergence_coverage.py` exists and
  carries the behavioural reproduction plus the vacuity floor named above.

Ran locally: `pytest src/cadrumo/application/storage/sync_runs/tests/test_sync_run_record_store.py`
— 10 passed, including the tree-wide coverage-derivation floor. The
recapture-coverage behavioural test was not re-run in this session; its
presence and shape were confirmed by reading, and its own closing commit
(`e9d49e0a08`) already carries verification for the state it reproduces.

## Notes

The two reusable lessons the row itself records are the load-bearing content
here and are not repeated in paraphrase: a row's verification claim is
re-run at execution time, never trusted from authoring time; and a negative
claim ("X is unreachable") inherits the scope of the thing actually checked,
not the width it is later read at. Both are attributed to production
incidents in THIS plan (the `P02.S08` revert's stale consumer census, and the
`P03.S02`/`P03.S07` capture-gate scope narrowing), not invented for this
record.
