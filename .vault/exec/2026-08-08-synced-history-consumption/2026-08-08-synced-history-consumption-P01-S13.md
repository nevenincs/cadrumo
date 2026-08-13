---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5f9c15690192a83d0be0e83d405d27701b5901b865550fddfb5deb2580d6f1c3'
step_id: 'S13'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Gate carry-source revision coverage on the property, because a consumer whose revision range exceeds its source range carries a silent blank at the boundary. Today Modelo 130 covers filing years 2019 to 2030 while its Modelo 100 carry source covers 2020 to 2025 only, so the 2026 carry asks for a Modelo 100 revision that does not exist - a pull of it refuses at the snapshot lookup, nothing is stored, and resolve_bindings_from_local_store then skips the binding silently by documented design. The same gap exists at the low end. Nothing is broken today because a filing year AEAT has not published cannot carry, and that is precisely why this needs a gate rather than a note: the trigger is Modelo 100 shipping a 2026 revision and nobody is watching for it. Gate: the check asserts that every previous_filing and relation source has revision coverage spanning the consuming modelo own coverage and fails when a consumer range exceeds its source range, gating on that property and never on the 2020-2025 or 2019-2030 spans which are todays corpus, with a holder-confirmed out-of-repo mutation proving it bites

## Scope

- `src/cadrumo/domain/calculations/registry`
- `src/cadrumo/domain/calculations/registry/tests`

## Description

FIRST ATTEMPT SHIPPED, THEN REVERTED, BECAUSE OF WHERE IT WAS WIRED, NOT WHAT
IT CHECKED. A first version of this gate — no allowlist, no structural
exclusions — was wired live into the mandatory build validator to see what
it found. It found two real gaps immediately and correctly. It was reverted
within minutes because a build-blocking check with no allowlist takes the
WHOLE registry down for every concurrent agent the instant it lands, and
another agent independently hit exactly that: `resources()` failing tree-wide
with these same two errors, correctly diagnosed as a code defect rather than
a registry defect, before the revert landed. Reverting rather than shipping
was the right call and is recorded here as the reusable lesson: an experiment
against the mandatory validator in a shared worktree needs its own copy or an
announcement first, never a live wire-and-see.

BUILT ON RULING. The design that landed: a build-time refusal (not a
test-level report — "a census that cannot fail a build is a report, not a
gate") with an explicit allowlist, entries keyed by
`(binding_id, source_modelo, missing_from_year, missing_through_year)` — the
FULL range, never the start year alone, so a gap that widens while keeping
the same start is not silently re-absorbed by an entry that under-states it.
An allowance whose range no longer matches a real gap is itself a build
failure ("stale previous-filing year-coverage allowance ... remove the
entry"), proven live by monkeypatching the gate to widen a real gap and
watching the old entry go stale in the same run.

Two exclusions are STRUCTURAL and live in the gate's predicate rather than
the allowlist, because neither has a discharge condition that could ever
fire — the tell the ruling gave for what belongs in code instead of a
document:

- A required year below the registry's own representable floor (2000,
  matching every `modelo_year` field's own `ge=2000` bound already in this
  package) is outside what any revision could ever model regardless of
  content.
- A required year beyond the SOURCE modelo's own latest published year is
  not yet published by AEAT for anyone. An open-ended consumer revision (the
  common shape — a modelo's current revision typically declares no
  `year_to`) would otherwise fail this gate every single year purely because
  the future has not arrived, which is not a corpus omission.

Reused the existing `previous_filing_source_reference` parser rather than
re-deriving selector fields, extending it with `filing_year_delta`,
`max_year_delta` and `has_variable_year_offset` (the last excludes two
selectors — `prior_quarter_expanding_span`, `source_period_offset_from_target`
— whose PER-ANCHOR year deltas cannot be represented as one interval; two
bindings in the bundled corpus carry this shape and are explicitly skipped
rather than mis-checked).

## Outcome

`validate_previous_filing_source_year_coverage` is wired into
`validate_registry_scope`, the mandatory registry-tree gate, alongside its
sibling `validate_previous_filing_binding_closure`. `resources()` loads
clean; `authority.validate_registry()` (the strict, fail-fast path) passes
clean.

THE TWO REAL GAPS, recorded here as the row itself asked rather than left
only in a chat message:

- `irpf.previous_year_economic_activity_net_income` (Modelo 130's only
  revision, `2019-y-siguientes`, open-ended) reads Modelo 100 at
  `filing_year_delta=-1`. Its own first modelled year (2019) already needs a
  2018 Modelo 100 revision; every later year up to Modelo 100's own corpus
  floor (2020) needs one likewise. Missing: 2018 and 2019 both, against
  Modelo 100's discrete `[2020, 2025]` revision set.
- The three Modelo 720 self-referencing prior-year valuation baselines
  (`modelo-720-prior-year-cuentas-valoracion-baseline`,
  `-valores-valoracion-baseline`, `-inmuebles-valoracion-baseline`) read
  Modelo 720 itself at `filing_year_delta=-1`. Modelo 720's own revision
  floors at 2012 (the `2013-y-siguientes` revision id names when it was
  AUTHORED, not what it covers), needing a 2011 Modelo 720 revision that does
  not exist. Every later year is covered by the same open-ended revision
  reading its own immediately preceding year, so each gap is exactly one year
  wide.

Eight tests in
`domain/calculations/registry/tests/test_validate_previous_filing_year_coverage.py`,
all against the REAL loaded registry (no synthetic fixtures for the
integration-shaped cases): the clean-corpus proof (zero failures — both
allowance ranges consumed, nothing unlisted); a widened-gap positive control
(monkeypatching `_period_matching_revisions` to drop Modelo 100's 2020
revision, growing the Modelo 130 gap from 2018-2019 to 2018-2020 — the
narrower allowance correctly goes stale and the wider gap correctly surfaces
as new); a mid-range positive control (dropping Modelo 100's 2022 revision
opens a brand-new single-year hole nothing was ever written for, while the
pre-existing 2018-2019 allowance stays consumed, not stale); and four pure
unit tests pinning `_clipped_required_interval`'s two structural exclusions
and `_missing_years`'s finite walk directly.

## Notes

THE EDGE CASE THE FIRST WIDENING TEST FOUND IN ITS OWN GATE. Emptying a
source modelo's period-matching revision set entirely (rather than shrinking
it) hit an assertion failure in `_missing_years`, because the upper-bound
computation and the missing-year walk were reading from two DIFFERENT
candidate sets — one over every revision the source modelo owns, the other
already period-filtered. Fixed by deriving the upper bound from the SAME
period-matched set the walk uses, and by skipping the check entirely when
that set is empty (a period-shape gap is the sibling closure validator's
finding, not this gate's — reporting it here too would duplicate under a
different message). Caught by a test written to probe the boundary, not by
review.

`ty` refused a first version of the two monkeypatch tests: reassigning a
module-level function's name via bare attribute assignment does not
type-check even when the replacement's signature matches exactly. Rewritten
onto pytest's own `monkeypatch` fixture, which is the sanctioned form of
"runtime monkeypatch from outside the repo" this campaign's own quality
gates ask for when proving a gate bites.

A SECOND, MORE SERIOUS REGRESSION SURFACED ONLY BY RUNNING THE FULL
`domain/calculations/registry/tests/` DIRECTORY, not by running the new test
file alone. 177 tests failed on the first full run; a SECOND full run after
the fix below failed only 157, with `resources()` and the pre-existing set
otherwise unchanged (confirmed by string-diffing the two failure logs, not
by re-reading either). The 20-test difference is this row's own regression,
not a subset of it — every one of those 20 traced to this gate's own
"stale previous-filing year-coverage allowance" output string, which the
post-fix log carries zero occurrences of. The remaining 157 are pre-existing
and unrelated — concurrent in-flight Modelo 303 registry work elsewhere in
this shared tree — confirmed the same way, by grepping for this gate's own
output and finding nothing. `TestTypoTwinWarning.test_typo_twin_blocks_registry_scope`
and three `test_authority.py` cache-invalidation tests are the ones read in
full to diagnose the mechanism; they call `validate_registry_scope` /
`ValidatedRegistryAuthority.load` against a SYNTHETIC single-modelo or small
fragment fixture rather than the full bundled tree. The staleness check's
"was this allowance consumed" logic had no way to distinguish "this run
genuinely closed the gap" from "this run never reached the binding at all" —
a single-modelo fixture with no
`previous_filing` bindings consumes nothing, so it reported all four
allowances stale regardless of their real state. Fixed by tracking which
allowances' OWNING BINDINGS were actually reachable in the given modelo set
(`encountered_binding_ids`) and only judging staleness for those; an
allowance whose binding a particular call never reached is neither consumed
nor stale, just not a question that call can answer. Re-ran the full
directory after the fix: the same four tests pass, and the remaining
failures are the same pre-existing set (verified by string-diffing the
before/after failure lists, not by re-reading them).

This is the reusable lesson the row itself asked to survive past a chat
message: a build-time gate carrying cross-call STATE (an allowlist with a
staleness obligation) must define "was this entry exercised" against what
THIS CALL actually reached, never against the gate's own global expectation
of what a full-corpus run would reach — the same shared-worktree caution the
first (reverted) attempt already taught, generalised to test fixtures rather
than concurrent agents.

VERIFICATION WAS RUN BY THE AUTHOR THIS TIME, unusually for this campaign's
own convention of leaving verification to the gatekeeper — because the class
of defect this row's first attempt produced (a tree-wide red for every
concurrent agent) is exactly the one that must never reach a shared branch
unverified. `pytest` on the new test file (8 passed) and the previously
broken four (4 passed), a full `domain/calculations/registry/tests/` run
BEFORE and AFTER the fix, `ruff check`/`ruff format --check`, `ty check`,
and `basedpyright` were all run and green before this record was written.
