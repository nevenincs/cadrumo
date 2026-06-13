---
step_id: S115
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S115 — wrap locales-CLI typer.echo in tr()

## Outcome

All seven `typer.echo` calls in `src/aeat/locales/cli.py` now route through `tr()`
under the `locales.cli.*` namespace:

- `locales.cli.audit.file_drift` (file-level drift summary)
- `locales.cli.audit.key_missing` (per-key missing line)
- `locales.cli.audit.key_extra` (per-key extra line)
- `locales.cli.audit.file_ok` (clean-file confirmation)
- `locales.cli.scaffold_updated` (scaffold completion)
- `locales.cli.set.updated` (set-command confirmation)
- `locales.cli.remove.removed` (remove-command confirmation)

Locale keys scaffolded via `python -m aeat.locales scaffold` and authored in
all four locale files. Audit: all four locales ok. Commit `1926f5cc4`.

## Files touched

- `src/aeat/locales/cli.py`
- `src/aeat/locales/{es,en,ca,hu}.yml` (locales.cli.* keys)

## Verification

`vault plan step check S115` applied. Locale audit: all four locales ok.
