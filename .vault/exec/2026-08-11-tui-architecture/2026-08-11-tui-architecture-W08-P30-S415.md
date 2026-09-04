---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:3df2803843328c3ae86b5db0bb89000084d386d7acf814c38dbbaaa68f4350e6'
step_id: 'S415'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Give logical UX groups the separation that makes a screen readable. OPERATOR REVIEW OF THE RENDERED FRAMES, 2026-09-04, and the more important of the two spacing findings: a title and the rows beneath it carry no separation, and neither do the major groups a screen is built from, so a surface reads as one continuous run of data that is difficult to parse. This is not decoration -- a heading that does not visibly own the content under it makes the operator work out the structure line by line. Establish the vertical rhythm as tokens (group gap, title-to-content gap, row density), apply it across every workbench surface, and prove it from the painted cells rather than from stylesheet declarations.

## Scope

- `src/cadrumo/entrypoints/tui/components/theme.py and every workbench screen under src/cadrumo/entrypoints/tui/`

## Changes

- `M` `src/cadrumo/entrypoints/tui/components/theme.py`
- `M` `src/cadrumo/entrypoints/tui/home.py`
- `M` `src/cadrumo/entrypoints/tui/aeat_sync/screens.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/overview.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`
- `M` `src/cadrumo/entrypoints/tui/declarations/overview.py`
- `M` `src/cadrumo/entrypoints/tui/components/widgets.py`
- `M` `src/cadrumo/entrypoints/tui/components/tests/test_component_boundary.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/tests/test_workbench_fixtures.py`
- `M` `src/cadrumo/entrypoints/tui/components/tests/test_widgets.py`
- `M` `src/cadrumo/entrypoints/tui/ledger/entries.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_workbench_responsive.py`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `pytest -n0 -m '' test_workbench_responsive.py tui/ledger/tests tui/declarations/tests` -> `pass` (20 + 109)

## Notes

Rhythm: `.cadrumo-heading` on the token table, asymmetric by construction --
section gap above to separate a group from the previous one, stack gap below to
bind the heading to its own rows. Home replaced its private `.home-heading`
(top margin only). AEAT Sync gained the two headings it never had.
`.cadrumo-heading-lead` marks a heading that opens a scroll region: no previous
group, so equal gaps, and both edges are restated because a Textual rule that
sets one margin edge replaces the whole box.

A REAL DEFECT was found by rendering rather than by the suite, and it predates
this step. Home mounted with the page already scrolled two rows down: focusing
the first table scrolls it into view, and in the single-column layout that
scrolled the top of the page away. Its opening heading was therefore absent at
the floor, above-wrap and 100x40 while 120x40 looked perfect. Fixed by
returning the page to the top on a fresh arrival, deferred to
`call_after_refresh` because the focus scroll is applied after layout settles
and overwrites anything issued during mount.

The rhythm now reaches Ledger overview, Ledger reconciliation and Declarations
overview as well. Those screens already had section labels above their tables;
they simply never carried the heading class, so the labels sat flush against
their own rows. Ledger reconciliation and both overviews also gained the
heading their first table never had, with four new keys across all four
locales.

The gate earned its keep four times. It failed on correct code first, because a
full-width blankness test reports a false gap on Home's second column, so
blankness is measured inside each heading's own column span. It had to be swept
across all four supported terminals, because the scroll defect was invisible at
the ordinary size. The below-the-fold exemption added for that sweep made it
blind to the same defect -- injecting the bug passed 8/8 -- so a heading that
OPENS a region is now never excused. Finally, locating a heading by searching
the frame for its text found the wrong row: the Declarations overview lists a
"Declaraciones" area in the table ABOVE its "Declaraciones" heading, so the
search measured the rhythm of a data row. Headings are now located by their own
widget region. Teeth proven by flattening the gaps to symmetric: all 20
parametrisations fail, all 20 pass restored.

Profile and Modelo were examined and deliberately keep their own grouping
mechanisms rather than gaining headings: Profile groups with `cadrumo-panel`
border titles, Modelo with those and with `DisclosureGroup` titles. Both
already name and separate their sections, so a heading there would name the
same group twice.

What DID need fixing at that level is the distance. Three mechanisms mark a
logical group in this product and only two shared a measure: panels carry
`$cadrumo-section` and headings now do, while `DisclosureGroup` had no CSS at
all and inherited Textual's default, so two titled groups sat flush against
each other. Measured with two mounted groups: gap 0 before, 2 after. The
grouping affordances may legitimately differ -- a panel is static, a disclosure
collapses -- but the distance that says "new group" has to be one distance.

Profile's source cards did need the heading rhythm and now take it: their
titles ran straight into the previous card's action button. Measured on two
mounted cards: both titles now `Spacing(top=2, bottom=1)`, second title clear
of the first card's button.

That gap is now gated.
`test_every_grouping_mechanism_separates_its_groups_by_the_same_distance`
mounts consecutive disclosure groups and consecutive panels and measures the
painted distance between them against the `cadrumo-section` token, so a drift
in EITHER mechanism fails and names the offender. Teeth proven twice, once per
mechanism: flattening `DisclosureGroup` reports
`{'DisclosureGroup': 0, 'cadrumo-panel': 2}`, and demoting the panel margin to
the stack token reports `{'DisclosureGroup': 2, 'cadrumo-panel': 1}`. Each file
restored by copy; 86 passed across the component and theme suites.

The source-card rhythm is gated too:
`test_a_source_card_title_is_separated_from_the_card_above_it` mounts two cards
and asserts each title carries the asymmetric pair, `(section, stack)`, rather
than any pair at all -- equal gaps would leave the title floating between the
two cards. Asserted from mounted geometry because the Profile manager surface
refuses to open standalone (it needs an active profile pointer), so this is the
only place the rhythm can be observed. Teeth proven by removing the heading
class: `(0, 0) rather than the (2, 1) rhythm`. Restored by copy; 51 passed.

Row density, the last part of this step's scope, is now one decision.
`cadrumo-cell-padding` joins the token table and `ContentDataTable` applies it
so no call site names a number. Home's three lists had set `cell_padding=0`
with no reason recorded while every other table in the product took Textual's
default of 1, so two surfaces disagreed about where a row begins; those
overrides are removed.

Density turned out to be an ALIGNMENT question rather than a spacing one. A
table insets its first column by the cell padding, so a heading flush at the
container edge starts one cell to the left of its own data and the group reads
as ragged. `.cadrumo-heading` and Home's `.home-state` lines now take the same
inset, and Home, AEAT Sync, Ledger overview and Declarations overview each show
one left edge from heading through rows.

Gated by `test_a_heading_shares_its_left_edge_with_the_rows_it_owns`, the
horizontal counterpart to the rhythm gate: neither can see the other's defect,
because correct gaps above and below a heading say nothing about whether it
lines up with the rows it introduces. It repeated the rhythm gate's own early
mistake -- measuring across the full painted line found Home's SIDEBAR text and
reported a left edge of 81 -- and is measured inside the heading's column span
for the same reason. Teeth proven by removing the inset: two surfaces fail
naming both columns. Restored by copy; 94 passed.

Running the ledger suite whole after the density change surfaced a live
regression that predates it and belongs to another writer: commit `19fd223559`
replaced `cast("ContentDataTable[str]", self.query_one(sel, ContentDataTable))`
with `self.query_one(sel, ContentDataTable[str])` at two sites in the Ledger
entries screen. Textual `isinstance`-checks that argument and Python refuses an
instance check against a subscripted generic, so the screen raised at MOUNT and
took eight ledger tests with it. The type checker approves of both forms; only
running the screen tells them apart. Restored to the cast form with the reason
in a comment, and gated statically by
`test_no_query_passes_a_subscripted_generic_as_its_expected_type`, which scans
the whole TUI package for a subscripted expected-type on `query`, `query_one`
and `get_child_by_type`. Teeth proven by reintroducing the exact refactor at one
site: the gate names the file, the line and the call. 113 passed across the
ledger and responsive suites afterwards.

Sweeping the devtools suite after the density change turned three fixture
geometry gates red, and the cause was a latent flaw in the gate rather than in
the change. `_visible_tables` returned EVERY table on screen, hidden ones
included. A screen hides a table whose zone is empty; the widget is then
`display: none` at size 0x0, and Textual still derives a scroll extent from its
cell padding, so it reports horizontal overflow while painting nothing. The
assertion was testing a widget that is not on screen.

It went unnoticed only because Home's three lists carried `cell_padding=0`,
and it surfaced the moment density became one shared token -- the accident that
hid it was exactly the inconsistency this step removed. Measured across every
fixture at every supported width before touching the helper: 45 HIDDEN tables
report an overflow and NO DISPLAYED table does, so nothing the operator can see
regressed. The helper now honours its name.

Narrowing a gate to fix your own red is how gates rot, so this one was
re-proven afterwards: removing the responsive column budget from the Ledger
entries screen makes a VISIBLE table overflow and the narrowed gate fails at
all three widths, naming the fixture. Restored by copy, and the restore
verified by grep before continuing rather than assumed.

CORRECTION. `test_completing_one_overview_operation_keeps_the_other_action_reachable`
was filed twice in this campaign as pre-existing and not mine. It was mine.
Removing the two AEAT Sync headings makes it pass; restoring them makes it
fail, which is the experiment that settles it and the one I did not run. The
earlier check reverted `application/aeat_sync/workspace.py` to HEAD and
concluded "fails at HEAD too" -- but HEAD already carried the heading change,
so that check could never have isolated it.

The cause is not the rhythm being wrong. `pilot.click` targets SCREEN
COORDINATES, and the two section headings cost six rows, which pushes the
operation buttons below the fold at the 80x24 floor. The click then lands on
whatever is painted at those coordinates, the handler never runs, and the
failure reads as a broken in-flight guard. Measured: the button sits at y=16 of
24 once scrolled into view, and off-screen before that.

The test now scrolls each button into view before clicking, which is what an
operator does to reach a control below the fold, not a workaround for the
assertion. Its subject -- that completing one operation leaves the other
reachable -- is unchanged, and it still detects a real defect: removing the
one-shot `event.button.disabled = True` fails it. Deterministic across three
isolated runs where it previously failed in isolation and passed inside larger
suites; 88 passed across both AEAT suites.

Worth stating plainly: the rhythm does cost six rows at the floor terminal, and
these operation buttons now start below the fold there. The page scrolls and
the controls remain reachable, so this is the accepted cost of the separation
rather than a defect -- but it is a cost, and it was invisible until a
coordinate-based click tripped over it.
