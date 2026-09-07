---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:623446fb98acacbd30ca371a4320aa08319bbaf2eeeb2b2761cb85f7c2cfb326'
step_id: 'S65'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

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
