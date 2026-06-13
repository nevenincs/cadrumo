---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S08'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` `P03.S08`

Added the Diseño-completeness manifest schema model enumerating the
expected `(segmento, number)` casilla set per modelo revision under the
strict-pydantic registry discipline.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`

## Description

Two new `RegistryModel` subclasses were added to the registry schema
module, inheriting the strict / frozen / `extra="forbid"` discipline of
`RegistryModel`.

`DisenoCompletenessCasilla` carries one expected casilla as the pair
`(segmento, number)`, with `segmento` optional (unset for single-segment
modelos, degrading the pair to `(None, number)`). It exposes an
`identity()` accessor returning the `(segmento, number)` tuple.

`DisenoCompletenessManifest` enumerates the expected casilla set for a
modelo revision: a `source_ref` naming the AEAT Diseño de Registros it
was derived from, a non-empty `casillas` tuple, a `manual_extraction`
flag plus `manual_extraction_reason` for PDF-only Diseños that resist
machine extraction, and `legal_refs` / `source_refs` provenance. A
`model_validator` rejects an empty casilla set, duplicate
`(segmento, number)` identities, a `source_ref` absent from
`source_refs`, a `manual_extraction` manifest with no reason, and a
reason declared without the flag. An `identities()` accessor returns the
frozenset of expected pairs for the completeness gate to compare against.

An optional `completeness_manifest: DisenoCompletenessManifest | None`
field was wired onto `ModeloRevision`, defaulting to `None`. The field
is purely additive: every existing revision validates unchanged with the
manifest unset, satisfying the schema-hardening rollout discipline that
all 26 modelos remain valid throughout the rollout. Both new models are
re-exported from the registry package `__init__.py`.

## Tests

`pytest` on `test_registry_schema.py` (66 tests) and
`test_modelo_parity_coverage.py` (1 test) — all 67 pass, confirming the
additive schema field does not red the 26 modelos. `ruff check` on the
two touched files passes clean.
