---
step_id: S83
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S83 — describe label tr() wrapping

## Outcome

In `src/aeat/entrypoints/cli/_modelo.py` at the `describe_modelo` command
(around line 363), wrapped all 11 tab-separated label strings in `tr()` calls
using the key pattern `cli.app.modelo.describe.label_*`:

- `label_modelo`, `label_title`, `label_official_name`, `label_tax_domain`
- `label_cadence`, `label_revision`, `label_revision_ids`, `label_periods`
- `label_casillas`, `label_bindings`, `label_formulas`

Added all 44 locale entries (11 keys × 4 locales: en, es, ca, hu) via
`python -m aeat.locales set`.

## Files touched

- `src/aeat/entrypoints/cli/_modelo.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`uv run --no-sync python -m aeat.locales scaffold --check` reported ok for all
four catalogues. Step closed via `vault plan step check`.
