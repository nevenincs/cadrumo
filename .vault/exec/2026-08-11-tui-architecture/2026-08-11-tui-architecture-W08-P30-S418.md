---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:56dc656950fb782f8f66bd4a5ea0da0903bf5b5c6308b539152e07602b1a47f7'
step_id: 'S418'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
