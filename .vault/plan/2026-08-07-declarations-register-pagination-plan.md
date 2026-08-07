---
tags:
  - '#plan'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_hash: 'sha256:d1c5f11ab05aefbdb877a652577d4b65d784ca9ea4bbfb81f7d0e4ce55240405'
tier: L1
related:
  - '[[2026-08-07-declarations-register-pagination-adr]]'
---

# `declarations-register-pagination` plan

## Description

Executes `2026-08-07-declarations-register-pagination-adr`: the declarations
register walker parses one DOM snapshot per `(modelo, ejercicio)` query and
returns it as complete with no signal when AEAT's own pager label declares
more rows than were rendered. This plan implements detection-and-refusal
(the ADR's chosen option B) only; full page traversal is explicitly out of
scope per the ADR's Constraints and Considered options. S01 adds the typed
page result and pager-total parsing at the parse boundary. S02 wires the
truncation refusal into both register-walk entry points. S03 confirms the
refusal reuses the existing per-pair bulk-capture failure taxonomy rather
than a new abort mechanism. S04 updates the pinning test
(`test_declarations_pagination_blindness.py`, commit `82df6ed81d`) to assert
the new refusal, per its own docstring's stated reversal condition, and adds
a companion non-regression test for the untruncated, no-pager-label case.

## Steps

- [ ] `S01` - Add a typed register-page result carrying rendered rows, parsed declared total, and a truncated flag to _parse_listbox; `src/cadrumo/adapters/outbound/aeat/sede/_declarations_listbox.py`.
- [ ] `S02` - Consume the typed register page in walk and walk_declarations_register, raising SedeParseError on a truncated page instead of returning a bare tuple; `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `S03` - Route the truncation refusal through the existing per-pair FiledDataCaptureFailureRow taxonomy in the bulk capture sweep; `src/cadrumo/application/live/_filed_data_capture.py`.
- [ ] `S04` - Rewrite test_declarations_pagination_blindness.py to assert the truncation refusal instead of the silent gap, and add a companion test proving a single-page (no pager label) result is never treated as truncated; `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_pagination_blindness.py`.

## Parallelization

S01 must land first: S02 and S03 both consume the typed page result S01
introduces. S02 and S03 touch disjoint files (`_declarations.py` versus
`_filed_data_capture.py`) and may run in parallel once S01 is closed. S04
depends on S02's refusal shape existing and must land last, in the same
change that closes S02, per the ADR's Constraints (the pinning test must not
be weakened or deleted separately from the fix that supersedes it).

## Verification

The plan is complete when every Step is closed and:

- `test_declarations_pagination_blindness.py` asserts, against the existing
  `declaraciones-modelo-100-paginated-synthetic.html` fixture (declared
  total 8, rendered 3), that walking the register raises the truncation
  refusal rather than silently returning 3 rows.
- A companion test proves the real single-row, no-pager-label fixture
  (`declaraciones-modelo-100-2022.html`) is never classified as truncated.
- A targeted pytest run over
  `src/cadrumo/adapters/outbound/aeat/sede/tests/` and
  `src/cadrumo/application/live/tests/` (or the narrowest owning test
  directories touched by S01 through S04) passes.
- Per the ADR's Constraints, no live-AEAT probe is run to validate this
  work; the open question of whether AEAT's real grid paginates this form
  stays explicitly unresolved and is not implicitly closed by this plan.
