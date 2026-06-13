---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S14'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P05.S14`

Updated the new config repair attribution help text through the locale module CLI and verified locale catalogue parity.

- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/audit/2026-05-22-secure-object-integrity-P05-S14-review.md`

## Description

The locale workflow used `uv run python -m aeat.locales audit` to detect that `cli.config.repair.integrity_attribution_help` was missing from all locale catalogues. The key was then added through `uv run python -m aeat.locales scaffold`, which produced scaffolded entries in English, Spanish, Catalan, and Hungarian.

The scaffold placeholders were replaced with locale-specific text describing the command's metadata-only grouping of undecryptable secure-object rows. The wording avoids payload disclosure promises beyond the command's safe metadata contract and stays aligned with the attribution behavior implemented earlier in the plan.

## Tests

Focused gates passed:

- `uv run python -m aeat.locales audit`
- `uv run python -m aeat.locales scaffold --check`
- `uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py`

Mandatory scoped review found no critical or high blockers.

Review audit: `2026-05-22-secure-object-integrity-P05-S14-review`.
