---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:70b8579c4c805436d473dd014776b54805515dff1cdf3c0ea2ccf75a56b023a1'
step_id: 'S426'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make the width-limit gate scan the whole TUI tree, after measuring what that surfaces. MEASURED 2026-09-04: test_no_surface_pins_or_caps_its_content_width calls scan_directory without recursive=True, which defaults to False, so it has only ever seen the eight top-level modules and never looked inside ledger, declarations, aeat_sync, modelo, profile, secret, components or operations. The two max-width 78 caps that the layout audit identified as the primary cause of table truncation sit outside its reach entirely. Combined with the substring defect already fixed, the single offender this gate reported was the only one that was not real. Turn recursion on only after enumerating the genuine pinned widths across those subdirectories, because that population is unknown and must be measured deliberately rather than discovered as a wall of failures; several of them are the same caps S413 is removing rather than tokenising.

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_theme.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/tests/test_theme.py`
- `verify:` `pytest -n0 -m '' src/cadrumo/entrypoints/tui/tests/test_theme.py` -> `pass` (36)

## Notes

`scan_directory` defaults `recursive` to False, so this gate had only ever read
the eight top-level modules. Everything inside `ledger`, `declarations`,
`aeat_sync`, `modelo`, `profile`, `secret`, `components` and `operations` was
outside its reach -- including both `max-width: 78` caps that caused the table
truncation, which is why the one offender it did report was the only one that
was not real.

The step required measuring the population before turning recursion on, and
that measurement is the reason this is a one-line change rather than a wall of
failures: ZERO offenders across the whole tree. S413 removed the caps rather
than tokenising them and S414 moved the literal measures onto the token table,
so the population recursion would have surfaced was already emptied by the two
steps that ran first. Recursion costs nothing today and holds every
subdirectory from here.

Teeth proven in a SUBDIRECTORY, which is the only proof that means anything for
this change: reintroducing `max-width: 78` in `declarations/calendar.py` fails
with `width limits: ['calendar.py: max-width: 78;']`. A first attempt proved
nothing -- the injection targeted a string that does not exist in
`ledger/overview.py`, the edit raised, and the gate passed on unmodified
source. A green teeth check is a finding, not a pass; the injection was redone
against a verified anchor. Restored by copy and the restore verified.
