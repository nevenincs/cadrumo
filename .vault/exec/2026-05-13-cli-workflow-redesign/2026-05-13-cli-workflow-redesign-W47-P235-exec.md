---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W47.P235'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W47.P235`

Thin-CLI-exposure + tightening loop. The `bindings` sub-Typer
registers under the existing `aeat app modelo` Typer (no new
root verb), nine new locale keys land in all four locale files
with real translations, and `ty check` is clean.

## Description

CLI registration: `_modelo.py` exposes `bindings_app` as a
Typer registered into the parent via `app.add_typer(bindings_app,
name="bindings")`. The root contract remains `aeat config` +
`aeat app` only; the new sub-Typer sits underneath `aeat app
modelo`.

Localization: each locale file (`es`, `en`, `hu`, `ca`) gains
nine new keys under `cli.app.modelo.bindings.*`:

- `app_help`
- `as_of_help`
- `list_help`
- `missing_help`
- `modelo_help`
- `override_help`
- `period_help`
- `preview_help`
- `year_help`

All four files carry distinct real translations so the locale
honesty test passes; locale parity is unchanged from before the
wave (the residual 8-key codebase-to-locale gap is pre-existing).

Type checking: `uv run --no-sync ty check
src/aeat/entrypoints/cli/_modelo.py` reports `All checks
passed!`.

Tightening loop concurrent with this wave: dev-process metadata
(wave / phase / ADR references) removed from source code across
the W31 / W33 / W37 / W47 modules. Source code describes what
the code IS, not the wave that produced it. Wave references
remain only in commit messages and vault exec records.

Closed plan rows: `W47.P235.S1405`, `W47.P235.S1406`,
`W47.P235.S1407`, `W47.P235.S1408`, `W47.P235.S1409`,
`W47.P235.S1410`.

## Tests

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py
src/aeat/entrypoints/cli/test_registry_corpus.py
src/aeat/locales/test_locale_translation_honesty.py -q` — 32 /
32 pass.
