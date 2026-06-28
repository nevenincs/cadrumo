---
tags:
  - "#exec"
  - "#casilla-db"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-casilla-db-plan]]"
---

# casilla-db phase1 step4

Curated the initial canonical casilla corpus for the three requested modelos.

- Created: `corpus/casillas/modelo_130/2025Q4.json`
- Created: `corpus/casillas/modelo_303/2025Q4.json`
- Created: `corpus/casillas/modelo_390/2025.json`

## Description

Added real, non-synthetic catalogue files with source provenance,
cross-references, reviewer metadata, and trilingual label/help fields for
`MODELO_130`, `MODELO_303`, and `MODELO_390`.

## Tests

`uv run aeat casillas verify` passed for all three checked-in catalogues.
