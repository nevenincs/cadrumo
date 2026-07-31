---
tags:
  - '#exec'
  - '#cpdefix-followup-allgreen'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:859285a3d1815340ba0e748790fad2d48524321e648f1871e379a4e1928b94a0'
step_id: 'S16'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---
# Resync relocated regularizacion source-mesh enrollment tests and remove test-export repository import

## Scope

- `src/aeat/application/modelo/tests/test_bienes_inversion_regularizacion_source_mesh_enrollment.py`

## Description

- Inspected the relocated bienes-inversion source-mesh enrollment test in the current shared worktree.
- Located the real repository implementation with code search: `BienesInversionIvaRegisterRepository` is defined in `src/aeat/adapters/persistence/profile/bienes_inversion.py`.
- Replaced the test-export bundle import with a direct import from the real adapter source.

## Outcome

The bienes-inversion enrollment test no longer provisions `BienesInversionIvaRegisterRepository` through `src/aeat/tests/application_adapter_exports.py`. It imports the real persistence adapter directly and remains covered by the focused relocated enrollment gate recorded in S15.

## Notes

No fallback shim or re-export was introduced. The broader test relocation appears to be concurrent work and was not claimed as this step's source edit.
