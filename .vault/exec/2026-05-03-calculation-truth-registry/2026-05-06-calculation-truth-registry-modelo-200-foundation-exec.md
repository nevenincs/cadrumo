---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `modelo-200` `foundation`

Added the Modelo 200 annual corporate-tax foundation to the registry and
connected its annual settlement to Modelo 202 instalment observations.

- Created: `registry/aeat/modelos/200.toml`
- Modified: `registry/aeat/legal/is.toml`
- Created: `corpus/normatives/html/ley-27-2014-art-41.html`
- Created: `corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf`
- Modified: `src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`

## Description

The new Modelo 200 registry entry declares the annual IS identity, the
2024-and-later revision, legal and source authorities, official casillas 00592
and 00599, and the cross-model relation that aggregates Modelo 202 periods
1P/2P/3P into the annual final-settlement calculation.

The calculation for casilla 00599 consumes official casilla 00592 and the
relation-resolved Modelo 202 aggregate directly. No intermediate casilla or
Python calculation authority is introduced.

Ley 27/2014 article 41 is catalogued as the legal basis for deducting
withholdings, payments on account, and instalment payments from corporate-tax
liability. The AEAT Modelo 200 manual PDF is committed as official guidance for
source-citation validation.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
- `uv run ty check src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py`
