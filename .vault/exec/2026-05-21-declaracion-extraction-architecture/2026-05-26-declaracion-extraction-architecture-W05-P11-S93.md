---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S93'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# `declaracion-extraction-architecture` `W05.P11.S93`

Fixed the M190 revision-range mismatch that caused `select_revision(year=2024)` to raise `RegistrySnapshotError`, and fixed the `decl.retenciones-total` label pattern that prevented full coverage extraction.

- Modified: `src/aeat/_data/registry/aeat/modelos/190.toml`

## Description

Two defects were present in the M190 registry:

The revision was keyed `2025-y-siguientes` with `period_selector = { year_from = 2025, periods = ["0A"] }`. The corpus fixture `2024-0A.pdf` presents year 2024, so `includes_year(2024)` returned False (2024 >= 2025 is False), producing a `RegistrySnapshotError`. Corpus comparison of the 2024 AEAT DR M190 (`Orden HAC/1432/2024`) and the 2025 DR (`Orden HAC/1431/2025`) confirmed identical record layout (same Tipo 1 / Tipo 2 field positions, same field descriptions). The revision was renamed to `"2024"` with `period_selector = { years = [2024], periods = ["0A"] }` to match the test's `revision_id == "2024"` assertion.

The `decl.retenciones-total` label_pattern was `Importe\s+total\s+de\s+retenciones\s+e\s+ingresos\s+a\s+cuenta`. The actual PDF text (page 2, box 03) reads "Importe total de las retenciones e ingresos a cuenta relacionados". The missing `las\s+` token caused the named_label extractor to match 0/1 targets, pushing coverage to 0.67 and triggering `fail_hard`. The pattern was corrected to `Importe\s+total\s+de\s+las\s+retenciones\s+e\s+ingresos\s+a\s+cuenta`.

## Tests

- `pytest src/aeat/adapters/inbound/declaracion/test_parser_boundary.py -k modelo_190`: 1 passed
- `pytest src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`: 1 passed (all 26 modelos valid)
- Commit: `057b73bf5`
