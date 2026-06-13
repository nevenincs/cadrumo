---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S119'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S119

Hardened the Modelo 840 printed-form label grounding test against an
over-broad registry regex.

- Modified: `src/aeat/domain/calculations/registry/test_modelo_840_registry.py`

## Description

The test already extracted text from the official AEAT printed-form PDF and
matched each registry `label_pattern` against that source. This step added an
independent assertion that the official PDF text contains the exact printed
labels `14 Ejercicio` and `15 Declaración de` for the targeted casillas before
checking the registry regex. That keeps the test source-grounded and avoids a
regex-only tautology.

## Tests

- `uv run --no-sync ruff check src\aeat\domain\calculations\registry\test_modelo_840_registry.py`
- `uv run --no-sync pytest -x src\aeat\domain\calculations\registry\test_modelo_840_registry.py -q`
