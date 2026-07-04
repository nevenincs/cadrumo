---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S13'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add export layout metadata grounded in the official record design

## Scope

- `registry/aeat/modelos`

## Description

- Add the Modelo 145 `modelo-145-dr-v20-fixed-width` fixed-width export layout for revision `2012-01-31-y-siguientes`.
- Attach bidirectional `export_refs` from the 50 source-backed payer-communication casillas to the layout fields.
- Keep DR145 date triples as one contiguous 8-byte value field per date casilla and reserve filler only for the AEAT-reserved row 58 span.
- Update the foundation tests to compare byte-span coverage against the bundled DR145 v2.0 extractor output and to keep the export link scoped to the local communication surface.

## Outcome

- `P03.S13` is complete: Modelo 145 now registers one fixed-width export layout, `modelo-145-dr-v20-fixed-width`, sourced to `aeat-dr-145-v20`.
- The registry still models Modelo 145 as a local payer communication, not an AEAT filing surface.
- `uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py --tb=short` passed: 4 tests.
- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py` passed.
- `uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_145_source_catalogue.py src/aeat/domain/calculations/registry/tests/test_modelo_145_registry_foundation.py src/aeat/domain/calculations/registry/tests/test_source_enrollment.py src/aeat/domain/calculations/registry/tests/test_support_matrix.py --tb=short` passed: 23 tests.

## Notes

- The export layout is structural metadata grounded in DR145 v2.0. It does not add filing schedules, deadline windows, portal links, or AEAT submission semantics.
- No new binding source kind, resolver convention, or validator convention was introduced.
