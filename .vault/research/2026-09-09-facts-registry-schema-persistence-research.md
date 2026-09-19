---
tags:
  - '#research'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:2ec5af7e8aaba97e878eb73b08c19e013cf36e1f61e7b14048903d6968ea2125'
related: []
---

# `facts-registry` research: `Governed fact schema and persistence`

The mature modelo/casilla registry should remain unchanged. Its lower-level
typed value, temporal, grounding, and identity patterns are reusable, but
cross-cutting tax facts need a sibling persistence family because not every
fact belongs to one filing revision and not every payload is numeric. The
evidence favors one semantic fact per flat TOML fragment with dated variants,
subject to ADR decisions on exact names and payload families.

## Findings

### Existing parameter primitives cover scalar facts but not the whole domain

`ParameterDefinition` carries typed scalar values, numeric brackets, keyed
brackets, legal and source references, and citations at
`src/cadrumo/domain/calculations/registry/schema_formula.py:352`. `DatedValue`
adds a date axis, validity window, and comparison operator at
`src/cadrumo/domain/calculations/registry/schema_formula.py:177`. These shapes
fit rates, thresholds, caps, multipliers, and numeric schedules.

The global `LegalParameter` at
`src/cadrumo/domain/calculations/registry/schema_references.py:594` is only a
string value, unit, free-form applicability text, references, and review
metadata. It lacks typed payloads, dated variants, source citations, and
structured selectors, so expanding it into the universal executable store
would be an invasive semantic change.

### Self-similarity should apply to the envelope, not every payload field

Scalar values, tax brackets, typed mappings, entity sets, treaty overrides,
calendar events, and multi-output surcharge bands require different payload
models. The IVA table documents deliberately overlapping overrides at
`src/cadrumo/_data/registry/aeat/iva/rates.toml:31`; treaty overrides carry
semantic kinds and optional rates at
`src/cadrumo/domain/calculations/registry/convenio.py:39`; and LGT surcharge
bands emit more than one result at
`src/cadrumo/_data/registry/aeat/legal/ley-58-2003-recargo-bands.toml:24`.
A universal dictionary would hide divergence, while a Decimal-only parameter
would coerce away meaning.

The common candidate envelope is stable fact identity, immutable variant
identity, closed family and payload kind, typed selector, one semantic temporal
axis and window, legal and source references and citations, review/authority
state, authored/generated ownership, and explicit override relationships.
Closed family-specific payload models retain domain meaning.

### One fact per flat file matches current review granularity

Current revision parameters use numbered one-concept fragments, for example
`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0052-renta-2025-deduccion-madrid-nacimiento-adopcion-cuantia.toml:1`.
A sibling candidate topology is
`src/cadrumo/_data/registry/aeat/facts/NNNN-<stable-slug>.toml`, with one
semantic fact and all of its variants in the file. The numeric prefix is
administrative ordering, never identity. A flat family avoids inventing a
modelo owner or a recursive directory grammar before evidence requires one.

### Fact and variant identities serve different continuity contracts

`fact_id` should identify the stable regulated concept without embedding its
current value, date, or modelo revision. `variant_id` should identify one
legally distinct redaction or interval and remain stable even when files are
reordered. Existing IDs accept lowercase administrative punctuation at
`src/cadrumo/domain/calculations/registry/ids.py:8`; whether variant IDs use an
effective-date suffix remains an ADR choice.

Variant-level references are important because authority and wording can
change while a numeric value remains equal. Fact-level type and unit may be
inherited only when compilation materializes a complete provenance-bearing
variant.

### Resolution needs exact typed coordinates

The current scalar resolver requires the declared date axis and exactly one
matching window at
`src/cadrumo/domain/calculations/registry/formula_runtime_ops.py:265`.
Governed-fact resolution should retain those fail-closed semantics while adding
typed family selectors and explicit zero-match classifications. Declaration
order and implicit “most specific” selection are unsafe; overlapping variants
need a validated, acyclic override or supersession edge.

## Sources

- `src/cadrumo/domain/calculations/registry/schema_formula.py:177`
- `src/cadrumo/domain/calculations/registry/schema_formula.py:352`
- `src/cadrumo/domain/calculations/registry/schema_references.py:594`
- `src/cadrumo/_data/registry/aeat/iva/rates.toml:31`
- `src/cadrumo/domain/calculations/registry/convenio.py:39`
- `src/cadrumo/_data/registry/aeat/legal/ley-58-2003-recargo-bands.toml:24`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/parameters/0052-renta-2025-deduccion-madrid-nacimiento-adopcion-cuantia.toml:1`
- `src/cadrumo/domain/calculations/registry/ids.py:8`
- `src/cadrumo/domain/calculations/registry/formula_runtime_ops.py:265`
