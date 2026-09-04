---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:08d9e79902c1ea2ff1c68dc501bb4b3bbdfd63ccf459d5905615a617f7e23924'
step_id: 'S414'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Derive every workbench surface from one design language instead of per-screen values. OPERATOR REVIEW OF THE RENDERED FRAMES, 2026-09-04: spacing and colour are inconsistent and non-canonical across surfaces, and not all of the design derives from the same UX vocabulary -- screens were evidently styled against themselves rather than against a shared token table. The theme module already declares tokens; what is missing is that every surface spends them and nothing hard-codes a measure or a colour of its own. Audit the whole TUI stylesheet surface for literal values standing in for tokens, for tokens used inconsistently between screens that mean the same thing, and for the places where two screens express one concept differently.

## Scope

- `src/cadrumo/entrypoints/tui/components/theme.py and every screen stylesheet under src/cadrumo/entrypoints/tui/`

## Changes

- `M` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `M` `src/cadrumo/entrypoints/tui/secret/registration.py`
- `verify:` `pytest -n0 -m '' src/cadrumo/entrypoints/tui/tests/test_theme.py` -> `pass`

## Notes

The two stylesheets still outside the token table are now inside it. Both
`home_candidates.py` CSS blocks went through `tokenised()`, which they had
never used, and their literal measures resolve to the scale: the panel box to
`tight`/`space-1`/`stack`, its corner to `cadrumo-radius`, its heading gap to
`stack`. `registration.py` already called `tokenised()` and simply hardcoded
three `margin-bottom: 1`, now `stack`.

Offenders went 11 -> 0 and the gate is green at 36 passed. Teeth re-proven by
restoring one literal `margin-bottom: 1` in `registration.py`; the gate named
that exact file and declaration, and the file was restored by copy.

FOLLOW-UP, from measuring the button geometry that the AEAT click investigation
exposed. `cadrumo-control-max-width` was tokenised at 28 in the earlier pass --
the literal lifted out of the AEAT stylesheet, carried across without being
questioned. Measured against the shipped catalogues, that cap wraps ELEVEN of
the sixteen declared AEAT action labels, in all four locales, English included
(`pull_filed_all` at 27 cells wraps because a button also spends two on its
border and two on `line-pad`).

A wrapped label costs a row, so that button alone is taller and the action row
goes ragged -- precisely the failure the `control-pad-x` note two lines above
already argues against, arrived at from the other side. It also had a
consequence beyond looks: the taller neighbour reached far enough to consume a
simulated press aimed at the button above it, which is what surfaced as a
failing in-flight guard.

The new value is derived rather than chosen: the longest declared label is 43
cells (Spanish and Catalan tie), plus two for the border and two for
`line-pad`, so 47 is the floor and 48 is the next even value. Verified by
measurement across three candidates -- at 28 the two probe buttons are 3 and 5
rows, at 40 they are 3 and 4, at 48 both are 3.

Gated by `test_no_declared_action_label_wraps_its_control`, driven from the
shipped catalogues rather than a sample string, because the binding constraint
is whichever locale translates an action longest and English -- the language a
developer reads while picking a number -- is nowhere near it. Teeth proven by
restoring 28: the gate names all eleven offenders with their cell counts and
row heights. Restored by copy; 115 passed across the component and AEAT suites.

AUDIT, negative result, recorded so it is not repeated. Having found one token
carrying an unexamined literal, the rest of the table was checked the same way.

Every token but two carries a recorded derivation; the two bare ones,
`cadrumo-gutter-y` (1) and `cadrumo-indent` (2), are small spacing values that
predate this campaign and cap nothing.

Every declared label that could reach a capped control was then measured
against the new 48, across all four catalogues. Exactly one exceeds it:
`tui.search.action.available` at 50 cells in Catalan. It is NOT a defect --
`search.py` composes no `Button`, and that string is palette row text rather
than a control label -- but it was checked rather than assumed, because the
cap's whole failure mode was a number that looked plausible until measured.

So no further control wraps at 48, and the only remaining risk in this family
is a future label longer than the cap. That is what
`test_no_declared_action_label_wraps_its_control` exists to catch, and it reads
the catalogues rather than a fixed list, so a new AEAT action is covered the
day it is translated.
