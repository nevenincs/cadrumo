---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:930e76a6236dc76c35911a09342e266c4a81d4494317e98dc6445d37ed111240'
step_id: 'S177'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unreached single-profile custody summary reader displaced by the live anchored multi-profile summary scan, and migrate its security assertions to exercise the canonical list path without preserving the redundant public helper.

## Scope

- `profile custody capsule reader and tests`
- `live profile-summary inventory tests`
- `production-metastate gate`
- `live unused-symbol measurement`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/custody/capsule.py`
- `M` `src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule.py`
- `verify:` `rg -n --glob "*.py" "\\bload_committed_profile_custody_summary_witness\\b" src/cadrumo dev` -> `pass`
- `verify:` `uv run ruff check src/cadrumo/adapters/persistence/storage/custody/capsule.py src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule.py` -> `pass`
- `verify:` `uv run pytest src/cadrumo/adapters/persistence/storage/custody/tests/test_capsule.py -q -n0` -> `pass` (23 passed)
- `verify:` `uv run pytest src/cadrumo/application/user_profile/tests/test_profile_summary_inventory.py -q -n0` -> `pass` (9 passed)
- `verify:` `git diff --check -- <S177 paths>` -> `pass`
- `verify:` `uv run python -m dev.quality.production_metastate` -> `fail` (three live findings)
- `verify:` `uv run python -m dev.quality.unused_symbol_coverage` -> `fail` (355 exact symbols; 18 orphan test modules)

## Notes

The zero-target metastate gate improved from four findings to three. The exact unused signal improved from 356 to 355 while orphan tests remained at 18. The remaining data-file replacement finding in the same module was left intact because its shipped test-facade dependency requires separate ownership analysis.
