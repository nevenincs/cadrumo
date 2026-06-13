---
step_id: S81
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S81 — ledger id-prefix catch-all through tr()

## Outcome

At `src/aeat/entrypoints/cli/_ledger.py` line 284, replaced the raw
`raise _bad(raw_message) from exc` catch-all with
`raise _bad(tr("cli.ledger.errors.id_prefix_unknown", message=raw_message)) from exc`.

Added locale key `cli.ledger.errors.id_prefix_unknown` with `%{message}`
interpolation to all four catalogues (en, es, ca, hu) via
`python -m aeat.locales set`.

## Files touched

- `src/aeat/entrypoints/cli/_ledger.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`uv run --no-sync python -m aeat.locales scaffold --check` reported ok for all
four catalogues. Step closed via `vault plan step check`.
