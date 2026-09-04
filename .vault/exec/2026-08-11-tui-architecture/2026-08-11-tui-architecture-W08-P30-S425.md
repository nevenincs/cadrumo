---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:8fd75e8ddf5bf6cd6abf1684f3e55ba4ed18f2c331a3396bba08c0f63a323687'
step_id: 'S425'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Give an empty Home a keyboard entry point. MEASURED 2026-09-04 by the vacuity guard added to the tab-reachability gate: on a fresh profile Home offers NO focusable control whatsoever. Its three tables set display=False when they hold no rows, so the destination an operator lands on first has nothing to Tab to and nothing to press Enter on -- the workbench is keyboard-dead until the profile has data. This was invisible to the reachability assertion because a subset check over an empty focusable set is trivially true, which is why the guard rather than the check found it. Whatever lands must keep a control reachable when every zone is empty or refused, and the gate must keep refusing a destination that offers nothing.

## Scope

- `src/cadrumo/entrypoints/tui/home.py and src/cadrumo/entrypoints/tui/tests/test_workbench_accessibility.py`

## Changes

- `M` `src/cadrumo/entrypoints/tui/home.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_workbench_accessibility.py`
- `verify:` `uv run --no-sync pytest -q -m integration src/cadrumo/entrypoints/tui/tests/test_workbench_accessibility.py` -> `pass`

## Notes

Found by the vacuity guard rather than by the assertion it guards: on a fresh profile every
Home zone is empty or refused, all three tables set display=False, and the destination an
operator lands on first had NOTHING focusable -- keyboard-dead until the profile holds data.
The reachability check could not see it because a subset over an empty set is trivially true.

The page container now takes focus in that state, so a keyboard operator arrives somewhere,
can read and scroll the zone states, and Escape still returns.
