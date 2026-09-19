---
tags:
  - "#adr"
  - "#modelo-localization-cascade"
date: '2026-08-04'
related:
  - '[[2026-08-04-modelo-localization-cascade-research]]'
  - '[[2026-08-04-modelo-localization-cascade-migration-feasibility-research]]'
  - '[[2026-06-08-registry-localization-backend-adr]]'
  - '[[2026-06-11-modelo-locales-cli-adr]]'
  - '[[2026-07-21-locale-key-resolution-adr]]'
  - '[[2026-08-05-modelo-localization-cascade-aeip-event-keyed-continuity-research]]'
  - '[[2026-08-05-modelo-localization-cascade-gapped-continuity-chain-notation-research]]'
supersedes:
  - '2026-06-08-registry-localization-backend-adr'
  - '2026-06-11-modelo-locales-cli-adr'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e2f29c73b480d72f9a3a8e1bf85feb1126a698c7feefe02b850feee5fac58da5'
---
# `modelo-localization-cascade` adr: `shared locale-key schema with verified Modelo retirement` | (**status:** `accepted`)

## Problem Statement

Modelo schema localization currently stores natural-language text and injected locale maps on revision schema objects, then repeats translated values across revision directories and downstream projections. This snapshot-per-revision shape makes unchanged presentation data look like independently authored schema truth and imposes a large maintenance burden.

The system needs one canonical localization authority in the shared application catalogues. Schema identities must derive standardized localization keys without storing language-specific text. Shared base values declare stable text once, while language-neutral enrollment records select only genuine revision divergences. The effective revision is a deterministic right-biased union.

The live corpus can be relocated and compared mechanically, but broad semantic collapse is blocked by incomplete continuity metadata. The migration must therefore generate an explicit review register rather than infer continuity or require manual file-by-file editing. The evidence and measured boundary are grounded in `2026-08-04-modelo-localization-cascade-research` and `2026-08-04-modelo-localization-cascade-migration-feasibility-research`.

This amended record continues to replace the storage, injection, and authoring decisions in `2026-06-08-registry-localization-backend-adr` and `2026-06-11-modelo-locales-cli-adr`.

## Considerations

- Modelo, selected revision, revision-local casilla id, and field are sufficient to derive one canonical occurrence key.
- Printed `number` and `segmento` remain AEAT metadata, not localization identity.
- `continuidad_id` remains the only authority for cross-revision semantic inheritance.
- Spanish is the mandatory source locale. Its current official strings must move verbatim to the shared `es` catalogue before schema text is removed.
- Regulatory and export consumers need a strict official-Spanish resolution channel, not hard-coded Spanish fields.
- Revisions need not form one linear chronology, so progressive overrides require explicit applicability sets.
- A disposable migration application can generate keys, relocate values, classify conflicts, and prove parity without becoming a permanent production compatibility layer.
- Review must operate per continuity candidate and distinct value variant, not per duplicated leaf.
- Locale edits must not rebuild or mutate shared cached registry definitions.

## Considered options

- **Keep Spanish text in schema and move only non-Spanish translations.** Rejected because it preserves language coupling and a second text-resolution mechanism.
- **Hand-edit every Modelo and revision into the new layout.** Rejected because the current loader already exposes deterministic identities and resolved values, making manual transcription slower and less reliable.
- **Infer continuity from repeated ids, numbers, labels, or normalized text.** Rejected because those signals produce useful candidates but do not prove legal semantic identity.
- **Use an implicit parent-revision chain for progressive overrides.** Rejected because applicability is law-determined and may branch or overlap.
- **Use exact revision overrides only.** Rejected as the sole divergence notation because one value shared by several revisions would still be repeated.
- **Use the shared runtime catalogues, derived keys, language-neutral revision applicability, and a generated migration manifest.** Chosen because it joins the existing locale-key system, declares each value once, preserves legal revision selection, removes Modelo-local translation storage, and makes unresolved work explicit.

## Constraints

- Revision selection remains law-determined. Localization receives an already selected revision and never infers chronology from sorting or a bare year.
- Every localizable natural-language field in Modelo, revision, casilla, and their presentation projections must move to the shared locale catalogues. Schema records retain identifiers, legal/source grounding, structural metadata, language-neutral locale-key enrollment, and evidence, but no language-specific presentation value.
- Legal evidence bytes, citations, AEAT codes, identifiers, and non-presentational source material remain outside localization. A migration inventory must classify every schema string field against this boundary.
- The Spanish catalogue is mandatory and source-authoritative. A missing Spanish value for a required key is load-blocking; no humanized or cross-locale fallback may satisfy it.
- A `repurposed` evolution is an inheritance barrier. A value cannot cross that boundary without a new grounded continuity identity.
- Provisional migration candidates and unresolved markers are not production continuity ids. The production compiler must reject unresolved required keys.
- No enrolled Modelo may retain a Modelo-root or revision-directory locale file. Migration-only extraction may read the old shape before that Modelo's cutover.
- The shared catalogues remain one logical catalogue per locale. Duplicate logical declarations fail even when values match.
- The implementation preserves the supported locale set and never falls from one non-Spanish locale into another.

## Implementation

### D1 - Make the shared locale catalogues the sole text authority

The existing shared runtime catalogues at `src/cadrumo/locales/{es,en,ca,hu}.yml` own every Modelo localization value. Spanish (`es`) carries the verbatim source values. English, Catalan, and Hungarian use the same standardized dotted keys and the existing catalogue parity contract.

No localization file may remain anywhere beneath the Modelo registry tree after the owning Modelo is enrolled. This prohibition includes `<modelo>/locales/**`, `<modelo>/revisions/<revision>/locales/**`, fragments, aliases, and generated compatibility copies. Revision schema fragments and materialized schema models must not carry natural-language labels, help, titles, names, locale maps, or hand-authored localization keys.

The shared catalogues cover:

- Modelo presentation and official-name fields.
- Revision presentation fields.
- Casilla labels, help, aliases, section presentation, and any later schema field classified as localizable text.
- Cross-revision defaults and reviewed revision divergences.

### D2 - Derive standardized dotted locale keys from schema identity

Production-facing keys use the application's existing dotted `locale.key` contract. They never use Spanish text, slash-delimited paths, printed casilla numbers, or hand-authored per-revision key declarations.

```text
modelo.schema.<modelo-id>.field.<field>
modelo.schema.<modelo-id>.revision.<revision-segment>.field.<field>
modelo.schema.<modelo-id>.casilla.continuidad.<continuidad-segment>.<field>
modelo.schema.<modelo-id>.revision.<revision-segment>.casilla.<casilla-segment>.<field>
```

The continuity form is the stable key for a grounded chain. The exact revision-occurrence form is used only when no grounded continuity identity exists. Locale is a resolver argument, not part of the key. Callers provide Modelo, the already selected revision, casilla id when applicable, and field; one canonical builder validates membership, resolves continuity, and derives the dotted key. Callers never construct keys or provide continuity ids.

Dynamic identity components pass through one injective, reversible key-segment codec. A component matching `[A-Za-z0-9_-]+` and not beginning `x-` is preserved. Every other component, including a raw value beginning `x-`, is UTF-8 encoded as unpadded lowercase Base32hex and prefixed with `x-`. This keeps compound casilla ids opaque and collision-free while satisfying the shared locale-key segment grammar.

The shared YAML catalogues store these keys through their normal nested representation. The registry scanner enrolls every derived concrete key so the existing discovery, parity, CLI, honesty, and rendering contracts see the complete Modelo key universe. No Modelo-local TOML is part of the target representation.

The disposable migration's already sealed slash-delimited `canonical_key` values are migration-only occurrence addresses. They remain valid joins and evidence for extraction and review, but the emitter must translate them from their structured identity fields into the standardized dotted keys. No slash-delimited value may appear in emitted catalogues, runtime facades, CLI key arguments, or resolver results.

### D3 - Store each distinct value once and keep applicability language-neutral

Each distinct localized scalar is one ordinary shared-catalogue leaf under its standardized dotted key. Continuity bases use the continuity key. A genuine repeated divergence uses one derived variant key. An ungrounded occurrence uses its exact revision-occurrence key.

A language-neutral Modelo localization enrollment record selects which base, variant, exact key, or tombstone applies to each validated occurrence. It stores only canonical identities, key coordinates, revision applicability, and suppression state; it stores no localized value and no Spanish prose. It is compiled and validated with the Modelo registry authority, while the values it selects exist only in the shared locale catalogues.

A base leaf appears once per `(locale, continuidad_id, field)`. A variant value appears once per locale and one applicability record names every revision where it applies. Exact occurrence entries remain available when continuity is absent.

For one continuity id and field, applicability sets must reference existing revisions and must not overlap. A variant equal to the base, or two variants with equal values, is rejected as duplicate authored state. `suppress = true` is a field tombstone and cannot coexist with `value`.

The logical materialization is:

```text
effective(revision, locale) = base(locale) override applicable_variants(revision, locale) override exact_occurrence(revision, locale)
```

The right-biased union operates field by field and never persists another full revision catalogue.

**Amendment (2026-08-05) -- year-parameterized values.** The corpus census measured 247 candidate chains whose Spanish label differs across revisions only by an embedded filing-year token (`Vivienda habitual en 2020` / `Vivienda habitual en 2021`). Representing that class as per-revision variants re-authors the same wording every filing year in every locale, permanently. A locale value may therefore declare a year placeholder resolved from the selected revision's filing year at render time -- one declaration per chain, field, and locale -- provided the rendered string reproduces the official per-revision text exactly and regulatory and export consumers continue to receive the rendered official form, never the template. The emitter and migration classifier treat the year-token class as its own representation, and parity comparison always evaluates the rendered value.

### D4 - Resolve identities, applicability, and fallbacks deterministically

For a grounded casilla field, resolution checks one applicable continuity variant, then the continuity base. For an ungrounded occurrence, it checks the exact revision occurrence entry. A tombstone skips inherited localized values and proceeds to the field's terminal behavior.

For locale `es`, every required field must resolve from the shared Spanish catalogue. Missing Spanish is an error. Regulatory and export consumers explicitly request this strict source channel.

For a non-Spanish locale, an authored requested-locale value wins. A missing optional or incomplete translation may fall back only to the same key's mandatory Spanish value. Strict development and audit modes reject that fallback when locale completeness is required. No non-Spanish locale falls through to another non-Spanish locale.

`repurposed` ends continuity inheritance. `retired` values remain available only through supported historical revisions containing the occurrence. A later stable concept needs a new grounded continuity id.

### D5 - Preserve Spanish verbatim while removing schema language coupling

Migration copies each current official Spanish string into the `es` catalogue under its derived key before deleting the schema text field. Comparison uses parsed Unicode string equality and records the source field and source hash in the migration manifest.

Spanish is the translation source, not an optional localization. Every non-Spanish translation is reviewed against the Spanish value at the same canonical key. Legal and source references remain attached to the schema occurrence that derives the key, preserving provenance without using prose as identity.

The migration must inventory every natural-language schema field. A field classified as localizable moves to the catalogue. A field classified as identifier, legal reference, source reference, AEAT code, or evidence remains in schema or corpus data. Unclassified string fields block cutover.

**Amendment (2026-08-05) -- the inventory boundary extends beyond the Modelo tree.** A census of the non-Modelo registry surfaces found natural-language schema text the original scope did not name: the centralized user-profile schema carries 26 section titles and 162 field descriptions of deliberately mixed-language prose (its short labels already resolve through the locale catalogues, but the prose remains the wizard copy authority and the translation fallback), and the calendars (46), iva (36), and categories (8) trees carry candidate label and description strings; topics, treaties, and apoderamientos measured clean. The inventory must classify these surfaces under the same localizable-versus-identifier discipline before cutover -- either enrolling them in the shared locale-key system or recording an explicit decision for why their text stays schema-resident. A surface omitted from the inventory is itself an unclassified state and blocks cutover.

### D6 - Separate schema loading, locale loading, and caches

Remove `localized_labels`, `localized_help`, and natural-language presentation fields from materialized schema and facade contracts. Registry loading materializes complete language-neutral revisions without applying locale data.

The existing shared locale loader and renderer resolve Modelo keys like every other standardized locale key. Modelo enrollment and applicability may be cached with the validated registry snapshot, but localized values are loaded and invalidated through the shared catalogue cache only. Locale edits do not invalidate or mutate `ModeloDefinition` or calculation snapshots.

One resolver owns canonical key derivation, catalogue loading, applicability, tombstones, Spanish-source validation, requested-locale fallback, and diagnostics. Presentation boundaries request one locale and receive one scalar value and, when required, its canonical key.

### D7 - Use the standard locale CLI and retire Modelo-local authoring

The standard `cadrumo.locales` command family remains the only write authority for shared catalogue values. Modelo-aware enrollment tooling derives the concrete dotted keys and registers them with the shared scanner; catalogue writes, scaffold, removal, parity, and honesty checks then use the same CLI contract as every other application key.

The legacy `cadrumo.locales modelo` file-authoring commands and `ModeloLocaleManager` may remain read-only migration inputs only until the last Modelo is enrolled. They are removed with the old-layout reader after final cutover. They must never write target data or recreate deleted Modelo-local locale files.

Audit, scaffold, and coverage operate on enrolled shared keys. They report inherited, variant, exact, Spanish fallback, suppressed, unresolved, stale, ambiguous, repurposed, retired, key-echo, mirrored, and missing states. They reject duplicate applicability and any legacy locale file for an enrolled Modelo.

### D8 - Use a disposable migration application and sealed manifest

Migration is performed by a sophisticated one-shot application, not by manual editing. It executes five stages: extract, classify, emit, compare, and cut over.

Extraction runs against the pre-migration production loader and records every source leaf, every schema source string, the complete resolved matrix, and source hashes. Classification assigns each occurrence one of `grounded`, `revision_exact`, or `continuity_candidate` and records all structural and value drift.

The generated manifest carries Modelo, revision, casilla, continuity, provisional candidate id, locale, field, source location, raw value, old resolved value, Spanish source value, state, normalized hash, drift fields, review status, emitted target, and source hash. Existing sealed slash-delimited occurrence addresses remain immutable source evidence. Emission derives the standardized dotted target key from the structured identity columns and records that target separately; it does not reinterpret or rewrite the source seal.

Provisional continuity candidates remain manifest-only. The generator may emit intentionally unresolved required entries so strict validation produces a complete review list. It must not fabricate defaults, promote repeated ids, or hide work with key-echo placeholders.

Emission first runs in parity mode, preserving every old resolution through bases, variants, exact entries, and tombstones. Canonicalization mode consumes explicit chain and value decisions and records every approved parity difference. Target values are applied to the shared catalogues through the locale CLI or an equally validated batch surface owned by that CLI; the disposable application does not directly edit catalogue YAML.

The migration application and its old-layout reader are deleted after cutover. The sealed manifest and parity report remain as migration evidence; they do not become runtime authorities.

### D9 - Require exhaustive parity and atomic per-Modelo retirement

For every supported Modelo, revision, casilla occurrence, locale, and field, the target resolver must equal the sealed old resolved value or carry an explicit approved difference. Spanish migration additionally requires exact equality with every source schema string.

Parity covers revision selection, regulatory rendering, exports, calculation snapshots, CLI and application presentation, strict missing-key behavior, cache invalidation, locale audit, and the absence of all-locale maps in facades.

Each Modelo has one atomic enrollment boundary. Before deletion, the migration must prove that every supported revision, occurrence, locale, and field for that Modelo is enrolled in the standardized key schema; every required shared-catalogue leaf exists; strict Spanish, translation, rendering, export, and facade parity pass; and the legacy source hashes still match extraction.

Only after that proof may the migration switch the Modelo to shared-key resolution and delete all of its legacy localization files and migrated natural-language schema fields in the same scoped change. Mixed ownership may exist temporarily between unenrolled and enrolled Modelos during the campaign, but never within one enrolled Modelo. Rollback requires restoring the whole pre-cutover Modelo payload from migration evidence; production never reads both layouts.

The per-Modelo gate rejects `<modelo>/locales/**`, `<modelo>/revisions/**/locales/**`, natural-language fields classified as localizable, injected locale maps, duplicate logical leaves, overlapping applicability, unresolved required keys, missing Spanish source values, and any production fallback to the old layout. The final campaign gate proves zero legacy Modelo locale files remain and removes the migration-only reader, manager, and commands.

### D10 - Preserve the governing decision chain

This ADR continues to supersede `2026-06-08-registry-localization-backend-adr` and `2026-06-11-modelo-locales-cli-adr`.

`2026-05-27-schema-hardening-casilla-continuity-contract-adr` remains accepted and supplies continuity semantics. `2026-07-21-locale-key-resolution-adr` remains accepted for its separate category-key scope and supplies the read-time, strict-Spanish-key precedent.

## Rationale

The chosen design removes repeated text and language coupling without inventing a parallel identity system. Derived occurrence keys make schema authoring language-neutral. Grounded continuity defaults and explicit applicability sets declare each distinct value once without assuming a linear revision history.

The disposable migration application uses the current loader as an oracle, so mechanical work stays mechanical. Its unresolved manifest concentrates judgment at the real boundary: semantic continuity and canonical wording. This follows the evidence in `2026-08-04-modelo-localization-cascade-migration-feasibility-research` and avoids both a giant manual transcription campaign and unsafe semantic inference.

Making Spanish the mandatory source catalogue aligns Modelo localization with the rest of the application's typed-key system while preserving regulatory text exactly. Strict Spanish resolution replaces hard-coded Spanish fields; it does not weaken the official-text invariant.

## Consequences

- Revision schemas and runtime schema objects become language-neutral.
- Modelo localization joins the established dotted locale-key universe and uses only the shared runtime catalogues.
- Every official Spanish value moves verbatim into the mandatory shared `es` catalogue and remains the source for translation and regulatory rendering.
- Stable values and each distinct reviewed variant are declared once, with explicit revision applicability.
- The initial generated register may fail strict validation at every unresolved continuity or value decision; those failures are the review queue, not defects to hide.
- Physical migration, key generation, source extraction, override derivation, tombstones, and parity are automated.
- Manual review remains necessary for continuity approval, repurposing or retirement classification, canonical wording, and natural-language field classification.
- Locale edits no longer rebuild cached registry definitions or propagate maps through every facade.
- Cutover is atomic per Modelo: confirmed shared-key enrollment and parity precede deletion of every root and revision legacy locale file for that Modelo.
- Final campaign closure proves no Modelo-local locale file, legacy reader, `ModeloLocaleManager`, or legacy Modelo locale command remains.
- The migration application is intentionally disposable; only the normalized catalogue, sealed manifest, and parity evidence survive.
