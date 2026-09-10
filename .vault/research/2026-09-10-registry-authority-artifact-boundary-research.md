---
tags:
  - '#research'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:5506b3b7faa2e4d028b3ae32bb86e2bf6019239a8ecc09ce1c8a914a0460e708'
related: []
---

# `registry-authority-artifact-boundary` research: immutable runtime publication

The production package currently compiles its bundled registry from raw authoring inputs, including source evidence and record-design PDFs. The next architecture decision must choose whether a complete validated snapshot artifact becomes the sole runtime authority and, if so, how publishing, packaging, and failure handling divide between `dev/` and `src/`.

## Findings

### Bundled authority is presently a source compiler, not an immutable consumer

`bundled_authority()` calls public root-based `ValidatedRegistryAuthority.load`; the load path constructs the registry from TOML, treaty, supplementary-Orden, fact-provider, and source-evidence inputs. Therefore an installed CLI still depends on authoring/compiler implementation rather than a published immutable authority. `src/cadrumo/domain/calculations/registry/authority.py:931-1073`

### The current compiled cache is not a publishable runtime boundary

The cache is a mutable-root recompilation shortcut keyed to compiler/source-tree identity. Its frozen models-and-catalogues payload is technically suitable for a package artifact, but retaining the cache behavior would retain mutable fallback and raw-root semantics. The alternative to evaluate is a versioned package-produced snapshot with schema and digest metadata, deserialized fail-closed when missing, malformed, or mismatched. `src/cadrumo/domain/calculations/registry/_compiled_cache.py:1-37` `src/cadrumo/domain/calculations/registry/loader.py:257-335`

### Record-design parsing and repairs are authoring validation, not runtime behavior

The PDF extraction/repair family exists to establish whether generated export layouts agree with official source material. It is enrolled through revision validation and has no observed production consumer outside that coverage gate. Its natural home is the development publisher/validator, with generated authority facts replacing its runtime presence. `src/cadrumo/domain/calculations/registry/_validate_revision_sections.py:211` `src/cadrumo/domain/calculations/registry/_validate_export_layout_coverage.py:971-1001` `src/cadrumo/domain/calculations/registry/record_design.py:48-227`

### Existing development publication code is a starting point but publishes into the wrong boundary

The registry pipeline already stages candidates and atomically publishes export-tree changes, then validates them through the production loader. It currently targets the bundled source tree and consequently preserves the conflation. A publisher that instead emits the validated snapshot artifact would make the development/runtime handoff explicit. `dev/registry/pipeline/cli.py:98-165` `dev/registry/pipeline/_tree_publication.py:136-260`

### Runtime callers can consume snapshots without root loading

The raw-loader callers identified in application and adapter code need only model/catalogue/snapshot access; their dependencies are representable by the authority surface. Replacing them with artifact-backed snapshot reads removes their arbitrary-root capability without a compatibility facade. `src/cadrumo/application/calculations/binding_prefill.py:460` `src/cadrumo/application/filing/draft_construction.py:96` `src/cadrumo/adapters/outbound/aeat/sede/declarations_observations.py:168`

### A behavioral proof must exercise publication and installed consumption

A useful gate would reject a defective dev candidate before artifact emission, demonstrate a real installed CLI calculation with authoring TOML and record-design corpus absent, refuse a corrupted/missing artifact without regenerating, and show that a post-publication source mutation has no effect until a valid republish. These scenarios test authority-path behavior rather than code shape.

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
