---
tags:
  - '#research'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:4b19c888f09e33893a4e191a33f634e497ea2ed2904a8b165b37614d369e0f66'
related:
  - "[[2026-06-08-registry-localization-backend-research]]"
  - "[[2026-06-11-modelo-locales-cli-research]]"
  - "[[2026-06-08-registry-localization-backend-adr]]"
  - "[[2026-06-11-modelo-locales-cli-adr]]"
  - "[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]"
  - "[[2026-05-08-modelo-directory-segmentation-adr]]"
---
# `modelo-localization-cascade` research: `canonical root-scope schema localization`

This research asks how one Modelo-root locale catalogue can serve every supported revision and consumer without treating a printed casilla number as stable identity. The current implementation already proves lazy Modelo-local loading and a two-level cascade, but it stores most values below revision directories and injects every supported translation into every materialized casilla and downstream projection. The evidence favors a typed, root-only catalogue addressed through existing Modelo, revision-local `CasillaDefinition.id`, and cross-revision `continuidad_id` contracts, with sparse exact-revision overrides and the official Spanish schema text as the terminal fallback. The authorizing ADR must fix the serialized notation, precedence, missing-continuity behavior, lifecycle boundaries, and migration gates.

## Findings

### The shipped backend already implements the semantic outline of a cascade

Modelo-root locale files are loaded by `_load_modelo_translations`, while revision-directory locale files are loaded separately by `_load_revision_translations`. Referential integrity validates Modelo-root keys against `continuidad_id` and revision keys against the selected revision's `casilla.id`; `_localize_casilla` applies the continuity value first and the revision occurrence value second, so the latter overrides the former field by field. The loader performs this after revision fragments are merged. These are existing contracts, not a new identity proposal: `src/cadrumo/domain/calculations/registry/_loader_locales.py:112`, `src/cadrumo/domain/calculations/registry/_loader_locales.py:116`, `src/cadrumo/domain/calculations/registry/_loader_locales.py:181`, `src/cadrumo/domain/calculations/registry/_loader_locales.py:207`, and `src/cadrumo/domain/calculations/registry/_loader_locales.py:263`.

The authoring side mirrors those scopes. `ModeloLocaleFileTarget` maps one target either to `<modelo>/locales/<locale>.toml` or `<modelo>/revisions/<revision>/locales/<locale>.toml`; inventory always emits revision-local rows by `casilla.id` and additionally emits Modelo rows when `continuidad_id` exists. The manager therefore already knows the two identities a root-only design needs, but its path and completeness contracts require both physical scopes: `src/cadrumo/locales/_modelo_manager.py:75`, `src/cadrumo/locales/_modelo_manager.py:94`, `src/cadrumo/locales/_modelo_manager.py:288`, `src/cadrumo/locales/_modelo_manager.py:800`, `src/cadrumo/locales/_modelo_manager.py:826`, and `src/cadrumo/locales/_modelo_manager.py:847`.

### A canonical address must begin with the selected casilla occurrence, then derive continuity

`CasillaDefinition.id` is the canonical reference identity inside a selected revision; `number` and `segmento` are AEAT record-design metadata, and the canonical `CasillaId` grammar permits compound identifiers such as the segment-qualified M200 ids. `continuidad_id` is a separate optional stable cross-revision concept key. The continuity ADR explicitly records that repeated ids are insufficient evidence of year-to-year legal continuity and that `repurposed` and `retired` are first-class evolution boundaries: `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:210`, `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:222`, `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:285`, `src/cadrumo/core/_casilla_id.py:33`, `src/cadrumo/domain/calculations/registry/_schema_base.py:185`, and `.vault/adr/2026-05-27-schema-hardening-casilla-continuity-contract-adr.md:39`.

The prior cascade proposal can therefore be represented without another identity authority by typed addresses whose path notation is only a serialization:

```text
modelo/<modelo-id>/campo/<field>
modelo/<modelo-id>/revision/<revision-id>/campo/<field>
modelo/<modelo-id>/casilla/continuidad/<continuidad-id>/<field>
modelo/<modelo-id>/revision/<revision-id>/casilla/<casilla-id>/<field>
```

The locale is a resolver argument and catalogue dimension, not part of semantic identity. A caller supplies a Modelo, the already selected revision, and `casilla.id`; the resolver proves occurrence membership and derives `continuidad_id` from that occurrence. Revision selection must reuse the law-determined temporal authority rather than independently guessing from a year or accepting a free revision override: `src/cadrumo/domain/calculations/registry/_temporal.py:58`.

### Root-only sparse catalogues address the measured storage and projection duplication

A read-only inventory on 2026-08-04 found 281 schema-locale TOML files under the Modelo tree: 278 below revision subtrees and only three at a Modelo root, all three under Modelo 100. The physical evidence is reproducible with `fd -t f . src/cadrumo/_data/registry/aeat/modelos | rg "[\\/]locales[\\/]"`; representative revision and root catalogues are `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/locales/en.toml:1` and `src/cadrumo/_data/registry/aeat/modelos/100/locales/en.toml:1`.

The duplication also crosses runtime projections. `CasillaDefinition` carries `localized_labels` and `localized_help`; the registry query report repeats both maps, query assembly copies them, and application and CLI payloads copy them again. The same three non-Spanish schema-local languages are therefore transported through multiple facades even though each consumer eventually selects one language: `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:236`, `src/cadrumo/domain/calculations/registry/_query_reports.py:136`, `src/cadrumo/domain/calculations/registry/_queries.py:674`, `src/cadrumo/application/modelo/_data_inventory.py:144`, and `src/cadrumo/entrypoints/cli/_modelo_payloads.py:823`. The closed output-language set is Spanish, English, Catalan, and Hungarian; Spanish is the default and the three translated schema catalogues are `en`, `ca`, and `hu`: `src/cadrumo/core/external_constants.py:474`.

A root-only source can author one leaf per `(locale, canonical address, field)` and allow physical fragmentation below the root `locales/` directory for large Modelos. That removes repetition across revisions and facades; it does not pretend that one natural-language value can serve three different languages.

### Safe fallback preserves the Spanish invariant and refuses semantic inference

The official Spanish casilla label is required schema data, and `get_label` currently falls back to it when a requested translation is absent; help has no equivalent official source and falls back to no value. The accepted backend ADR also reserves official Spanish text for regulatory/export consumers: `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:313` and `.vault/adr/2026-06-08-registry-localization-backend-adr.md:20`.

For a non-Spanish casilla lookup, the evidence-supported cascade is an exact revision-occurrence value, then a continuity-concept value when the selected occurrence declares `continuidad_id`, then the official Spanish label; help terminates at no value. A casilla without `continuidad_id` has no evidence-backed Modelo-wide base and can only use an exact revision occurrence until continuity is grounded. A `repurposed` evolution is an inheritance barrier, while a retired continuity value remains valid only for supported historical revisions that still contain the occurrence. Missing translations must not silently fall through to another non-Spanish locale.

Modelo metadata follows the same separation: operator-facing `ModeloDefinition.title` and optional `ModeloRevision.label` can have root-catalogue values, while `official_name` and the official Spanish schema fields remain invariant data. The current schema exposes those three surfaces at `src/cadrumo/domain/calculations/registry/_schema.py:999`, `src/cadrumo/domain/calculations/registry/_schema.py:1094`, and `src/cadrumo/domain/calculations/registry/_schema.py:1095`.

### Read-time resolution is the boundary that removes localization from revision schemas and facades

The current directory loader injects locale maps before building its cached `ModeloDefinition`, and a separate no-locales loader exists solely for the authoring manager. A root-only catalogue does not require locale values to remain fields on `CasillaDefinition`; the catalogue and its own fingerprinted cache can be loaded lazily, while a single resolver returns one requested value at the presentation boundary. This keeps revision schemas regulatory/calculation data and prevents every DTO from transporting all languages: `src/cadrumo/domain/calculations/registry/_loader.py:287`, `src/cadrumo/domain/calculations/registry/_loader.py:297`, and `src/cadrumo/domain/calculations/registry/_loader.py:302`.

The repository's generic locale-key decision independently found that read-time resolution avoids baking an operator locale into shared cached state. That finding does not dictate the schema-locale key shape, but it supports keeping the selected locale out of cached registry objects: `.vault/adr/2026-07-21-locale-key-resolution-adr.md:29` and `.vault/adr/2026-07-21-locale-key-resolution-adr.md:48`.

### The alternatives differ mainly in whether they preserve one identity authority

- Keeping the current Modelo-plus-revision directory cascade preserves shipped behavior but retains the measured physical and projection duplication.
- Keying a root catalogue only by printed casilla number, or assuming a repeated `casilla.id` means the same concept across years, is unsafe because neither proves cross-revision semantics.
- Introducing an unrelated translation-key registry could deduplicate text but would create a second identity authority that must remain synchronized with `CasillaDefinition.id`, `continuidad_id`, and revision selection.
- A root-only typed cascade using those existing identities preserves current semantics while making revision entries sparse. It is the evidence-favored option; the ADR must decide its exact TOML tables, override/tombstone behavior, strict validation, and migration cutover.

### Migration needs per-Modelo parity and an atomic removal boundary

The current CLI already owns audit, scaffold, set, remove, and coverage operations, but its commands require a revision and its manager writes both physical scopes. A root-only migration must change inventory from “every revision occurrence in every locale” to “one continuity default plus genuine revision divergences,” retain exact-occurrence inventory for missing continuity, and report unresolved, stale, ambiguous, repurposed, and retired keys. The existing command surface is grounded at `src/cadrumo/locales/cli.py:356`, `src/cadrumo/locales/cli.py:384`, `src/cadrumo/locales/cli.py:436`, `src/cadrumo/locales/cli.py:463`, and `src/cadrumo/locales/cli.py:489`.

Each Modelo can be migrated independently through the same boundaries: inventory and classify identities, synthesize root defaults and sparse overrides, compare every old resolved leaf with the new resolver for every supported revision and locale, switch all consumers, prove audit/scaffold parity and cache invalidation, then remove that Modelo's revision locale directories. The final global gate must reject any remaining revision-local locale data and any localization maps on revision-schema or facade DTOs. The accepted backend and CLI ADRs require the opposite storage and injection shape at `.vault/adr/2026-06-08-registry-localization-backend-adr.md:32` and `.vault/adr/2026-06-11-modelo-locales-cli-adr.md:28`; choosing the root-only design therefore requires superseding both rather than leaving contradictory accepted records.

## Sources

- `src/cadrumo/domain/calculations/registry/_loader_locales.py:112`
- `src/cadrumo/locales/_modelo_manager.py:75`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:210`
- `src/cadrumo/core/_casilla_id.py:33`
- `src/cadrumo/domain/calculations/registry/_schema_base.py:185`
- `src/cadrumo/domain/calculations/registry/_temporal.py:58`
- `src/cadrumo/domain/calculations/registry/_schema.py:999`
- `src/cadrumo/domain/calculations/registry/_loader.py:287`
- `src/cadrumo/domain/calculations/registry/_query_reports.py:136`
- `src/cadrumo/domain/calculations/registry/_queries.py:674`
- `src/cadrumo/application/modelo/_data_inventory.py:144`
- `src/cadrumo/entrypoints/cli/_modelo_payloads.py:823`
- `src/cadrumo/core/external_constants.py:474`
- `src/cadrumo/locales/cli.py:356`
- `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/locales/en.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/100/locales/en.toml:1`
- `.vault/adr/2026-05-27-schema-hardening-casilla-continuity-contract-adr.md:39`
- `.vault/adr/2026-06-08-registry-localization-backend-adr.md:20`
- `.vault/adr/2026-06-11-modelo-locales-cli-adr.md:28`
- `.vault/adr/2026-07-21-locale-key-resolution-adr.md:29`
- Read-only inventory command: `fd -t f . src/cadrumo/_data/registry/aeat/modelos | rg "[\\/]locales[\\/]"`
