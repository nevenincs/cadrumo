---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S27'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P06.S27`

Refocused the P03 manifest schema model so it represents the
calculation-closure required casilla set, and renamed it away from the
now-misleading "Diseño" name.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`

## Description

The P03 manifest schema model was authored one day prior under the old
B3 wording as a full-Diseño coverage set. The ADR amendment of
2026-05-20 refocuses the gate to calculation-completeness, so the
"Diseño" name is now misleading. The model is renamed and its docstrings
rewritten:

- `DisenoCompletenessCasilla` -> `CalculationCompletenessCasilla`
- `DisenoCompletenessManifest` -> `CalculationCompletenessManifest`

The model shape is unchanged — `(segmento, number)` casilla pairs, a
`source_ref`, `manual_extraction` flag, `legal_refs` / `source_refs` —
because that shape already expresses an enumerated required casilla set.
What changed is the documented contract: the manifest now enumerates the
casillas inside a modelo's *calculation closure* (formula targets,
formula-expression casilla references, binding and relation endpoint
casillas, verification-expectation operands), derived from the AEAT
Diseño *intersected with* the modelo's calculation surface, not the full
Diseño coverage set. The class and validator-error strings are updated
to "calculation-completeness manifest" wording.

The model has no authored instances yet (P05 authors the manifests), so
the rename is a pure schema-surface change with no checked-in data to
migrate. All references were updated: the `ModeloRevision.
completeness_manifest` field type, the registry `__init__.py` re-export
import block and `__all__` list, and the `test_referential_integrity.py`
import block and helper. The substantive test-logic rewrite to the
refocused subset-plus-grounding semantics lands in `P06.S29`; this Step
only carries the mechanical class-name update so the tree stays green.

## Tests

`pytest src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py`
passes — all 26 modelos load valid and the gate stays dormant.
`test_referential_integrity.py` collects cleanly (44 tests). `ruff check`
on all three touched files passes clean. No stale `DisenoCompleteness`
references remain anywhere in `src/aeat/`.
