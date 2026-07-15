---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S14'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Render one hand-authored inline-SVG icon and class-scoped styling per display class in the shared search controller card row (box, document, terminal, code, question mark), reading the shipped display_class meta only, never re-deriving it in JS

## Scope

- `docs/_static/cadrumo-docs.js`
- `docs/_static/cadrumo-docs.css`

## Description

- Add a `DISPLAY_CLASS_ICONS` map to the shared search controller: five hand-authored inline-SVG icons keyed by display class (`casilla` box, `modelo` document, `cli` terminal, `technical` angle-brackets, `doc` question-mark), authored in the file's existing 16x16 stroke/viewBox idiom.
- Read `meta.display_class` verbatim in `cardFromPagefind` into `entry.displayClass`; select the icon from that string alone, with zero kind/URL heuristic.
- Render the icon in `paint` as a leading `cadrumo-palette-item-icon--<class>` span inside a new `cadrumo-palette-item-body` text wrapper; a row with no shipped class renders no icon (degrade path).
- Restyle `cadrumo-palette-item a` as a flex row with an icon column, add class-scoped icon colours, and retire the now-redundant crumb-dot badges the icon supersedes.

## Outcome

Delivered on commit `9cfb70eac2`. The per-class icon renders on both hosts (the Ctrl-K modal and the inline search page) because the shared controller drives both. Licence-clean: hand-authored inline SVG only, no icon-font and no external asset. The JS never re-derives the class, matching ADR D7 / Axis-6 O6b. Verified green by the browser gates: `test_palette_ranking.py::test_palette_casilla_outranks_cli_and_renders_class_icon` (casilla and cli class icons render) and `test_search_page_inline_ladder.py::test_search_page_renders_the_tier_ladder` (the `doc` icon renders on the inline host).

## Notes

Full-text page hits are Pagefind directory-indexed and carry no `display_class`, so they render no icon by the sanctioned degrade path rather than a guessed one.
