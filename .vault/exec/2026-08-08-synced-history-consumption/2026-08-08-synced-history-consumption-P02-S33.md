---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:1b0a46f7955c9759ede076f985aa8ab6f2a688be7ad6a08f5bf61bc0138df06d'
step_id: 'S33'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---

# Adjudicate the two per-casilla comparators that the S32 ruling never covered, as their own question rather than as an S32 sub-task, because they are the gap that row's original scope missed rather than a detail within it. casillas_a_recapture_would_change at application/live/_filed_data_capture.py:1249 answers what a re-capture would overwrite and today compares with no tolerance, so a sub-cent artefact reads to the operator as a filing AEAT corrected. The revision-versus-revision delta at application/modelo/_projection.py:835 answers what changed between two of the app's own calculation revisions, where a tolerance may be actively wrong because both sides are the app's own arithmetic and an exact match is the honest claim. Those two are not obviously the same shape as each other, still less as the two S32 ruled, so decide each against its own use rather than by analogy. Gate - each of the two carries a recorded verdict naming its constraint shape and whether a tolerance is correct for its use, and a mutation proves whichever behaviour is chosen actually bites

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`
- `src/cadrumo/application/modelo/_projection.py`

## Description

- Found that a prior, already-committed change (dated ahead of this row's own
  authoring) had already run the substitutability pre-filter across all six
  pairs of the four-member cluster and recorded the discriminator (the
  absence contract, not the tolerance) beside each site, including both
  comparators this row covers. That settled the SUBSTITUTABILITY question but
  left the TOLERANCE question, which this row's own gate asks as a distinct
  axis, unresolved for one of the two and unproven for both.
- Adjudicated `casillas_a_recapture_would_change`: both its sides are
  AEAT-sourced captures of the same underlying filing (a fresh re-capture
  against a previously stored one), the same rationale that grounds the
  ratified pair's tolerance. Verdict: a tolerance IS correct for this
  comparator's use, unlike the delta.
- Implemented that verdict: added a `tolerance` keyword parameter defaulting
  to exact equality, changed the bare inequality to `abs(delta) > tolerance`,
  and added a small resolver mirroring the two existing published-tolerance-
  or-exact-equality helpers' identical contract (registry-published tolerance
  for the observation's own modelo/year/period triple, falling back to exact
  equality when no registry authority resolves for the triple or the
  resolved revision declares no verification expectations). Threaded it
  through the comparator's one production caller.
- Deliberately did NOT create a fourth shared tolerance-resolution helper or
  import either of the two existing private ones across a package boundary:
  consolidating them is its own judgment call this row's own text explicitly
  hands to a later row, which forbids mechanically collapsing tolerance sites
  onto one shared primitive before that measurement is done.
- Adjudicated the revision-vs-revision delta in `_projection.py`: the
  already-committed verdict (both sides are the application's own arithmetic,
  so a tolerance would hide a real change rather than absorb noise) is
  correct and the code already implements it as a bare, unfiltered delta.
  No code change was needed there; this row's addition is the missing proof.
- Wrote the mutation-style proof for both verdicts, each pinned against a
  REAL bundled registry value (Modelo 130 2026 1T publishes tolerance 0.01)
  rather than a hardcoded literal, so neither proof can pass by coincidence:
  for the re-capture comparator, a change exactly at the published tolerance
  is absorbed while one cent beyond it still fires, proven both at the pure
  comparator and end to end through the real notice-producing caller against
  a real persisted observation; for the delta comparator, two real revisions
  differing by exactly that same published tolerance surface the full delta
  unabsorbed, proving the comparator does NOT read the value the sibling
  comparators are correct to read.

## Outcome

COMPLETE against the row's gate. Both comparators now carry a recorded
verdict naming their constraint shape and whether a tolerance is correct for
their use: yes for the re-capture comparator (now implemented), no for the
delta comparator (already implemented, now proven). A mutation-style test
proves each verdict actually bites rather than merely asserting the
implementation.

Regression sweep across every test file consuming the touched module (51
tests) and the extended `_projection.py` compare-service tests (3) is green.
`ruff check`, `ruff format --check` and `basedpyright` are clean on every
touched production file.

## Notes

The row's own line numbers for both comparators were stale (function
locations had moved since the row was authored); both were re-found by name
before editing, per this session's standing discipline of never trusting a
row's own premise without re-checking it at HEAD.

This row's own tolerance-resolution helper is now a THIRD near-duplicate of
the same published-tolerance-or-exact-equality shape (alongside the two S32
already named). That is expected, not a shortcut: the row explicitly forbids
consolidating tolerance sites here, and the later row that inventories and
measures the whole tolerance-primitive population will need to find this new
site too.
