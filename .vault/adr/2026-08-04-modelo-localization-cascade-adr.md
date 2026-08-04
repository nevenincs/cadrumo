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
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
  - '[[2026-07-21-locale-key-resolution-adr]]'
  - '[[2026-05-08-modelo-directory-segmentation-adr]]'
supersedes:
  - '2026-06-08-registry-localization-backend-adr'
  - '2026-06-11-modelo-locales-cli-adr'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3a6880e0c5d476f7c92746690cae064c8644efd984d7a6f22d2eaafbd66b088c'
---
# `modelo-localization-cascade` adr: `root-only language-neutral schema localization cascade` | (**status:** `accepted`)

## Problem Statement

Modelo schema localization currently stores natural-language text and injected locale maps on revision schema objects, then repeats translated values across revision directories and downstream projections. This snapshot-per-revision shape makes unchanged presentation data look like independently authored schema truth and imposes a large maintenance burden.

The system needs one canonical localization authority at each Modelo root. Schema identities must derive standardized localization keys without storing language-specific text. A root base set must declare each stable value once, while grouped revision applicability records declare only genuine divergences. The effective revision is a deterministic right-biased union.

The live corpus can be relocated and compared mechanically, but broad semantic collapse is blocked by incomplete continuity metadata. The migration must therefore generate an explicit review register rather than infer continuity or require manual file-by-file editing. The evidence and measured boundary are grounded in `2026-08-04-modelo-localization-cascade-research` and `2026-08-04-modelo-localization-cascade-migration-feasibility-research`.

This amended record continues to replace the storage, injection, and authoring decisions in `2026-06-08-registry-localization-backend-adr` and `2026-06-11-modelo-locales-cli-adr`.

## Considerations

- Modelo, selected revision, revision-local casilla id, and field are sufficient to derive one canonical occurrence key.
- Printed `number` and `segmento` remain AEAT metadata, not localization identity.
- `continuidad_id` remains the only authority for cross-revision semantic inheritance.
- Spanish is the mandatory source locale. Its current official strings must move verbatim to the root `es` catalogue before schema text is removed.
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
- **Use a root-only catalogue, derived keys, explicit revision applicability sets, and a generated migration manifest.** Chosen because it decouples language from schema, declares each value once, preserves legal revision selection, and makes unresolved work explicit.

## Constraints

- Revision selection remains law-determined. Localization receives an already selected revision and never infers chronology from sorting or a bare year.
- Every localizable natural-language field in Modelo, revision, casilla, and their presentation projections must move to a root locale catalogue. Schema records retain identifiers, legal/source grounding, structural metadata, and evidence, but no language-specific presentation value.
- Legal evidence bytes, citations, AEAT codes, identifiers, and non-presentational source material remain outside localization. A migration inventory must classify every schema string field against this boundary.
- The Spanish catalogue is mandatory and source-authoritative. A missing Spanish value for a required key is load-blocking; no humanized or cross-locale fallback may satisfy it.
- A `repurposed` evolution is an inheritance barrier. A value cannot cross that boundary without a new grounded continuity identity.
- Provisional migration candidates and unresolved markers are not production continuity ids. The production compiler must reject unresolved required keys.
- No production compatibility reader may preserve revision-directory locale files after cutover. Migration-only extraction may read the old shape.
- Root catalogue fragments must compile into one logical catalogue per locale. Duplicate logical declarations fail even when values match.
- The implementation preserves the supported locale set and never falls from one non-Spanish locale into another.

## Implementation

### D1 - Make Modelo-root locale catalogues the sole text authority

Every Modelo owns one logical catalogue per locale beneath its root `locales/` directory. Spanish (`es`) is always present and carries the verbatim source values. English, Catalan, and Hungarian use the same canonical keys.

No localization file may live beneath `revisions/`. Revision schema fragments and materialized schema models must not carry natural-language labels, help, titles, names, locale maps, or hand-authored localization keys.

A locale may use one file or fragmented files beneath its Modelo-root locale directory. Fragmentation is physical only. The compiled catalogue has one logical ownership surface and rejects duplicate leaves.

The root catalogue covers:

- Modelo presentation and official-name fields.
- Revision presentation fields.
- Casilla labels, help, aliases, section presentation, and any later schema field classified as localizable text.
- Cross-revision defaults and reviewed revision divergences.

### D2 - Derive canonical localization keys from schema identity

The public casilla occurrence key is:

```text
modelo/<modelo-id>/revision/<revision-id>/casilla/<casilla-id>/<field>
```

Modelo and revision fields use:

```text
modelo/<modelo-id>/campo/<field>
modelo/<modelo-id>/revision/<revision-id>/campo/<field>
```

Locale is a resolver argument, not part of semantic identity. Callers provide Modelo, selected revision, casilla id when applicable, and field. The canonical key builder validates occurrence membership and derives the key. Callers never construct keys, use printed numbers, or provide continuity ids.

Schema objects may expose a typed computed key at a presentation boundary, but the key is never repeated in authored revision data. Compound casilla ids remain opaque canonical ids.

### D3 - Store each distinct value once with explicit applicability

Each locale catalogue uses this logical shape:

```toml
[modelo]
title = "Localized Modelo title"
official_name = "Official localized Modelo name"

[revision_fields."2024"]
label = "Localized revision label"

[casillas."<continuidad-id>"]
label = "Default value"
help = "Default help"

[[casillas."<continuidad-id>".label_variants]]
value = "One divergent value"
revisions = ["2023", "2024", "2025"]

[[casillas."<continuidad-id>".help_variants]]
suppress = true
revisions = ["2020", "2021"]

[revision_occurrences."<revision-id>"."<casilla-id>"]
label = "Exact value without grounded continuity"
```

The Modelo id and locale are implied by the physical root. A base leaf appears once per `(locale, continuidad_id, field)`. A variant value appears once and names every revision where it applies. Exact occurrence entries remain available when continuity is absent.

For one continuity id and field, applicability sets must reference existing revisions and must not overlap. A variant equal to the base, or two variants with equal values, is rejected as duplicate authored state. `suppress = true` is a field tombstone and cannot coexist with `value`.

The logical materialization is:

```text
effective(revision, locale) = base(locale) ⊎ applicable_variants(revision, locale) ⊎ exact_occurrence(revision, locale)
```

The right-biased union operates field by field and never persists another full revision catalogue.

### D4 - Resolve identities, applicability, and fallbacks deterministically

For a grounded casilla field, resolution checks one applicable continuity variant, then the continuity base. For an ungrounded occurrence, it checks the exact revision occurrence entry. A tombstone skips inherited localized values and proceeds to the field's terminal behavior.

For locale `es`, every required field must resolve from the root Spanish catalogue. Missing Spanish is an error. Regulatory and export consumers explicitly request this strict source channel.

For a non-Spanish locale, an authored requested-locale value wins. A missing optional or incomplete translation may fall back only to the same key's mandatory Spanish value. Strict development and audit modes reject that fallback when locale completeness is required. No non-Spanish locale falls through to another non-Spanish locale.

`repurposed` ends continuity inheritance. `retired` values remain available only through supported historical revisions containing the occurrence. A later stable concept needs a new grounded continuity id.

### D5 - Preserve Spanish verbatim while removing schema language coupling

Migration copies each current official Spanish string into the `es` catalogue under its derived key before deleting the schema text field. Comparison uses parsed Unicode string equality and records the source field and source hash in the migration manifest.

Spanish is the translation source, not an optional localization. Every non-Spanish translation is reviewed against the Spanish value at the same canonical key. Legal and source references remain attached to the schema occurrence that derives the key, preserving provenance without using prose as identity.

The migration must inventory every natural-language schema field. A field classified as localizable moves to the catalogue. A field classified as identifier, legal reference, source reference, AEAT code, or evidence remains in schema or corpus data. Unclassified string fields block cutover.

### D6 - Separate schema loading, locale loading, and caches

Remove `localized_labels`, `localized_help`, and natural-language presentation fields from materialized schema and facade contracts. Registry loading materializes complete language-neutral revisions without applying locale data.

A dedicated root-catalogue loader validates and caches localization lazily by Modelo, locale, and root-catalogue fingerprint. Locale edits invalidate only the locale cache. They do not invalidate or mutate `ModeloDefinition` or calculation snapshots.

One resolver owns canonical key derivation, catalogue loading, applicability, tombstones, Spanish-source validation, requested-locale fallback, and diagnostics. Presentation boundaries request one locale and receive one scalar value and, when required, its canonical key.

### D7 - Keep the locale CLI as the sole authoring authority

The `cadrumo.locales modelo` command family remains the only write authority. Every command targets root catalogues and accepts Modelo, revision, casilla id, field, and locale as applicable. It derives keys and continuity internally.

Writes must state whether they create a continuity base, grouped variant, exact occurrence value, or tombstone. The CLI never infers authorial intent from text equality. Spanish writes preserve the source-authoritative contract and require the schema occurrence's grounding.

Audit, scaffold, and coverage operate on resolved keys. They report inherited, variant, exact, Spanish fallback, suppressed, unresolved, stale, ambiguous, repurposed, retired, key-echo, mirrored, and missing states. They reject duplicate applicability and revision-local locale files.

### D8 - Use a disposable migration application and sealed manifest

Migration is performed by a sophisticated one-shot application, not by manual editing. It executes five stages: extract, classify, emit, compare, and cut over.

Extraction runs against the pre-migration production loader and records every source leaf, every schema source string, the complete resolved matrix, and source hashes. Classification assigns each occurrence one of `grounded`, `revision_exact`, or `continuity_candidate` and records all structural and value drift.

The generated manifest carries Modelo, revision, casilla, continuity, provisional candidate id, locale, field, source location, raw value, old resolved value, Spanish source value, state, normalized hash, drift fields, review status, emitted target, and source hash.

Provisional continuity candidates remain manifest-only. The generator may emit intentionally unresolved required entries so strict validation produces a complete review list. It must not fabricate defaults, promote repeated ids, or hide work with key-echo placeholders.

Emission first runs in parity mode, preserving every old resolution through bases, variants, exact entries, and tombstones. Canonicalization mode consumes explicit chain and value decisions and records every approved parity difference.

The migration application and its old-layout reader are deleted after cutover. The sealed manifest and parity report remain as migration evidence; they do not become runtime authorities.

### D9 - Require exhaustive parity and one global deletion boundary

For every supported Modelo, revision, casilla occurrence, locale, and field, the target resolver must equal the sealed old resolved value or carry an explicit approved difference. Spanish migration additionally requires exact equality with every source schema string.

Parity covers revision selection, regulatory rendering, exports, calculation snapshots, CLI and application presentation, strict missing-key behavior, cache invalidation, locale audit, and the absence of all-locale maps in facades.

Root catalogues remain staged outside the live registry until all Modelos pass parity and source hashes still match extraction. Production then switches to the new resolver once, removes every revision locale file and migrated natural-language schema field, and rejects mixed ownership.

The final gate rejects `revisions/**/locales`, natural-language fields classified as localizable, injected locale maps, duplicate logical leaves, overlapping applicability, unresolved required keys, missing Spanish source values, and any production old-layout reader.

### D10 - Preserve the governing decision chain

This ADR continues to supersede `2026-06-08-registry-localization-backend-adr` and `2026-06-11-modelo-locales-cli-adr`.

`2026-05-27-schema-hardening-casilla-continuity-contract-adr` remains accepted and supplies continuity semantics. `2026-07-21-locale-key-resolution-adr` remains accepted for its separate category-key scope and supplies the read-time, strict-Spanish-key precedent.

## Rationale

The chosen design removes repeated text and language coupling without inventing a parallel identity system. Derived occurrence keys make schema authoring language-neutral. Grounded continuity defaults and explicit applicability sets declare each distinct value once without assuming a linear revision history.

The disposable migration application uses the current loader as an oracle, so mechanical work stays mechanical. Its unresolved manifest concentrates judgment at the real boundary: semantic continuity and canonical wording. This follows the evidence in `2026-08-04-modelo-localization-cascade-migration-feasibility-research` and avoids both a giant manual transcription campaign and unsafe semantic inference.

Making Spanish the mandatory source catalogue aligns Modelo localization with the rest of the application's typed-key system while preserving regulatory text exactly. Strict Spanish resolution replaces hard-coded Spanish fields; it does not weaken the official-text invariant.

## Consequences

- Revision schemas and runtime schema objects become language-neutral.
- Every official Spanish value moves verbatim into a mandatory root `es` catalogue and remains the source for translation and regulatory rendering.
- Stable values and each distinct reviewed variant are declared once, with explicit revision applicability.
- The initial generated register may fail strict validation at every unresolved continuity or value decision; those failures are the review queue, not defects to hide.
- Physical migration, key generation, source extraction, override derivation, tombstones, and parity are automated.
- Manual review remains necessary for continuity approval, repurposing or retirement classification, canonical wording, and natural-language field classification.
- Locale edits no longer rebuild cached registry definitions or propagate maps through every facade.
- Cutover is global and removes the old reader, revision locale directories, and migrated schema text together.
- The migration application is intentionally disposable; only the normalized catalogue, sealed manifest, and parity evidence survive.
