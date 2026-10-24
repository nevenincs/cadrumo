---
tags:
  - '#exec'
  - '#desktop-navigation-register'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:06aa01b56dda3bf1ce1e9fb8803f65b61219db69ce31f7694cbc07685c607c33'
related:
  - "[[2026-10-24-desktop-navigation-register-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `desktop-navigation-register` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S06` `A` `src/cadrumo_client/contracts/navigation.toml`
- `S06` `A` `src/cadrumo_client/contracts/navigation.py`
- `S06` `A` `src/cadrumo_client/contracts/tests/navigation_vectors.json`
- `S06` `A` `src/cadrumo_client/contracts/tests/test_navigation_register.py`
- `S06` `A` `src/cadrumo_client/contracts/tests/test_navigation_links.py`
- `S06` `M` `pyproject.toml`
- `S06` `M` `dev/tests/test_wheel_content_boundary.py`
- `S06` `M` `dev/locales/manager.py`
- `S06` `M` `src/cadrumo/locales/en/common.yml`
- `S06` `M` `src/cadrumo/locales/es/common.yml`
- `S06` `M` `src/cadrumo/locales/ca/common.yml`
- `S06` `M` `src/cadrumo/locales/hu/common.yml`
- `S06` `verify:` `pytest src/cadrumo_client/contracts/tests/test_navigation_register.py src/cadrumo_client/contracts/tests/test_navigation_links.py` -> `pass`
- `S06` `verify:` `pytest dev/tests/test_wheel_content_boundary.py -k required_functional_members` -> `pass`
- `S06` `verify:` `lint-imports --config .importlinter` -> `pass`
- `S06` `verify:` `ruff check and ruff format --check on touched files` -> `pass`
- `S06` `verify:` `ty, pyrefly and basedpyright on touched files` -> `pass`
- `S06` `verify:` `pytest dev/locales/tests` -> `fail`

## Notes

- `S06` dev/locales/tests: 4 failures in `test_desktop_chrome,` `test_dict_constant_naming_convention,` `test_modelo_schema_runtime_localization` and `test_audit` product identity; none names a navigation key; they sit in files other sessions are editing. Locale spelling flags ca Instal·lació and es/ca Python shell for navigation labels exactly as for the existing tui.destination.installation and desktop.rail.python cells.
