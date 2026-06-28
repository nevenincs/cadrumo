---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W06.P19.S116'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-convention-hardening-audit]]'
---

# declaracion-extraction-architecture W06.P19.S116

Re-audited declaration parser and Modelo 840 tests for tautological assertions
and hardened the synthetic parser tests against registry drift.

- Modified: `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Description

The Modelo 840 label test had already been hardened in `W06.P19.S119` by
checking exact printed-form labels from the official AEAT PDF before matching
registry regexes.

The remaining tautology risk was in synthetic parser tests that generated
expected PDF values from the same extraction profile the parser resolves. Those
tests now independently pin the expected target casilla IDs for Modelo 130,
Modelo 111, current Modelo 123, and historical Modelo 123 before generating the
PDF. A missing, empty, or accidentally changed profile can no longer satisfy the
round-trip assertion just because expected values were derived from the changed
profile.

## Tests

- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\domain\calculations\registry\test_modelo_840_registry.py`
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\domain\calculations\registry\test_modelo_840_registry.py -q`
