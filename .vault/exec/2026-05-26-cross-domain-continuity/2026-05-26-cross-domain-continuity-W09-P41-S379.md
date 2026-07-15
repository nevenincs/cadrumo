---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S379'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-S372-M349 land OperadorRow .nif crash fix plus detail_rows schema widening plus regression test exercising the full row materialisation per AEAT M349 diseno de registro

## Scope

- `closed by 7ff039f4c: existing domain row-id guards confirm the OperadorRow nif_comunitario crash path is covered`
- `and the landed work widens CLI calculation/revision JSON schemas with DetailRowPayload detail_rows materialised from real row models`
- `M349 --row operador JSON calculate and revision now expose full row fields including nif_comunitario`
- `no new reexports were added`
- `verified by 17 payload tests`
- `11 M349 display/replay tests`
- `94 JSON schema conformance tests`
- `the focused M349 CLI row regression`
- `2 domain row-id guards`
- `ruff`
- `and diff check`
- `ty remains blocked by the shared-tree missing stubs directory`
- `src/aeat/entrypoints/cli/_modelo_revision_payload_parts.py src/aeat/entrypoints/cli/_modelo_payloads.py src/aeat/entrypoints/cli/_modelo_work_revision_payloads.py src/aeat/entrypoints/cli/_modelo_rendering.py src/aeat/entrypoints/cli/tests/test_modelo_payloads.py src/aeat/entrypoints/cli/tests/test_work_calculate_row_flag.py`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `7ff039f4ca` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
