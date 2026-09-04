---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:ac4b27a4657085ac67c19813864bb48804c20b0a4dfe9f39adbdea6a4925340d'
step_id: 'S418'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Let the command palette refuse instead of raising, and give the refusal code a rendering path. INDEPENDENT REVIEW, REPRODUCED 2026-09-04: the search provider dereferences the workbench search service unconditionally and the root raises when it is None -- but None is the DESIGNED refusal state, set alongside workbench_search_refusal_code, and it is the first-run state for any profile without a declared NIF. Opening the palette in that state raises RuntimeError. The refusal code has NO production consumer anywhere in src: it is written by the root and read only by two tests, so the operator is never told why search is unavailable. Return no hits and surface the code.

## Scope

- `src/cadrumo/entrypoints/tui/search.py and src/cadrumo/entrypoints/tui/app.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/search.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_search.py`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/tui/tests/test_search.py` -> `pass`

## Notes

None was the DESIGNED refusal value for the search service and the provider dereferenced it
anyway, so opening the palette raised on the first-run state of any profile whose sources
are not all readable yet. The refusal code the root publishes for exactly this had no
consumer anywhere in production.

The palette now yields one hit naming the refusal and navigating nowhere. An unrecognised
code degrades to generic wording rather than being shown raw, because a reason code is an
internal token and not operator copy; a second gate asserts that.

The host protocol gained the refusal channel, so the search test double had to implement it
too -- that is the protocol describing the root seam correctly, not a test accommodation.

Teeth proven by deleting the refusal branch: both new gates fail.
