---
step_id: S107
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S107 — describe BadParameter localized via tr()

## Outcome

Replaced `raise typer.BadParameter(message)` at `src/aeat/entrypoints/cli/_modelo.py:362`
(the describe registry-snapshot error fallback path) with:

```python
raise typer.BadParameter(tr("cli.app.modelo.describe.period_error", message=message)) from exc
```

Added locale key `cli.app.modelo.describe.period_error` with `%{message}` interpolation slot
to all four locales (en, es, ca, hu) via `python -m aeat.locales set`.

## Files touched

- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`uv run --no-sync python -m aeat.locales audit` → ca.yml: ok, en.yml: ok, es.yml: ok, hu.yml: ok
