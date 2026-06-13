---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase2` `step11`

Reduced Modelo 100 borrador parsing from hardcoded summary authority to
observed PDF data extraction with optional registry-profile coverage
validation.

- Modified: `src/aeat/adapters/inbound/borrador/__init__.py`
- Modified: `src/aeat/adapters/inbound/borrador/_extractors/__init__.py`
- Modified: `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py`
- Modified: `src/aeat/adapters/inbound/borrador/_parser.py`
- Modified: `src/aeat/adapters/inbound/borrador/_schema.py`
- Modified: `src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The extractor no longer owns a Modelo 100 summary casilla tuple. It scans
printed four-digit casilla rows and returns observed values only. When a
registry extraction profile is supplied, parsing filters to that profile's
target casillas and fails hard if observed coverage is below the registry
minimum.

`BorradorObservation` records the applied registry extraction profile id and
coverage when a profile is used. The filing-named alias was removed.
Parser tests no longer restate the removed summary scope. They exercise artefact detection, observed-row
extraction, profile filtering, coverage failure, sparse PDFs, and override
behaviour.

## Tests

- Static text discovery over `src\aeat\adapters\inbound\borrador`
  returned no removed authority names in the active parser surface.
- `uv run pytest src\aeat\adapters\inbound\borrador -q`
  passed: 11 tests.
- `uv run ruff check src\aeat\adapters\inbound\borrador`
  passed.
- `uv run ty check src\aeat\adapters\inbound\borrador`
  passed.
