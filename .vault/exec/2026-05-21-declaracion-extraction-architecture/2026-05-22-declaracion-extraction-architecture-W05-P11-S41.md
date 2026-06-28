---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W05.P11.S41'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-research]]'
---

# `declaracion-extraction-architecture` `W05.P11.S41`

Confirmed the committed registry snapshot-build gate.

## Verification

`uv run --no-sync pytest src/aeat/domain/calculations/registry/test_committed_registry.py`
passed: 41 tests.

The gate validates the committed calculable registry snapshots exercised by
`test_committed_registry.py`. The remaining W05.P11 rows for per-modelo
declaracion PDF round-trip fixtures remain open.
