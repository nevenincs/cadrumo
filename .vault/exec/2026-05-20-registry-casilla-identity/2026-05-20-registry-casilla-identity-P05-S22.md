---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S22'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P05.S22`

Authored the Modelo 200 calculation-completeness manifest and corrected
two defects in the off-load-path derivation tool that prevented the
manifest from clearing the gate. Modelo 200 now clears the
calculation-completeness gate.

- Created: `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/completeness-manifest.toml`
- Modified: `src/aeat/domain/calculations/registry/_record_design.py`

## Description

The Modelo 200 calculation closure was derived with
`derive_calculation_completeness_casillas` against the official AEAT
Diseño de Registros corpus (`aeat-dr-200-2025`). Deriving it surfaced two
genuine defects in the derivation tool — both reported and fixed here
rather than worked around, because the gate must not be weakened and the
manifest must not hide a wrong closure.

Finding 1 — cross-modelo relation `source_output` wrongly folded into
the closure. `calculation_closure_numbers` added every
`RelationDefinition.source_output` to the modelo's closure. A relation
always carries a `source_modelo`, and its `source_output` is a casilla
on that *foreign* modelo: the Modelo 200 `rel-202-pagos-fraccionados`
relation has `source_modelo = "202"` and `source_output = "34"`, where
`34` is a Modelo 202 casilla, not a Modelo 200 one. Folding it into the
Modelo 200 closure would make the completeness gate demand casilla `34`
from the Modelo 200 Diseño. The cross-modelo edge correctly enters
Modelo 200 through `relation.target_binding`, whose bound casilla is
already counted as a current-modelo binding endpoint. Fixed:
`calculation_closure_numbers` no longer adds `relation.source_output`.

Finding 2 — the multi-segment derivation over-generated. For a
`multi_segment` modelo the tool emitted a `(segmento, number)` pair for
*every* Diseño sheet containing a closure number. Modelo 200's Diseño
places `00592` in three record segments and `00599` in three more, so
the tool yielded six pairs for a two-casilla closure — and the gate would
then demand `00592` and `00599` under segments the registry never
declares them in, failing the M200 gate. The ADR amendment defines the
manifest as the Diseño *intersected with the modelo's calculation
surface*: the calculation surface declares each closure casilla under
exactly one segment (`DP200014B` for both `00592` and `00599`). Fixed:
`derive_calculation_completeness_casillas` is now segment-aware — when a
closure number resolves to a declared casilla carrying an explicit
`segmento`, the manifest identity is pinned to that declared
`(segmento, number)` pair (still verified present in the Diseño under
that segment). An undeclared or single-segment closure number keeps the
every-sheet fallback, so the Modelo 200 missing-casilla defect class
still surfaces.

With both fixes the Modelo 200 closure derives to exactly
`{(DP200014B, 00592), (DP200014B, 00599)}` — the cuota liquida casilla
that is the cuota-del-ejercicio formula's expression input and the cuota
del ejercicio casilla that is the formula target and the
verification-expectation operand. The manifest enumerates that pair,
grounded on `aeat-dr-200-2025` and the cuota-chain legal references, and
Modelo 200 clears the calculation-completeness gate. The off-load-path
drift re-verification test re-derives this set from the corpus Diseño and
matches.

## Tests

`pytest test_record_design.py test_referential_integrity.py
test_modelo_200_registry.py` — 88 tests pass, including the drift
re-verification which re-derives the M200 manifest from the corpus and
the closure-bounds test. `pytest test_modelo_parity_coverage.py
test_schema_hygiene.py` — 12 tests pass, all 26 modelos load valid with
the M200 manifest live. `ruff check` on `_record_design.py` is clean.
