---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P18.S122'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-auth-gated-acquisition-status-audit]]'
---

# W05.P18.S122 - post-authentication acquisition matrix

Recorded the post-authenticated-read acquisition matrix for the remaining
blocked modelos after Modelo 190 was closed through the 2024 legal/source slice
and existing sanitized fixture.

## Evidence Reviewed

- Local official corpus coverage for modelos 180, 036, 369, 720, and 840.
- Registry legal/source refs for the same modelos.
- Absence of fixture directories under
  `src/aeat/tests/fixtures/justificantes/{180,036,369,720,840}/`.
- The read-only Sede listing result that returned zero rows for those modelos
  across 2024-2026.

## Result

No additional fixture-backed implementation row can be closed from the current
worktree evidence:

- Modelo 180 remains limited to record-design/procedure/form-spec authority for
  export and calculation surfaces.
- Modelo 036 remains limited to record-design/procedure authority until an
  authorised printed-form/declaration fixture exists.
- Modelo 369 remains limited to record-design/procedure/BOE authority until an
  Esquema Union declaration fixture exists.
- Modelo 720 remains limited to record-design/procedure/BOE authority until a
  declaration PDF fixture exists.
- Modelo 840 has static printed-form label grounding, but no value-bearing
  fixture for parser round-trip assertions.

## Remaining Gate

Rows `W03.P06.S20`, `W05.P11.S34`, `W05.P11.S36`, `W05.P11.S38`,
`W05.P11.S39`, `W05.P11.S40`, `W05.P11.S92`, `W05.P11.S94`,
`W05.P11.S96`, `W05.P11.S97`, `W05.P11.S98`, and `W05.P18.S105` through
`W05.P18.S110` remain open. Closing any of them requires an operator-supplied
authorised fixture, an authenticated filed declaration with available artifact,
or another non-synthetic official artifact. Live preview/download flows that
send synthetic data to Sede or AEAT-hosted form surfaces are prohibited.

Follow-up `W05.P18.S123` converted the acquisition policy language to this
hard constraint. Follow-up `W05.P18.S124` tracks the broader, previously
accepted Modelo 100 and Modelo 349 live-surface registry entries that still
declare `synthetic_data_allowed = true` on AEAT-hosted surfaces.

## Validation

- `uv run --no-sync pytest -q src\aeat\adapters\inbound\declaracion\test_parser_boundary.py`
  - 11 passed.
- `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\test_committed_registry.py`
  - 41 passed.
