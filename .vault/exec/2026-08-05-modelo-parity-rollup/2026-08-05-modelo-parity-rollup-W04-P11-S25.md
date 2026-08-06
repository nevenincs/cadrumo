---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:53f7e379c6e49fb7f474ec168984b7ea08c6680ee9baea4c39e622f01de8e514'
step_id: 'S25'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---
# Record exact oracle enrollment only for certified coordinate and payload mappings

## Description

- Enroll only coordinate and payload mappings already certified by the registry's grounded evidence and external-oracle boundary.
- Keep the enrollment revision-specific and do not expand it to unresolved annual M100 2025/0A rows.

## Outcome

The final oracle census measured 1,261 reconciled casillas and 61 independently checked casillas backed by 24 bundled oracle payloads. All 61 declared grounding claims matched enrolled evidence; unattributed oracle payloads and unmatched oracle evidence were both zero. No ungrounded M100 2025/0A enrollment was added.

## Notes

The enrollment is evidence coverage, not a correctness claim for every casilla. The annual matrix remains provisional for M100 2025/0A, with casillas 0150, 0613, and 1481 retained for SOL adjudication.
