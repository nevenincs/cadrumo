---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:44fb02dca2bc2a3e006eefc40f76ee681c49e8d1127eb0e2c05b7761b6daaf7b'
step_id: 'S44'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M369 calculation-mode OSS Union-scheme cuota-total enrollment test across two renta years

## Scope

- `src/aeat/application/calculations/tests/test_modelo_369_oss_fidelity.py`

## Description

- Rebaseline stale-open M369 enrollment-test row against the current test suite.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M369 OSS test.
- Update the plan row to the actual calculation-mode M369 proof.

## Outcome

- `test_modelo_369_oss_fidelity.py` already proves calculation-mode OSS Union-scheme cuota-total continuity for 2024 and 2025.
- No product code changed in this step.

## Notes

- This does not claim data-fidelity-only class, IOSS, or import-scheme coverage.
