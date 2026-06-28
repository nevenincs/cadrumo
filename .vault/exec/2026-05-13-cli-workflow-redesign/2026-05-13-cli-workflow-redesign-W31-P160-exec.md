---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W31.P160'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W31.P160`

Thin-CLI-exposure phase + tightening loop for the wave. The CLI
surface lives under the existing `aeat app registry` Typer (no new
root verb), the 18 new locale keys land in all four locale files
with real translations, and `ty check` reports clean against the
new modules.

## Description

CLI registration: `_registry_corpus.py` exposes
`citations_app` and `manuals_app` Typer instances. `registry.py`
adds them under the parent `app` via
`app.add_typer(citations_app, name="citations")` and
`app.add_typer(manuals_app, name="manuals")`. The root contract
remains `aeat config` + `aeat app` only; the two new sub-Typers
sit underneath `aeat app registry`.

Localization (Spanish-first authoritative; English, Hungarian,
and Catalan all carry real translations distinct from English so
the locale honesty test passes):

- `src/aeat/locales/es.yml`, `en.yml`, `hu.yml`, `ca.yml` each
  gain 18 new keys under `cli.registry.citations.*` and
  `cli.registry.manuals.*` plus an `errors.unknown_section`
  string. The codebase-to-locale parity gap shrinks from 26
  missing keys to 8 missing keys across every locale; the
  remaining 8 are pre-existing glob-pattern gaps from other
  waves and are not in W31 scope.

Type checking: `uv run --no-sync ty check
src/aeat/entrypoints/cli/_registry_corpus.py
src/aeat/entrypoints/cli/_stdio.py` reports `All checks
passed!`. One narrowed `# ty: ignore[invalid-assignment]`
suppression on the `RuleKind` runtime-narrowing assignment is
documented inline.

Error / logging discipline tightening:

- `_registry_corpus.verify_citations_cmd` catches the specific
  `NormativeParseError` (not bare `Exception`) and logs the
  swallow at warning level with structured `extra` context.
- `_stdio._reconfigure_stream` emits `_LOGGER.debug(...)` for
  both the no-`reconfigure()` and the `OSError`/`ValueError`
  decline cases. No silent-swallow paths remain.

Closed plan rows: `W31.P160.S0955`, `W31.P160.S0956`,
`W31.P160.S0957`, `W31.P160.S0958`, `W31.P160.S0959`,
`W31.P160.S0960`.

## Tests

`uv run --no-sync pytest
src/aeat/entrypoints/cli/test_registry_corpus.py
src/aeat/entrypoints/cli/test_stdio.py
src/aeat/locales/test_locale_translation_honesty.py -q` —
20 / 20 pass.
