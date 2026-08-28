---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:fd5baf3da1298eafe5450e869789512e81b1d6940bb0334942e08e497ecc3525'
step_id: 'S337'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make the passphrase screen usable on a twenty-four row terminal, where its controls have never fitted: reproducing the pre-conversion topology puts the change button at row 26 against a 32-row content column, so the screen did not fit an 80x24 terminal before the screen conversion and does not after -- the conversion moved it one row and did not cause it. The immediate cause is that the passphrase action group is a vertical stack where the login and registration screens use a horizontal row, costing rows its siblings do not spend; but correcting that alone still leaves the content taller than the viewport, so this needs a narrow-terminal design decision rather than a layout tweak. Decide what the screen does at the 80x24 floor every emulator honours -- scroll the content, collapse a section, or present a reduced set with the remainder reachable -- and record WHY, because the next person will otherwise re-litigate it. Do not weaken the containment assertion to make it pass, and do not reshape the interface silently; this row exists because the previous owner correctly refused both

## Scope

- `the passphrase screen's action group and its narrow-terminal layout`
- `plus the containment assertion that surfaces the overflow`

## Changes

- `M` `src/cadrumo/entrypoints/tui/secret/passphrase.py`
- `M` `src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/secret/tests/test_secret_journeys.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/secret src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py src/cadrumo/entrypoints/tui/tests/test_visual_verification.py -m integration -n0` -> `fail`
- `verify:` `uv run --no-sync ruff check` / `ruff format` / `ty check` on the secret package -> `pass`

## Notes

**The narrow-terminal decision, and why.** The floor is served by SCROLLING.
Measured at 80x24 before any change, the content column was 31 rows against a
22-row viewport, with the primary action at y=27. Sharing one row between the
two buttons recovers 3 rows, leaving 28 against 22. Collapsing the intro and
the new-password hint would recover roughly 3 more and still not fit. Reaching
22 rows would require dropping a credential field or its label, which removes
part of the operation rather than laying it out differently: the screen needs
the current passphrase, the replacement, and its confirmation, each labelled,
plus the live strength line. So the content does not fit the floor and cannot
be made to without cost to the operation.

Scrolling is also not a new answer invented here. It is what the responsive
layout proofs for every other full-screen surface already record: horizontal
overflow is unrecoverable and is asserted absolutely, while vertical extent is
carried by the scroll host each surface mounts. This screen already mounted
that host; nothing consumed it, because the assertion demanded simultaneous
visibility instead of reachability.

**What changed in the screen.** The action group was a vertical stack where the
sibling login screen uses a horizontal row, spending 3 rows for no layout
benefit on a surface already past the floor. It is now a horizontal row with
the same shared style and the same button margin the login screen declares.

**A correction to the row's stated evidence.** The row says the login AND
registration screens use a horizontal row. Login does. Registration uses a
VERTICAL container holding a single button, where the axis costs nothing and
so is not evidence either way. The passphrase screen was an outlier against
login alone, not against two siblings. The conclusion is unchanged; the
supporting count was not.

**The assertion was re-expressed, not weakened, and that claim was tested.**
The previous check asserted that every control lay inside the viewport
simultaneously, which at the floor is unsatisfiable for any content taller
than the screen. It now asserts horizontal containment absolutely, and
vertical reachability by scrolling to each control and re-measuring it. The
obvious risk is that scrolling makes anything reachable and the proof becomes
vacuous, so it was tested directly: reproducing the original defect class the
assertion was written for -- a sibling displaced far down the column, the
`SourceActionCard` shape -- still fails the rewritten test at all three
terminal sizes, because the scroll host cannot bring a control past its
scrollable extent into view. The rewrite is therefore no weaker on the defect
it existed to catch, and stronger in one respect: it proves the operator can
reach each control rather than that the layout happened to fit.

**Two further tests pin the decision so it is not reversed silently.** One
asserts the actions genuinely start below the fold at the floor AND that the
scroll host genuinely carries them into view, with a stated instruction to
retire it deliberately rather than relax it should the content ever fit
outright. The other asserts the two actions share a single row.

**Mutation results.** Reverting the action group to a vertical stack at
runtime fails the single-row test and nothing else, which is correct: a
stacked row is still scroll-reachable. Making `scroll_visible` a no-op while
leaving the scroll host mounted and reporting headroom fails both the
reachability test and the decision test -- this is the mutation only an
assertion that actually scrolls can catch, and a test reasoning "a scroll
container is mounted, therefore reachable" would have passed it. Displacing
the action group far down the column fails the reachability test at every
size. All three were runtime monkeypatches loaded from outside the repository;
no tracked file was edited and the plugins were deleted.

**Failures in the wider run are not attributable to this work.** Running the
secret package together with the responsive-layout and visual-verification
suites leaves 30 failures. None involves the passphrase surface, and they
share one cause: screen classes no longer expose the app-level test driver
those suites call, an in-flight conversion of the login and registration
surfaces owned elsewhere. This change touches one screen and one test module.
No stash-based confirmation was available in this shared tree, so this is a
reasoned attribution and is not claimed as a proof.

**Production reachability.** Direct and positive. The change is to the
composition of the shipped `PassphraseScreen` that
`run_passphrase_change_tui` mounts, and the proofs drive that real screen
through the headless pilot against a real enrolled profile and the real
rotation door, at the real terminal sizes. An operator on an 80x24 terminal
can now reach the change and cancel actions.
