---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:07a983deb929cc7dea24b68ddb567ebac56a9f4a7364cab008109c8bcb1d422c'
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
- `verify:` `pytest -n0 -m '' test_workbench_responsive.py::test_every_section_heading_is_separated_from_the_content_it_owns` -> `pass`

## Notes

Step left OPEN; this is a partial. The step asks for three things and one of
them is unmet.

Landed: the shared `.cadrumo-heading` rhythm on the token table, asymmetric by
construction (section gap above, stack gap below). Home now uses it in place of
its private `.home-heading`, which carried a `margin-top` only. AEAT Sync
gained the two headings it never had, so its stacked navigation and detail
tables are no longer one continuous run of rows.

Gate: the rhythm is read from the PAINTED frame, inside each heading's own
column span. A full-width blankness test reports a false gap on Home, whose
second column paints on the rows a left-column heading needs blank; that
mismeasurement was caught by the gate failing on correct code. Teeth proven by
flattening the gaps to symmetric -- both parametrisations failed -- and
restoring the file by copy.

Unmet: the rhythm reaches Home and AEAT Sync only. The Ledger, Declarations,
Profile and Modelo surfaces compose no heading widgets at all, so applying the
rhythm there is composition work rather than styling, and the gate only covers
the two surfaces that have headings to check. Row density is untouched.
