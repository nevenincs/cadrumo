---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:6dbe1a7337ef3310a577322defba33c333aa85060ba0b11795bc33e8a0003443'
step_id: 'S60'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P02.S60`

## Scope

- `P02.S60`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/record_design.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S60.md`

## Notes

- Historical provenance: `a29f27e098e901f01781b6df0a32183d2aa6ddc4` adds `_DASH_NATURALEZA_RE`, `_FILLER_DESCRIPTION_RE`, and the `_parse_pdf_row` guard that rejects dash-token rows unless their description names a filler. It changes no dedicated record-design parser test and preserves no pytest command or literal output. The plan row's historical outcome is therefore not restated as independently observed evidence.
- Contemporary verification on clean current `record_design.py`: `\.venv\Scripts\python.exe -c "from cadrumo.domain.calculations.registry.record_design import _parse_pdf_row; assert _parse_pdf_row('1 - En el caso de que en el campo Clave Tipo de Identificacion se haya consignado una C', 455) is None; row = _parse_pdf_row('58 - BLANCOS', 58); assert row is not None and row.offset == 58 and row.type_code == 'Blancos'; print('narrative-prose=refused; single-position-filler=accepted')"` emitted `narrative-prose=refused; single-position-filler=accepted` (exit 0).
- Contemporary corpus verification on the four currently bundled Modelo 181 PDFs (`01`, `02`, `03`, `04`) emitted one line per PDF with `2 0`, meaning two parsed sheets and zero skipped sheets (exit 0). This is fresh current-state evidence, not recovered historical output.
