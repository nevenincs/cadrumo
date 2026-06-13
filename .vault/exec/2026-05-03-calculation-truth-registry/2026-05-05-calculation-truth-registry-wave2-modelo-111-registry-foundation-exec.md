---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-04-live-filing-data-capture-adr]]'
---



# `calculation-truth-registry` `Wave 2` `Modelo 111 registry foundation`

Added the first centralized Modelo 111 registry slice for the current AEAT
surface.

- Modified: `registry/aeat/legal/irpf.toml`
- Created: `registry/aeat/modelos/111.toml`
- Created: `corpus/aeat_official/instructions/modelo_111/files/modelo-111-instrucciones.html`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The Wave 2 work now has reviewed source catalogue entries for the official
Modelo 111 instructions and current record-design workbook. The legal catalogue
now includes the IRPF withholding declaration basis used by the new Modelo 111
registry definition.

The new Modelo 111 registry definition covers the current 30-casilla
`2019-y-siguientes` liquidation surface, the supported calculations for casillas
28 and 30, the record-design export layout, submitted-file and declaration-PDF
extraction profile declarations, static official cross-reference guard,
workbook layout evidence, verification expectation, application links, and 2026
quarterly deadline windows.

The implementation deliberately does not preserve the old 21-casilla
calc-verify simplification. The official AEAT instructions and current
record-design workbook define the current surface.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_registry_schema.py -q` passed.
- `uv run pytest src\aeat\domain\calculations\registry -q` passed.
- `uv run ruff check src\aeat\domain\calculations\registry\test_committed_registry.py` passed.
- `uv run ruff check registry\aeat\modelos\111.toml registry\aeat\legal\irpf.toml src\aeat\domain\calculations\registry\test_committed_registry.py` passed.
- `uv run ty check src\aeat\domain\calculations\registry` passed.
- `git diff --check` on the touched registry, test, plan, and corpus files passed.
