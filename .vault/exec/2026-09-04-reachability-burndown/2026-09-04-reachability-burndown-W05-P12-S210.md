---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:e62400575530a4ead92a674b4c18b5cc2e77609f7a935654308f4ed20ffe729c'
step_id: 'S210'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the wholly unused did_page_required public alias and export from filing export parity while retaining the private canonical DID-page predicate and the live shared suppression path consumed by parity derivation and record rendering.

## Scope

- `Filing export parity and focused renderer/parity tests`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `src/cadrumo/application/filing/_export_parity.py`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/_export_parity.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 -m "" --basetemp <isolated-workspace-temp> <two focused DID account tests>` -> `pass` (4 parametrized cases passed)
- `verify:` `rg -n '^did_page_required\\s*=' ...` and fixed-string export search -> `pass` (public alias and export absent)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `findings` (317 exact unused symbols; target absent)

## Notes

The exact unused-symbol count fell from 318 immediately before S210 to 317 after removal of the public alias; the live graph otherwise remained at 65 unreachable modules, 18 orphaned tests, and 2028/2094 shipped modules reachable.
