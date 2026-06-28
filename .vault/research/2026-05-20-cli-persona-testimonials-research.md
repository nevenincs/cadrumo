---
tags:
  - '#research'
  - '#cli-persona-testimonials'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-cli-persona-testimonials-audit]]"
---



# `cli-persona-testimonials` research: `cli-i18n-naked-string-remediation-inventory`

Brief description of what was researched, why, and how it relates to
`cli-persona-testimonials`.

## Findings

Adapt format based on content.


## Context

## Purpose

Complete inventory of operator-facing naked strings (text bypassing
`tr()` localisation) across the `aeat` CLI surface, plus the remediation
plan. Drives the i18n wave (task #519). Read-only sweep following the
persona-testimonial audit.

## Localisation contract

- `core/i18n.tr(key, **kwargs)` resolves a key against
  `src/aeat/locales/{es,en,ca,hu}.yml`.
- `core/errors/_registry.py::resolve_error_message`: for an `AeatError`
  subclass it returns `error.args[0]` VERBATIM if a literal positional
  message was passed; renders `error.translated_message` through `tr()`
  when set; else falls back to `tr(code.message_key)`.
- A NAKED error = `AeatError` raised with a literal positional message
  and no `translated_message`. Fix = raise with
  `translated_message="<key>"` + `context={...}` (no positional), or for
  boundary classes drop the positional so the registered `message_key`
  renders.
- Naked help/echo = `help="literal"` / `typer.echo("literal")`; fix =
  `tr("<key>")`.
- New keys: `python -m aeat.locales scaffold`, fill `es/en/ca/hu`
  values, `python -m aeat.locales audit` for parity. Never hand-edit yml
  structure.

## Inventory — 35 naked strings, 6 clusters

### Cluster A - IdentityError (core/identity/_documents.py, 10 strings)

NIF/NIE/CIF validation; surfaces via `aeat config profile create`.
Lines 126,131,140,145,155,161,166,173,203,206. Key family
`errors.identity.*`. Fix: per-site `translated_message` + `context`.

### Cluster B - _modelo.py typer.BadParameter (11 strings)

Lines 359,363,587,695,697,1239,1257,1600,1651,1659,1888,1895. Keys
under `cli.app.modelo.work.*` / `.aggregate.*` / `.bindings.*` /
`.filing_record.*`. Fix: `typer.BadParameter(tr("<key>", **kwargs))`.
NOTE: `_modelo.py` carried concurrent-agent WIP earlier — re-check
git-clean before editing.

### Cluster C - ledger import (3 strings)

`application/ledger/_actions.py:333` + `:1836`
("The ledger file cannot be imported: ...") and
`adapters/inbound/financial/providers/_base.py:156`
("source file does not exist: ..."). Keys
`errors.transaction.ledger_import_failed`,
`errors.transaction.ledger_import_requires_bucket` (_actions.py:368),
`errors.financial.source_file_not_found`. Localise wrapper AND source
raise so the embedded detail is also Spanish.

### Cluster D - CLI boundary errors (entrypoints/cli/_errors.py, 2 strings)

`:89` `CliValidationBoundaryError` and `:126`
`CliUnexpectedBoundaryError` pass literal positional English. Highest
impact - render on every leaked validation error / unexpected crash.
Fix: drop the positional so the boundary falls through to the
registered `message_key`
(`errors.refused.refused_cli_validation_boundary`,
`errors.internal.internal_cli_unexpected_boundary`). Verify those keys
carry es/en/ca/hu translations.

### Cluster E - censo sync (application/user_profile/_censo_sync.py, 4 strings)

Lines 171,218,241 (`CensoNotAvailableError`) and 294
(profile-not-found). Keys `errors.censo.*`. Surfaces via
`aeat config profile census refresh/show/compare/apply`.

### Cluster F - _app_live.py typer.BadParameter (7 strings)

Lines 27,569,574,826,900,961,1091. Enum/surface validation for
`aeat app live verify|portals|borrador`. Keys `cli.app.live.*`
(826/900 share one key).

### Additional singletons

- `entrypoints/cli/__init__.py:269` - startup missing-dependency echo;
  key `cli.root.startup_import_error`.
- `_config/__init__.py:1567` - auth-diagnostic-not-found; a
  `cli.config.auth.diagnostics.not_found` key already exists - reuse.
- `_config/__init__.py:1829,1889` - bucket-history `--since/--until`
  validation; keys `cli.config.bucket.history.*`.

## UNSURE - trace before action

- `_config/__init__.py:1419` - `CliRefusedBoundaryError(str(exc))`
  wrapping a plain-`ValueError` English message; likely naked.
- `_config/__init__.py:1764` - `CliRefusedBoundaryError(str(exc))` from
  an unspecified service; trace call sites.
- `_config/_google.py` - ~18 `CliRefusedBoundaryError(str(exc))`
  wrapping `google-auth` library exceptions (always English). The Google
  config surface IS operator-facing (Drive sync setup).
- `core/config.py:951,983,987,996` - `CoreValidationError` in Settings
  validators; naked by contract, but surface before locale resolution
  warms up. `core/config.py` had concurrent WIP - re-check.

## Execution discipline

Fix cluster by cluster; each a commit paired with a CLI surface test
asserting Spanish rendering. Code edits (raises) parallelise across
files; locale yml edits serialise - scaffold all keys in one batch, fill
es/ca/hu/en, `audit`. Re-verify git-clean on `_modelo.py` and
`core/config.py` before editing those. Sequence: D (cleanest, highest
impact) → C, E, A (error clusters) → B, F (BadParameter clusters) →
singletons → UNSURE resolution.

