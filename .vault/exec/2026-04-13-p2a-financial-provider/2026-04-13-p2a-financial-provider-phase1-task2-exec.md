---
tags:
  - "#exec"
  - "#p2a-financial-provider"
date: "2026-04-13"
modified: '2026-04-13'
related:
  - "[[2026-04-13-p2a-financial-provider-plan]]"
---

# `p2a-financial-provider` `phase-1` `task-2`

Wired the CLI/settings surface and added fixture-driven verification.

- Modified: `env/.env.example`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_smoke.py`
- Created: `src/aeat/entrypoints/cli/financial/`
- Created: `tests/fixtures/financial/`

## Description

Added the `aeat financial ingest` Typer sub-app, registered it on the root CLI, introduced the financial ingest settings fields, aligned `.env.example`, and generated the CSV/XLSX/OFX fixture corpus required by issue `#73`. Added colocated unit tests covering model round-trips, provider detection, bank CSV layouts for BBVA/Santander/CaixaBank/Revolut, XLSX header detection, OFX parsing, and CLI JSON output.

## Tests

Branch-wide verification passed with `just lint`, `just typecheck`, `just test`, and `just hooks`.
