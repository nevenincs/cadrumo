---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-calculation-authority-evidence-tiering-adr]]'
---



# `calculation-truth-registry` `phase-4r` `renta-parity-tape`

Added the first Modelo 100 scenario/tape parity coverage over the restored
parity harness.

- Created: `src/aeat/domain/calculations/registry/test_modelo_100_parity_tapes.py`

## Description

The new test creates a runtime XLSX parity workbook and executes it through the
scenario/tape harness against the validated Modelo 100 ejercicio 2025 registry
snapshot. The scenario covers Renta economic-activity direct-estimation
outputs and payments-on-account outputs, including casillas `0180`, `0224`,
`0235`, `0604`, and `0609`.

Before running the tape, the test verifies that the selected registry snapshot
classifies `modelo-100-renta-web-open` as an unauthenticated read-only Open
simulator with synthetic data allowed. Authenticated Renta surfaces remain
outside the scenario and stay observation-only.

The tape is saved and replayed in the test so drift in the current registry
runtime will fail the parity check.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_parity_tapes.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_100_parity_tapes.py src\aeat\domain\calculations\registry\test_parity_tapes.py -q`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\test_modelo_100_parity_tapes.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\test_modelo_100_parity_tapes.py src\aeat\domain\calculations\registry\_parity_tapes.py src\aeat\entrypoints\cli\registry.py`
  passed.
