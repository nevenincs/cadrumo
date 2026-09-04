---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:d0f5509918fee406be5c2c80fad314bb0dee87401f618295c35a555687f53922'
step_id: 'S416'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Make destination admission a property of the CURRENT generation instead of the first one. INDEPENDENT REVIEW, REPRODUCED 2026-09-04: the root freezes `admissions` from generation 1 while every factory resolves its projection from the live `current[0]`, and the two then disagree the moment a refresh legitimately changes availability. Two failures fall out of the one cause. An operator who registers without a NIF and then declares it in Profile gets a coherent refreshed generation with AEAT Sync available, and the parity check raises, killing search for the WHOLE session under workbench.search.refresh_unavailable while navigation keeps advertising a reader-unavailable reason that is now a lie; only sign-out recovers. An operator who CLEARS their NIF -- a supported trim-or-clear edit that nothing refuses -- keeps a palette entry whose factory now raises RuntimeError out of a Textual handler. Recompute admissions and the factory set on every capture and rebuild the catalogue, or refuse through the navigation layer rather than through _required_projection.

## Scope

- `src/cadrumo/entrypoints/tui/launcher.py and src/cadrumo/entrypoints/tui/app.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `M` `src/cadrumo/entrypoints/tui/app.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/tui/tests/test_installed_generation_composition.py src/cadrumo/entrypoints/tui/tests/test_launcher_composition_root.py src/cadrumo/entrypoints/tui/tests/test_app.py src/cadrumo/entrypoints/tui/tests/test_search.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Changes to behaviour

Admissions and factories are now derived together from whichever generation is current, by
one door that reads it at call time, so a destination is offered exactly when its projection
exists. The root rebuilds its catalogue on the same authoritative child return that refreshes
search, and the search parity check compares a refreshed capture against its OWN admissions
rather than the session's first ones -- that stale comparison was what killed search for the
rest of a session after a supported profile edit.

Teeth proven by removing the door: both new gates fail.

## Notes

RESIDUAL, not closed by this step. The review's second symptom was a palette offering a
route whose factory then raises. Rebuilding on child return closes the return path, but a
generation can still change between a return and a palette selection, and that window is
unproven. It needs either a navigation-layer refusal at mount time or a gate that exercises
the window; neither is in this step.
