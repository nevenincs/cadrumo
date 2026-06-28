---
tags:
  - '#audit'
  - '#registry-schema-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-schema-boundary` audit: `schema model extraction boundary audit`

## Scope

Audited `src/aeat/domain/calculations/registry/_schema.py` as the
registry package's generic schema authority and the next P04 monolith
target. The audit assessed internal extraction boundaries, public API
compatibility, and whether the extraction requires an ADR.

## Findings

### High

- `_schema.py` is 2,542 working-tree lines and combines scalar
  validators, typed aliases, base model config, source/legal metadata,
  extraction profiles, cross-reference decisions, workbook parity
  references, construct/dependency/deadline models, formula expressions,
  parameters, bindings, casilla definitions, completeness manifests,
  algorithm bindings, relations, export layouts, verification predicates,
  modelo revisions, catalogues, policy, and snapshots. This is a generic
  cross-application schema surface, not a set of modelo-specific
  definitions.
- The current working tree contains formatting-only peer WIP in
  `_schema.py`. This slice must not edit production schema code. A later
  extraction commit should begin from a clean diff or explicitly preserve
  the peer formatting changes if they have landed.
- `src/aeat/domain/calculations/registry/__init__.py` re-exports schema
  classes as public API, and `test_public_api_boundaries.py` already
  treats `_schema` as a private registry module. Extraction must preserve
  imports from `aeat.domain.calculations.registry` and should keep
  `_schema.py` as a compatibility facade until private-import consumers
  are retired.

### Medium

- The safest extraction unit is not "one model per file". It is a small
  number of generic schema-family modules with `_schema.py` re-exporting
  their public names.
- Scalar validators and typed aliases are a good first extraction because
  many later models depend on them and tests already cover the public
  data-type validators.
- Revision, modelo, catalogue, policy, and snapshot models should move
  last. They depend on nearly every earlier family and are the highest
  blast-radius part of the file.
- Formula, parameter, and binding models are coupled by IDs and runtime
  consumers, but they form a coherent calculation-schema family. They
  should move after scalar/base types and before casilla/revision models.
- Casilla and completeness models are a coherent family, but
  `CasillaDefinition` is one of the most widely used public schema
  classes. Its extraction needs public API tests and committed-registry
  load tests.

### ADR assessment

- No ADR is required for a behavior-preserving internal module
  decomposition that keeps schema semantics, TOML shape, public
  re-exports, and `_schema.py` compatibility intact.
- An ADR is required before changing schema construction semantics, adding
  a new fragment inheritance/delta model, introducing modelo-specific
  schema modules, or moving registry fragment support out of the existing
  generic loader/schema contract.

## Recommendations

1. Keep `_schema.py` as a compatibility facade during decomposition.
2. Start with a private base/scalar module containing `RegistryModel`,
   `DecimalValue`, typed scalar aliases, and the associated validators.
   Re-export those names from `_schema.py`.
3. Move source/legal/extraction/workbook/cross-reference metadata models
   next as a generic metadata family.
4. Move calculation definition models next: `FormulaExpression`,
   `FormulaDefinition`, parameter rows/tables, and
   `DataBindingDefinition`.
5. Move casilla/completeness definitions after calculation definitions:
   `CasillaConstraints`, `CasillaDefinition`,
   `CalculationCompletenessCasilla`, and
   `CalculationCompletenessManifest`.
6. Move export/record verification models after casillas and before the
   revision aggregate.
7. Move `ModeloRevision`, `ModeloDefinition`, `RegistryCatalogues`,
   `RegistryVerificationPolicy`, and `RegistrySnapshot` last.
8. Do not create modelo-specific schema files. Any extracted module must
   describe a generic schema family used across modelos.
9. Each extraction commit should run the public API boundary test,
   registry schema tests, affected scalar datatype tests, and a
   committed-registry load test scoped to the touched family.

## Codification candidates

- **Source:** finding High-1 and ADR assessment.
  **Rule slug:** `registry-schema-family-modules`.
  **Rule:** Registry schema decomposition must use generic schema-family
  modules with compatibility re-exports; modelo-specific schema modules
  or new schema construction semantics require an ADR.
