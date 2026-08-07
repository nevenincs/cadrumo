---
tags:
  - '#plan'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:2a81b9c23ffd13651e8b75111728494042b0adb656808104fa7ec2f2579bd2ec'
tier: L1
related:
  - '[[2026-08-07-declarations-register-pagination-adr]]'
---

# `declarations-register-pagination` plan

## Description

Executes `2026-08-07-declarations-register-pagination-adr`: the declarations
register walker parses one DOM snapshot per `(modelo, ejercicio)` query and
returns it as complete with no signal when AEAT's own pager label declares
more rows than were rendered. Implementation is authorised; every Step below
is an executable code change with a named verification gate, not a deferred
"investigate" row. This plan implements detection-and-refusal (the ADR's
chosen option B) only; full page traversal is explicitly out of scope per
the ADR's Constraints and Considered options and, per operator directive, no
Step in this plan performs or requires any live authenticated AEAT probe.
Whether AEAT's real grid paginates this form stays unverified; a future
attempt to build traversal or to verify pagination against a live account
needs separate operator sign-off and is not authorised by this plan. S01
adds the typed page result and pager-total parsing at the parse boundary.
S02 wires the truncation refusal into both register-walk entry points. S03
confirms the refusal reuses the existing per-pair bulk-capture failure
taxonomy rather than a new abort mechanism. S04 updates the pinning test
(`test_declarations_pagination_blindness.py`, commit `82df6ed81d`) to assert
the new refusal in the same change that implements it, per its own
docstring's stated reversal condition, and adds a companion non-regression
test for the untruncated, no-pager-label case. S05 proves the S04 gate
actually bites: break the detector via an outside-the-repo runtime
monkeypatch, confirm the test reds, restore, confirm green — a gate is
unproven until it has failed on demand.

## Steps

- [x] `S01` - Add a typed DeclaracionesRegisterPage carrying rendered rows, a parsed declared_total (int or None, None only when no pager label is present) and a derived truncated property to _parse_listbox, reusing a pager-label regex analogous to the pinning test's fixture-independent extraction. Gate: a new unit test asserts declared_total is parsed correctly off the existing synthetic paginated fixture and is None off the real single-row fixture; `src/cadrumo/adapters/outbound/aeat/sede/_declarations_listbox.py`.
- [x] `S02` - Consume the typed page in DeclaracionesRegisterSession.walk and walk_declarations_register, raising SedeParseError naming modelo, ejercicio, rendered count and declared_total when truncated is true, instead of returning a bare tuple. Gate: a unit test drives walk against the synthetic paginated fixture end to end and asserts SedeParseError is raised, and a second test drives it against the real single-row fixture and asserts the prior tuple-returning behaviour is unchanged; `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `S03` - Confirm capture_filed_data_bulk's existing failure-row assembly turns the new SedeParseError into a FiledDataCaptureFailureRow under BEST_EFFORT so the sweep continues to the next pair, and re-raises under FAIL_FAST, adding no new bulk control-flow branch. Gate: an application-level test forces one (modelo, ejercicio) pair's walk to raise the truncation error under BEST_EFFORT and asserts the bulk report lists it as a FiledDataCaptureFailureRow while the remaining pairs still complete, and a companion test asserts FAIL_FAST propagates the same error; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `S04` - Rewrite test_declarations_pagination_blindness.py (commit 82df6ed81d) so its assertions flip from pinning the silent gap to asserting the new refusal fires on the paginated synthetic fixture, and add a companion test proving the real no-pager-label fixture is never classified as truncated. Do not delete, skip, xfail, or loosen this test to make an unrelated fix pass. Its docstring's own stated reversal condition is authorisation to REPLACE its assertions with the refusal assertion, not to remove coverage of the gap. Gate: pytest on this file is green with the new assertions and reds if truncated defaulted to False unconditionally; `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_pagination_blindness.py`.
- [x] `S05` - Prove the S04 refusal test actually detects a broken detector. From a scratch script outside this repository, never a tracked-file edit so a peer sweep cannot commit the mutation, monkeypatch the declared_total parsing or the truncated property to always report untruncated, rerun the S04 refusal test and confirm it reds naming the expected rendered-versus-declared mismatch, then remove the monkeypatch and confirm the same test is green again. Gate on the property that a rendered-versus-declared mismatch is refused, never on an exact expected row count, since a hardcoded count encodes one fixture snapshot and stops detecting anything once the fixture changes; `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_pagination_blindness.py (proof only, no tracked file is edited to perform it)`.

## Parallelization

S01 must land first: S02 and S03 both consume the typed page result S01
introduces. S02 and S03 touch disjoint files (`_declarations.py` versus
`_filed_data_capture.py`) and may run in parallel once S01 is closed. S04
depends on S02's refusal shape existing and must land in the same change
that closes S02, per the ADR's Constraints (the pinning test must not be
weakened or deleted separately from the fix that supersedes it). S05 depends
on S04's new test existing and runs immediately after S04 closes, before the
Step is marked done, since S05 is the proof that S04's gate actually
detects a regression rather than passing vacuously.

## Verification

The plan is complete when every Step is closed and:

- The pass condition is a PROPERTY, not a count: `test_declarations_pagination_blindness.py`
  asserts that walking a register page where the rendered row count is
  strictly less than the pager's own declared total raises the truncation
  refusal. The existing fixture (declared total 8, rendered 3) exercises
  this property; the test must not assert those specific numbers as the
  pass condition, only that a genuine mismatch is refused.
- A companion test proves the real single-row, no-pager-label fixture
  (`declaraciones-modelo-100-2022.html`) is never classified as truncated,
  so the detector does not false-fire when AEAT serves no pager label.
- S05's mutation proof is recorded as having been run: the S04 test reddened
  under the outside-the-repo monkeypatch and passed again after it was
  removed. A gate with no recorded red run is not yet verified.
- A targeted pytest run over
  `src/cadrumo/adapters/outbound/aeat/sede/tests/` and
  `src/cadrumo/application/live/tests/` (or the narrowest owning test
  directories touched by S01 through S04) passes.
- Per the ADR's Constraints, no live-AEAT probe is run to validate this
  work; the open question of whether AEAT's real grid paginates this form
  stays explicitly unresolved and is not implicitly closed by this plan.
  Building traversal, or running any live authenticated verification of
  pagination, requires separate operator sign-off this plan does not grant.
