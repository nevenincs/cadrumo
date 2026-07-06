---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S62'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# complete the declared-but-unwired modelo-210-2025-calculation engine link so a real IRNR calculation runs per A5-210 (TRLIRNR RDLeg 5/2004) (vaultspec-high-executor)

## Scope

- `src/aeat/domain/calculations/engines/_modelo_210.py`

## Description

- Rebaseline live M210 calculation enrollment with RAG and targeted test discovery.
- Confirm the live M210 registry calculation drives 2025 and 2026 annual GB/general rental-income scenarios through the real engine.
- Close the row as already satisfied by current code; no source edit was needed for this record.

## Outcome

Closed as current-code satisfied. The live enrollment test exercises a real M210 calculation in two renta years and the registry authorization fragment already declares the matching year set.

## Notes

Verification: `uv run --no-sync pytest -q -n 0 src/aeat/application/calculations/tests/test_modelo_210_irnr_continuity.py src/aeat/application/calculations/tests/test_modelo_151_beckham_cuota_continuity.py src/aeat/application/calculations/tests/test_modelo_347_informativa_fidelity.py src/aeat/application/calculations/tests/test_modelo_184_informativa_fidelity.py src/aeat/application/calculations/tests/test_modelo_036_censal_continuity.py src/aeat/core/access_gate/tests/test_authorization_manifest.py src/aeat/tests/test_modelo_authorization_gate.py` returned 42 passed.
