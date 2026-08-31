---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:d4d54400387574425ec352af92e750977fb7511bf6f239d383131ccc8c9745df'
step_id: 'S336'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make the operation modal's action row fit an eighty-column terminal, where two of its controls are currently unreachable: the modal body is sized at eighty per cent of the terminal, so sixty-four columns at the 80x24 floor every emulator still honours, while the action row is a non-wrapping horizontal carrying five buttons -- reject, apply, cancel, detach and close -- right-aligned with no small-width variant. Measured at that size, detach is clipped from column 66 and close sits entirely off-screen from 84 to 100. These surfaces carry no horizontal scroll affordance, so an overflowed control is not merely awkward, it cannot be reached at all. The operator consequence is the part that makes this more than cosmetic: the modal refuses to close for operations whose close policy demands a cancel request, so an operator on a small terminal watching a live operation can reach neither Detach nor Close and has no in-interface way out. The percentage-based width token is behaving correctly; the fixed five-control row is what does not fit. Wrap the row, or present a reduced control set at small widths with the remainder reachable, and prove containment at the eighty-column floor rather than only at comfortable sizes

## Scope

- `the operation modal's action row layout and its small-width behaviour`

## Changes

- `M` `src/cadrumo/entrypoints/tui/operations/modal.py`
- `M` `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py::test_the_operation_surface_fits_every_terminal_width -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync ruff check` / `ruff format` / `ty check` on the operations package -> `pass`

## Notes

**The decision: the action row WRAPS.** The five controls are laid in an
auto-wrapping grid with a minimum column width, which produces two rows inside
the modal body at the eighty-column floor and collapses back to a single row
wherever the body is wide enough. Measured after the change in all four
catalogues: two rows and no overflow at 80x24, one row at 120x40 and 200x60.

**A correction to my own first reasoning, which the row also carries.** I
began from the translated label lengths and concluded the constraint was
locale-bound -- that the Spanish set needed sixty-eight columns where the
English set fitted. That was wrong, and I only found it because a mutation run
reported identical button geometry in all four languages when I expected them
to differ. Textual gives every button a sixteen-column MINIMUM width, so five
buttons hold at least eighty columns between them before gutters, in every
language, against a body of sixty-four. Label length never was the binding
constraint and no language was a special case: the single row overflowed
everywhere. Both docstrings were corrected to the real reason before this
landed, so the code does not carry the wrong explanation.

**The locale parametrize was kept, with an honest justification.** Once label
length is not the constraint, running four locales no longer proves the case I
originally wrote it for. It is retained because it guards the layout against a
future label long enough to exceed that sixteen-column minimum and change how
the row wraps, and because it exercises each catalogue rather than whichever
one the ambient setting happens to select. The language is switched through
the real settings override the application reads, verified to change the
rendered labels, so it is a real axis rather than four identical runs.

**The operator consequence is what made this more than cosmetic.** These
surfaces carry no horizontal scroll affordance, so an overflowed control
cannot be reached at all, and the modal refuses to close for operations whose
close policy demands a cancel request. Before the change Detach was clipped
from column 66 and Close sat entirely off-screen at 84 to 100, which left an
operator on a small terminal watching a live operation with no in-interface
way out. The new proof therefore asserts containment against the modal body
AND against the terminal, on both axes.

**Mutation results.** Restoring the non-wrapping horizontal row reproduces the
original defect and fails the floor proof in all four locales, while the
wide-size collapse test still passes, which is correct. Shrinking the grid
column so all five controls are forced back into a single row fails the proof
too -- and that one matters most, because the row IS a single row in that
state, so a test that merely counted rows would pass it while the buttons
overflowed their cells. Both were runtime monkeypatches loaded from outside
the repository; no tracked file was edited and the plugins were deleted.

**Failures elsewhere in the run are not attributable to this work.** The
responsive-layout suite also reports three failures on the PROFILE surface,
raising `ProfileManagerScreen object has no attribute exit`. That is the
in-flight screen conversion owned elsewhere, the same cause as the failures
seen alongside the passphrase work. This change is confined to the operation
modal and its test module. No stash-based confirmation was available in this
shared tree, so this is a reasoned attribution and is not claimed as a proof.
Two type-checker diagnostics in the same test module sit at lines well above
the appended tests and were present before this change.

**Production reachability.** Direct and positive. The change is to the
composition of the shipped `OperationModal` that every supervised operation is
presented through, and the proofs drive that real modal, mounted from a real
submitted operation against the real registry, journal, lease and custody set,
at the real terminal sizes. An operator on an 80x24 terminal can now reach
Detach and Close.
