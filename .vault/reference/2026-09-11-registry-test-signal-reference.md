---
tags:
  - '#reference'
  - '#registry-test-signal'
date: '2026-09-11'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:40fd32247891aba7833a733b2eb1660777411cb62970909ec137b3f61893a215'
related: []
---

# `registry-test-signal` reference: `delta-aware signal verification`

## Summary

The current `just test-registry` result is not a trustworthy registry migration verdict. Its lane
transport is useful, but the reducer can false-green missing lanes, the recipe omits the migration
signal's own tests, and several selected tests encode the displaced full-copy/casilla-only model.

The accepted edition-authoring decision makes a successor the union of every declaration family
with a stable identity. Unchanged members are inherited, formula and binding identifiers become
edition-free, and completeness manifests remain edition-local. The test signal must gate the
compiled semantic result and malformed delta declarations without requiring an unfinished
migration backlog or successor-local restatement.

### Signal reducer defects

`dev/test_runs/command.py:322-355` computes whether expected lanes completed, but checks child
exit status first. A successful child that emits no lane markers therefore returns exit 0 with
`classification=clean` and `result=passed` while reporting `complete=false`,
`lanes_completed=0`, and every expected lane as `not_run`. Missing expected lanes must make the
signal incomplete and nonzero regardless of the child status.

For a real collection/bootstrap failure with lane finish markers but no pytest terminal summary,
the aggregate is classified as a tool failure, but `dev/test_runs/command.py:274-293` classifies
each lane as `blocking_findings` in phase `execution`. The same envelope reports
`lanes_tool_failed=0` at `dev/test_runs/command.py:364`. Summaryless failed lanes need one
consistent tool/collection classification.

The focused reducer test is stale and internally contradictory. At
`dev/test_runs/tests/test_command.py:253` it requires `test_probe.py` to be absent from all
stdout, while the same test at line 278 requires that path in the final envelope's bounded
`top_affected_files`. The final envelope is the intended home for the hotspot; only progress
events should omit detail. The import-boundary test at line 167 also assumes one stdout JSON
object although the runner now emits start and finish envelopes.

### Population ownership gap

The private registry conformance lane at `Justfile:928-929`, used by `test-registry` at
`Justfile:934-935`, does not select `dev/registry/analysis/tests`,
`dev/registry/compiler/tests`, or the test modules directly under `dev/registry/pipeline`.
That leaves 22 modules and 332 test functions outside the registry aggregate. In particular,
all 57 tests in `dev/registry/analysis/tests/test_edition_delta_status.py` and the delta
publication/generator tests are absent from the signal whose migration behavior they protect.
The public `test-registry-conformance` recipe duplicates the same omission.

`dev/tests/test_lane_reachability.py:176` and line 465 detect this gap, but those checks belong to
the tooling population rather than direct `just test-registry`. Their current live run names
these directories as unowned.

### Stale delta assumptions in selected tests

`dev/registry/tests/test_delta_minimality.py:91-102` requires modelo 131 to remain a live
restater. Correctly migrating modelo 131 makes the test fail. The same module's line 391 requires
the live unlineaged-successor count to remain above zero. Both are campaign-state ratchets; the
constructed minimal-delta, planted-restatement, and parity assertions around them provide the
durable detector teeth without preserving debt.

`dev/registry/tests/test_materialisation_excludes_non_casilla_families.py:1-5` states the old
casilla-only materialisation rule, and lines 182-217 require an omitted successor formula to stay
absent. The completeness-manifest exclusion remains valid, as does an exclusion for a family that
cannot prove stable identity. The blanket non-casilla exclusion and formula assertion do not.

`dev/registry/tests/test_revision_inherited_reference_resolution.py:1-8` assumes every successor
redeclares formulas and bindings. Lines 213-244 refuse inherited casilla references unless the
successor states the target declaration itself, including an edition-free binding. Under the
accepted union rule the successor may state or inherit that declaration. Dangling and ambiguous
references must still fail, but successor-local authorship is not a valid requirement.

### Migration report correctness

The report's deterministic, constructed-input, delta-aware tests are shaped correctly: they avoid
frozen live counts and distinguish coverage from authoring work. They are not currently owned by
`test-registry`, so they do not protect the operator signal.

The in-flight family restatement extension has one unsafe comparison. At
`dev/registry/analysis/edition_delta_status.py:262` and lines 481-482 it removes
`source_refs`, `legal_refs`, and `additional_source_refs` wholesale before declaring two
members identical. Its test at `dev/registry/analysis/tests/test_edition_delta_status.py:579`
codifies that any binding differing only in references is restated. References are ignorable only
after subtracting each edition's declared family defaults. A genuine member-specific authority or
source change must remain a difference; otherwise the report can recommend inheritance that loses
grounding.

### Live verification on 2026-09-12

`just test-registry` exited 1 before running a test: all three lanes failed during schema
collection/import. The final aggregate correctly selected `tool_failure`, but its per-lane
classifications were inconsistent as described above.

`just report-registry-edition-delta-status --totals-only` also exited 1 before producing a report
because the in-flight `Modelo` type refactor entered a circular import while Pydantic evaluated
registry schema annotations. The focused edition-status tests failed collection for the same
reason. These are current worktree failures, not evidence that a delta registry is invalid.

The focused `dev/test_runs/tests/test_command.py` and `test_lanes.py` run produced 2 failures
and 7 passes. The lane-reachability run produced 8 failures and 34 passes, including the three
unowned registry directories. A direct summary-reducer probe reproduced the false green with two
expected lanes, zero lane events, exit 0, and `complete=false`.
