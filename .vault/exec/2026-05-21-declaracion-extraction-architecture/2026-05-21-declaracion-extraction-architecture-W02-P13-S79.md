---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W02.P13.S79'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# `declaracion-extraction-architecture` `W02.P13.S79`

Test-reader migration: all 11 test files that previously read
`ExtractionProfileDefinition.target_casillas` as bare `CasillaId` strings
updated to read `.casilla_id` from `ExtractionTargetDefinition` records.
Covers steps S69 through S79.

- Modified: `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_record_design.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_720_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_232_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`
- Modified: `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
- Modified: `src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py`

## Description

Every test that iterated `profile.target_casillas` as a flat string tuple
was updated to read `target.casilla_id` from each `ExtractionTargetDefinition`
record (using set comprehensions `{t.casilla_id for t in ...}` where needed).

`test_modelo_100_summary.py`: `_profile()` helper rewritten to construct
`ExtractionTargetDefinition` records; `target_casillas` parameter renamed
`target_casilla_ids`.

`test_declarations.py`: 4 call-sites updated to use `.casilla_id`.

`test_referential_integrity.py`: `ExtractionTargetDefinition` imported;
dangling-ref test updated to construct a full `ExtractionTargetDefinition`
in the inline-table test fixture.

Steps S76 (`test_first_slice_routing.py`) and S78
(`test_renta_cuota_chain_contract.py`) were no-ops: those tests
do not read `target_casillas` directly and required no changes.

## Tests

`uv run pytest -q src/aeat/domain/calculations/registry/ src/aeat/adapters/inbound/declaracion/test_parser_boundary.py src/aeat/adapters/inbound/borrador/test_modelo_100_summary.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py` passed 194 tests in 94.5s.
