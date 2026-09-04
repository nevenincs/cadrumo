---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:cfb7b73ad9e27c1a65e305238b1286cf1120388708e2865fd89821ed43272fa8'
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
- `M` `src/cadrumo/entrypoints/tui/tests/test_workbench_responsive.py`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `pytest -n0 -m '' test_theme.py test_workbench_responsive.py test_home.py` -> `pass` (62)

## Notes

Rhythm: `.cadrumo-heading` on the token table, asymmetric by construction --
section gap above to separate a group from the previous one, stack gap below to
bind the heading to its own rows. Home replaced its private `.home-heading`
(top margin only); AEAT Sync gained the two headings it never had, so its
stacked navigation and detail tables are no longer one run of rows.
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
and overwrites anything issued during mount. The restored-selection branch
keeps its own position deliberately.

The gate reads painted cells inside each heading's own column span, and it
earned its keep three times over. It failed on correct code first, because a
full-width blankness test reports a false gap on Home's second column. It then
had to be swept across all four supported terminals, because the scroll defect
was invisible at the ordinary size the gate originally ran at. Finally, the
below-the-fold exemption added for the sweep made it blind to that same defect
-- injecting the bug passed 8/8 -- so a heading that opens a region is now
never excused, and only that version detects it (2 failed at floor and
above-wrap). Teeth proven by removing the scroll fix and restoring by copy.

Remaining, not blocking this step: Ledger, Declarations, Profile and Modelo
compose no heading widgets at all, so the rhythm reaches them only as
composition work; row density is untouched; the sweep covers the two surfaces
that have headings.
