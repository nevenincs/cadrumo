---
tags:
  - '#exec'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - '[[2026-05-01-modelo-347-calc-verify-plan]]'
---

# `modelo-347-calc-verify` `implementation` `phase3-verifier-cli`

Added Tier-S summary parity verification and CLI dispatch for Modelo 347.

- Created: `src/aeat/application/verification/_verify_summary.py`
- Created: `src/aeat/application/verification/test_verify_summary.py`
- Modified: `src/aeat/application/verification/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `tests/integration/test_kent_workflows.py`

## Description

`verify_modelo_347_summary` compares printed resumen casillas `01` through `04` with extracted detail-record count, annual operation sum, cash-record count, and cash total. It returns `VERIFIED` on parity and `NEEDS_REVIEW` with `CORRECTNESS_DIVERGENCE` discrepancies on mismatch. The CLI routes Modelo 347 declaration imports to this verifier before attempting formula-ruleset resolution.

## Tests

Unit tests cover verified parity, total mismatch, and count mismatch. Kent CLI tests cover 2024/2025/2026 happy paths, resumen mismatch, and row drift.
