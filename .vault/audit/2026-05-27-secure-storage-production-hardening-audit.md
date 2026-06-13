---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---



# `secure-storage-production-hardening` audit: `locale setter code review`

## Scope

Reviewed the canonical locale setter slice for the `python -m aeat.locales`
maintenance path:

- `src/aeat/locales/cli.py`
- `src/aeat/locales/manager.py`
- `src/aeat/locales/test_parity.py`

The review focused on preserving locale-file structure, keeping the CLI under
the canonical locale maintenance entrypoint, avoiding undeclared runtime
dependencies, and preventing writes outside the configured locale directory.

## Findings

No open findings after remediation.

Resolved during review:

- LOCALE-SET-001 | MEDIUM | The first setter pass accepted raw locale path
  fragments. `LocaleManager.set_locale_value()` now rejects path-like locale
  names, restricts writes to existing locale stems under `locales_dir`, resolves
  the target path, and verifies containment before reading or writing.

Residual risk:

- The focused tests exercise `LocaleManager.set_locale_value()` directly rather
  than invoking the exact Typer command path. The command is a thin pass-through;
  a future command-level test would catch argument-order drift without changing
  the current behavior.

## Recommendations

Keep locale value edits on the canonical `python -m aeat.locales set` path. Do
not mutate locale YAMLs by hand except for non-semantic formatting repair after
the CLI has performed the string change.

Validation performed:

- `uv run pytest src/aeat/locales/test_parity.py::test_set_locale_value_updates_one_leaf src/aeat/locales/test_parity.py::test_set_locale_value_rejects_locale_path_traversal -q`
- `uv run pytest src/aeat/core/i18n/test_placeholder_parity.py -q`
- `uv run ruff check src/aeat/locales/manager.py src/aeat/locales/cli.py src/aeat/locales/test_parity.py`

Known unrelated shared-tree state: `uv run python -m aeat.locales audit` fails on
`profile.descendiente.custodia_compartida_prorrata_applied` extra locale keys
introduced by concurrent profile/family WIP. That failure is outside this slice
and was not staged for this commit.
