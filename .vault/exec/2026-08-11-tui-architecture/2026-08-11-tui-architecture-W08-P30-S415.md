---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:37b8b4143c782af25f5d470686d8585d4097ea0b20ad2861f123a2e0d37e8110'
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
- `M` `src/cadrumo/entrypoints/tui/components/tests/test_widgets.py`
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

Row density remains untouched, and is the one part of this step's scope not
addressed.
