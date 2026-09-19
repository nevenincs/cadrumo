---
tags:
  - '#research'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:76cb8e387a7ba6f228efa0e9d6984f91d7749e241d87c5a7861cc31f9a9331d2'
related: []
---

# `facts-registry` research: `Registry development tooling blast radius`

The registry development corpus contains reusable validation patterns, but its
mature conformance and generation tools use modelo revisions or casillas as
their denominator. Facts require new catalogue-generic gates alongside
unchanged modelo-specific tooling. Extending `ModeloRevision` would enroll
unrelated facts in filing, export, locale, completeness, and review obligations.

## Findings

### Schema-family discovery is powerful but revision-specific

`ModeloRevision` marks 19 collections with `SCHEMA_FAMILY` at
`src/cadrumo/domain/calculations/registry/schema.py:775`. The exhaustive
denominator is derived at `src/cadrumo/domain/calculations/registry/schema.py:977`,
and `src/cadrumo/domain/calculations/registry/tests/test_schema_family_coverage.py:115`
requires collection fields and enrolled families to remain equal. A separate
fact-provider registry can reuse this self-enrollment pattern without changing
revision coverage.

### Existing screens establish transferable evidence discipline

`dev/registry/README.md:47` requires screens to inspect resolved surfaces, key
measurements on every axis, and gate invariants rather than counts. Provenance
analysis discovers reference-bearing children using schema metadata at
`dev/registry/analysis/provenance_consistency.py:105`. Facts should follow the
same principles through their own provider and variant denominator.

### Regulatory-literal detection has material blind spots

The build enrolls the existing detector through `dev/quality/suite.py:40`.
`dev/registry/analysis/modelo_regulatory_literal_scan.py:49` only identifies
nontrivial numeric literals in branches that name a `Modelo`, and excludes the
calculation-registry package. It misses named constants, `Decimal` and date
strings, computed enum values, mappings, returns, defaults, legal text, custom
loaders, and rules without an explicit modelo branch.

A replacement should combine a broad report-only discovery sentinel with
enforceable architecture gates: no retired legal-constant imports, no direct
opening of governed folders, and no operative fact result without provenance.

### Modelo conformance and generation remain unchanged

The conformance manager iterates modelos and revisions at
`dev/registry/conformance/manager.py:699`; stamping locates revision manifests
at `dev/registry/conformance/_stamp.py:386`; closure is revision-denominated at
`dev/registry/conformance/closure.py:329`. Export generation derives fixed-width
records from designs, maps, and render profiles at `dev/registry/README.md:11`.
None should be repurposed for global facts.

### Fact tooling needs its own complete gate family

Catalogue-generic checks should cover directory ownership, provider enrollment,
identifier uniqueness, typed payloads, reference closure, admitted temporal
axes, overlap and explicit precedence, exact resolution, variant provenance,
authored/generated ownership, fingerprints, cache invalidation, and migration
closure. The generated annual Orden checker at
`dev/registry/analysis/m303_orden_anual.py:28` is an analogue for generated
provider ownership, not a universal fact generator.

## Sources

- `src/cadrumo/domain/calculations/registry/schema.py:775`
- `src/cadrumo/domain/calculations/registry/schema.py:977`
- `src/cadrumo/domain/calculations/registry/tests/test_schema_family_coverage.py:115`
- `dev/registry/README.md:11`
- `dev/registry/README.md:47`
- `dev/registry/analysis/provenance_consistency.py:105`
- `dev/quality/suite.py:40`
- `dev/registry/analysis/modelo_regulatory_literal_scan.py:49`
- `dev/registry/conformance/manager.py:699`
- `dev/registry/conformance/_stamp.py:386`
- `dev/registry/conformance/closure.py:329`
- `dev/registry/analysis/m303_orden_anual.py:28`
