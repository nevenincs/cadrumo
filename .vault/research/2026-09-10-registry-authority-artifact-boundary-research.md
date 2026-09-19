---
tags:
  - '#research'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:d68a289649d37dcc6391191ce184aa37d7e0db88756738921c7e3a00d2d78f2f'
related: []
---

# `registry-authority-artifact-boundary` research: immutable runtime publication

The production package originally compiled its bundled registry from raw authoring inputs, including source evidence and record-design PDFs. This research grounds the immutable publication boundary and its 2026-09-12 follow-up audit of the remaining bootstrap and parallel runtime lanes.

## Findings

### Bundled authority was a source compiler, not an immutable consumer

`bundled_authority()` called public root-based `ValidatedRegistryAuthority.load`; the load path constructed the registry from TOML, treaty, supplementary-Orden, fact-provider, and source-evidence inputs. That coupling motivated the published artifact boundary. `src/cadrumo/domain/calculations/registry/authority.py:931-1073`

### The compiled cache was not a publishable runtime boundary

The cache was a mutable-root recompilation shortcut keyed to compiler/source-tree identity. Its frozen models-and-catalogues payload was suitable for publication, but its fallback and raw-root semantics were not. `src/cadrumo/domain/calculations/registry/_compiled_cache.py:1-37` `src/cadrumo/domain/calculations/registry/loader.py:257-335`

### Record-design parsing and repairs are authoring validation, not runtime behavior

The PDF extraction/repair family establishes whether generated export layouts agree with official source material. It is enrolled through revision validation and has no production responsibility outside that development coverage gate. `src/cadrumo/domain/calculations/registry/_validate_revision_sections.py:211` `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py:971-1001` `src/cadrumo/domain/calculations/registry/record_design.py:48-227`

### Development publication provides the transaction boundary

The registry pipeline stages candidates and atomically publishes validated output. Publication into a versioned authority artifact makes the development/runtime handoff explicit. `dev/registry/pipeline/cli.py:98-165` `dev/registry/pipeline/_tree_publication.py:136-260`

### Runtime callers can consume snapshots without root loading

Application and adapter callers need model, catalogue, and snapshot access; those dependencies are representable by the authority surface. Artifact-backed snapshot reads remove arbitrary-root capability without a fallback facade. `src/cadrumo/application/calculations/binding_prefill.py:460` `src/cadrumo/application/filing/draft_construction.py:96` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py:168`

### The artifact reader still has a raw-source bootstrap cycle

`Modelo` and `TaxDomain` are constructed from raw governed-fact TOML at module import, while the registry schema imports those types before the artifact payload can be reconstructed. Moving the same closed member lists into Python or reading them from the artifact during import would respectively duplicate authority or invert the compiler dependency. `src/cadrumo/core/modelo.py:20-48` `src/cadrumo/core/tax_domain.py:12-37` `src/cadrumo/domain/calculations/registry/schema.py:948`

### Closed-enum behavior has a bounded migration surface

Production uses 41 named `Modelo` constants across 108 files and one direct enumeration site. It has no observed production dependency on enum `__members__`, subscription, or member names. String construction, equality, hashing, serialization, `.value`, and `isinstance` behavior are the compatibility surface needed by a syntax-valid string identifier. `src/cadrumo/entrypoints/cli/common.py:72` `src/cadrumo/domain/submission/models.py:245`

### Parallel raw runtime lanes remain outside the published authority

IVA catalogue, place-of-supply, country/territory, recargo-band, and apoderamientos consumers parse authoring TOML and maintain caches independently of the authority artifact. Operative values embedded merely as source bytes would retain those parsing and management lanes; canonical runtime projection therefore requires typed catalogue data. `src/cadrumo/domain/iva/catalogue.py:33-119` `src/cadrumo/domain/iva/place_of_supply.py:187-263` `src/cadrumo/domain/deadlines/recargo.py:46-99` `src/cadrumo/domain/auth/apoderamientos/catalogue.py:76-95`

### Revision expansion and period selection are separate concerns

The compiler materializes authored revision deltas into canonical typed revisions, while period selectors remain compact and runtime revision selection applies their bounds. A production delta interpreter is unnecessary; compaction can omit only schema-declared defaults and still reconstruct the same typed graph. `src/cadrumo/domain/calculations/registry/authority_artifact.py:407-466` `src/cadrumo/domain/calculations/registry/temporal.py`

### Behavioral proof must exercise installed consumption

The release gate must reject defective publication, run a real installed workflow with authoring inputs absent, refuse a corrupt or missing artifact without regeneration, and show that source mutation has no runtime effect until republishing. It must additionally prove that operative consumers use typed projections rather than reparsing embedded source documents.

## Sources

`src/cadrumo/domain/calculations/registry/authority.py:931-1073`

`src/cadrumo/domain/calculations/registry/_compiled_cache.py:1-37`

`src/cadrumo/domain/calculations/registry/loader.py:257-335`

`src/cadrumo/domain/calculations/registry/_validate_revision_sections.py:211`

`src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py:971-1001`

`src/cadrumo/domain/calculations/registry/record_design.py:48-227`

`dev/registry/pipeline/cli.py:98-165`

`dev/registry/pipeline/_tree_publication.py:136-260`

`src/cadrumo/application/calculations/binding_prefill.py:460`

`src/cadrumo/application/filing/draft_construction.py:96`

`src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py:168`

`src/cadrumo/core/modelo.py:20-48`

`src/cadrumo/core/tax_domain.py:12-37`

`src/cadrumo/domain/calculations/registry/schema.py:948`

`src/cadrumo/entrypoints/cli/common.py:72`

`src/cadrumo/domain/submission/models.py:245`

`src/cadrumo/domain/iva/catalogue.py:33-119`

`src/cadrumo/domain/iva/place_of_supply.py:187-263`

`src/cadrumo/domain/deadlines/recargo.py:46-99`

`src/cadrumo/domain/auth/apoderamientos/catalogue.py:76-95`

`src/cadrumo/domain/calculations/registry/authority_artifact.py:407-466`

`src/cadrumo/domain/calculations/registry/temporal.py`
