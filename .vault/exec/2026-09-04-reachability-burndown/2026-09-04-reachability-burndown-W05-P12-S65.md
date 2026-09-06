---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:ee8717fbfd582f8df5208f538512ad955f02df97701e2de1795d5b311dfa6b88'
step_id: 'S65'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Wire the optional-extra classifier as the import-failure backstop it was written to be: the console-script bootstrap now catches a ModuleNotFoundError escaping the CLI, classifies it against the declared optional-extras inventory, and routes a declared optional package through the same require path a feature boundary uses so the operator gets an actionable install message instead of a deep-stack import failure, while a module outside the inventory re-raises untouched as the broken installation it is and an extra that is actually installed also re-raises so a genuine deep-import failure inside it is never mislabelled

## Scope

- `src/cadrumo/entrypoints/_cli_main.py`

## Changes

- `M` `src/cadrumo/entrypoints/_cli_main.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints` -> `pass`
- `verify:` lookup returns the owning extra for a declared package, `None` for an
  undeclared one, and attributes a deep import to its owner

## Notes

The backstop deliberately does not mask two cases. A module outside the declared
inventory re-raises unchanged, because its absence is a broken installation
rather than a configuration choice. And an extra that IS installed also
re-raises, so a deep-import failure inside an installed package is not reported
as "install the extra" -- confirmed here, where playwright is present and the
simulated `playwright.async_api` failure fell through to the re-raise.
