---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:ce737f2d1918aecfcb31bd9d26c3cacdd13b35e6660a68ae1966de78ffdd6ea3'
step_id: 'S11'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Remove replay-specific fields from every payload and schema projection

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`

## Description

- Verify no replay-specific fields or schema projections remain in `_modelo_aux_payloads.py`.

## Outcome

- The only replay payload was `ModeloAuditReplayResult`, removed with its `@register_schema("modelo.audit.replay")` registration in P03.S08 (the forced consumer sweep of the command removal). A grep confirms zero remaining `replay` references in `_modelo_aux_payloads.py`. No further change required for this step.

## Notes

- This step's substantive removal landed in commit `87f49c5d2f` (S08); S11 is the verification that the payload/schema surface is clean.
