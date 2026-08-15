---
tags:
  - '#research'
  - '#modelo-localization-cascade'
date: '2026-08-04'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e10dafc200164c9022283d8157edeebfba9534ff605800c45e25716bd49cb940'
related:
  - '[[2026-08-04-modelo-localization-cascade-research]]'
  - '[[2026-08-04-modelo-localization-cascade-adr]]'
---
# `modelo-localization-cascade` research: `mechanical migration feasibility`

This investigation asks whether a disposable migration application can replace the current revision-local localization layout with the shared standardized locale-key schema. The live corpus supports deterministic extraction, shared-catalogue enrollment, exhaustive parity comparison, and per-Modelo deletion of the legacy layout after enrollment is proven. It does not yet support automatic semantic collapse across most revisions because only 18 of 15,774 casilla occurrences declare `continuidad_id`. The migration can still generate every occurrence address, move every current value, and emit an intentionally unresolved conflict register. Manual review can then operate per proposed continuity chain and distinct value variant instead of per file or localization leaf. The operator requires official Spanish text to move verbatim into the shared Spanish catalogue as the mandatory translation source, leaving schema records language-neutral. The authorizing ADR must settle grouped revision applicability, strict Spanish-source resolution, and the verified legacy-deletion boundary.

## Findings

### The current loader is a deterministic extraction oracle

The current locale compiler reads Modelo-root catalogues by `continuidad_id`, reads revision catalogues by revision-local `casilla.id`, validates both key spaces, and applies revision values after Modelo values. `CasillaDefinition.get_label` then falls back to the official Spanish label, while `get_help` returns no value when localization is absent. These contracts expose the full pre-migration resolved matrix without reconstructing behavior from files: `src/cadrumo/domain/calculations/registry/_loader_locales.py:112`, `src/cadrumo/domain/calculations/registry/_loader_locales.py:181`, `src/cadrumo/domain/calculations/registry/_loader_locales.py:207`, `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:313`, and `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:317`.

The live registry locale parity test passed both cases on 2026-08-04. It loads the complete registry tree and verifies representative English, Catalan, and Hungarian resolutions, so extraction can use the production loader rather than a hand-copied resolver: `src/cadrumo/domain/calculations/registry/tests/test_registry_locales_parity.py:18`; verification command `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_registry_locales_parity.py -q` returned `2 passed`.

### The physical corpus can be migrated mechanically

A read-only inventory found 73 directory-mode Modelos, 90 revisions, 15,774 casilla occurrences, and 281 locale TOML files. Of the locale files, 278 live under revision subtrees and three live at the Modelo 100 root. The files contain 42,057 localization leaves: 25,737 revision labels, 16,296 revision help values, and 24 Modelo-root leaves. Their only table families are `[labels]` and `[help]`; no tombstone, suppression, Modelo metadata, revision metadata, or grouped-applicability syntax exists.

The manager already exposes a typed extraction row containing Modelo, revision, scope, field, storage key, source casilla id, source continuity id, and official Spanish label. It also rejects duplicate keys across fragments and writes deterministic sorted TOML: `src/cadrumo/locales/_modelo_manager.py:118`, `src/cadrumo/locales/_modelo_manager.py:288`, `src/cadrumo/locales/_modelo_manager.py:669`, `src/cadrumo/locales/_modelo_manager.py:1085`, and `src/cadrumo/locales/_modelo_manager.py:1093`.

These properties make deterministic occurrence addressing and shared-catalogue enrollment mechanical. A migration application can derive a sealed source coordinate such as `modelo/<modelo>/revision/<revision>/casilla/<casilla-id>/<field>` from validated schema identities. That slash-delimited coordinate is useful migration evidence, but it is not the production locale key and does not need to be authored into each revision record.

### The existing locale-key contract fixes the production notation

The application already derives standardized dotted locale keys from schema structure. User-profile section and field identities become `profile.schema.section.<section>.title` and `profile.schema.field.<section>.<field>.label`, then the registry scanner enrols the complete derived set in the shared locale toolchain: `src/cadrumo/domain/user_profile/_labels.py:61`, `src/cadrumo/domain/user_profile/_labels.py:73`, and `src/cadrumo/locales/_registry_scanner.py:44`. The shared CLI also accepts dotted keys as its authoring address: `src/cadrumo/locales/manager.py:367`.

The in-flight disposable migration currently names its slash-delimited source coordinate `canonical_key`: `dev/registry/migration/manager.py:334`. That record is deterministic and suitable for manifest joins, but allowing it to become the runtime key would create a second localization-key grammar beside the established dotted contract. Reconciliation therefore preserves existing sealed manifests as migration evidence, treats their slash values as migration-only occurrence addresses, and derives dotted Modelo locale keys at the emission boundary. Target values enroll in the existing shared runtime catalogues; Modelo-root and revision-local TOML remain extraction inputs only and are deleted after the owning Modelo passes enrollment and parity.

### Continuity coverage is the blocker to automatic semantic collapse

Only 18 casilla occurrences participate in four grounded continuity chains; 15,756 occurrences carry no `continuidad_id`. Across the corpus, 2,358 casilla-id groups repeat in more than one revision. Four groups, covering the 18 grounded occurrences, are fully grounded. The remaining 2,354 groups, covering 11,755 occurrences, are fully ungrounded.

The continuity contract intentionally forbids treating a repeated numeric id or label as proof of cross-revision identity. `CasillaDefinition.id` identifies an occurrence inside a selected revision, while `continuidad_id` owns cross-revision semantic identity: `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:210`, `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:285`, and `2026-05-27-schema-hardening-casilla-continuity-contract-adr`.

The live evolution corpus contains `unchanged`, label evolution, legal-reference evolution, combined label/legal evolution, and one retirement. It contains no `repurposed` declaration. Four revisions opt into strict continuity validation. The one retirement is grounded at `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/continuidad/1038-2024-2025-retired.toml:1`. No duplicate continuity id was found inside one revision.

A lossless migration therefore needs no continuity inference: ungrounded occurrences can move as exact shared-catalogue revision keys. Achieving broad deduplication requires approving continuity chains or expanding the identity contract; a migration application may propose candidates but must not promote them silently.

### Drift classification can reduce review from leaves to chains and variants

The 2,354 ungrounded repeated-id groups divide into 1,835 groups whose measured structural core is stable and 519 groups with structural drift. The measured core included `number`, `segmento`, data type, semantic role, input kind, formula, binding, form number, and revision occurrence identity. This is triage evidence, not continuity proof.

Only 88 ungrounded groups resolve uniformly across all three translated locales and both fields. Authored label variants occur in 1,548 Catalan groups, 1,708 English groups, and 1,860 Hungarian groups. Forty-six Catalan groups collapse after conservative Unicode normalization, whitespace normalization, case folding, and trailing punctuation removal. Help observations are more regular: in each locale, 2,177 groups have one authored help variant plus missing revisions, and 177 have no authored help.

The stored quality states also matter. The corpus contains 24 Hungarian key-echo labels, 24 Hungarian key-echo help values, and 9,453 help values that mirror a label. No blank values were found. The existing manager classifies these states explicitly and counts only authored values as translated: `src/cadrumo/locales/_modelo_manager.py:51`, `src/cadrumo/locales/_modelo_manager.py:1017`.

A generated review register can therefore group all occurrences by candidate chain, list distinct values once per locale and field, and attach the revisions that use each variant. One reviewer decision can resolve an entire chain. Reviewing 42,057 leaves individually is unnecessary.

### A deliberately unresolved register is safer than fabricated defaults

The disposable application can assign a provisional candidate-chain id in its migration manifest and emit a strict unresolved marker for every unapproved chain. Provisional ids must not enter `CasillaDefinition.continuidad_id` or a production continuity default. The production compiler should reject unresolved markers, while the report remains queryable by Modelo, confidence, drift field, value variant, and affected revision.

Each manifest observation should contain:

```text
modelo_id
revision_id
casilla_id
continuidad_id
candidate_chain_id
locale
field
source_path
source_scope
raw_value
old_resolved_value
official_fallback
leaf_state
normalized_value_hash
drift_fields
review_status
emitted_target
source_hash
```

The application should classify observations as `grounded`, `revision_exact`, or `continuity_candidate`. It should retain key echoes, mirrored help, missing values, and genuine variants as separate states rather than normalizing them into authored text.

### Shared-catalogue emission can preserve behavior without manual editing

For grounded chains, the emitter can preserve continuity defaults and derive sparse divergences from the captured old matrix. For ungrounded casillas, it can emit exact shared-catalogue revision keys. If a selected base would make a previously missing translation inherit a value, the language-neutral enrollment can add a field tombstone to preserve the old Spanish or no-help fallback.

This process separates two modes:

- Parity mode preserves every old resolution exactly, including placeholders and mirrored help.
- Canonicalization mode applies reviewed continuity and value decisions, with every intentional parity difference recorded in the manifest.

The migration should run parity mode first. Canonicalization can then consume explicit decisions without losing the original oracle.

### Exact revision overrides do not fully collapse repeated variants

The accepted ADR serializes an override under one exact `(revision_id, casilla_id)` address. That representation preserves behavior, but it repeats one divergent value when several revisions share the same variant. Implicit chronological inheritance is unsafe because revision applicability is law-determined and need not form one linear chain: `src/cadrumo/domain/calculations/registry/_temporal.py:58`.

The evidence favors one declaration per distinct value plus an explicit revision applicability set. The ADR must decide a representation equivalent to:

```toml
[[casillas."<continuidad-id>".overrides]]
revisions = ["2023", "2024", "2025"]
label = "One canonical value"
```

Applicability must reference existing revisions, may not overlap for the same field, and must resolve through the selected occurrence. Exact occurrence entries remain necessary when continuity is absent.

### Official Spanish becomes the mandatory source catalogue

Current locale files contain English, Catalan, and Hungarian values. Official Spanish casilla labels remain natural-language fields on `CasillaDefinition`, and `ModeloDefinition.title`, `ModeloDefinition.official_name`, and `ModeloRevision.label` are also schema text: `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:234`, `src/cadrumo/domain/calculations/registry/_schema.py:999`, `src/cadrumo/domain/calculations/registry/_schema.py:1094`, and `src/cadrumo/domain/calculations/registry/_schema.py:1095`.

Replacing injected localization maps, repeated translated values, and schema text with derived keys is mechanical because Modelo, revision, casilla, and field already determine the key. The operator directive requires migration to copy every official Spanish value verbatim into the shared `es` catalogue before removing the schema field. Spanish becomes the mandatory source locale from which other locales are translated. Regulatory and export consumers must resolve the same key through a strict official-Spanish channel with no humanized, cross-locale, or missing-value fallback.

This pattern already exists elsewhere in the application. Typed records carry translation keys, validation proves the key has an authoritative Spanish catalogue value, and all four locales resolve at read time. `LedgerImportDiagnostic.message` is a typed key whose validator refuses a missing Spanish value: `src/cadrumo/application/transactions/_diagnostics.py:59`, `src/cadrumo/application/transactions/_diagnostics.py:79`. The renderer's strict mode treats a key echo as missing, and locale audits resolve Spanish, English, Catalan, and Hungarian through the same key surface: `src/cadrumo/core/i18n/tests/test_key_echo_resolution.py:1`, `src/cadrumo/application/wizard/_translations.py:27`.

The language-neutral schema boundary must distinguish localizable natural-language fields from identifiers and evidence. Legal references, source references, fixed AEAT codes, and bundled evidence bytes remain schema or corpus data. Every operator-facing or regulatory natural-language field in Modelo and casilla definitions must instead carry or derive a localization key. A migration inventory must enumerate these fields rather than assuming the current label/help scope is exhaustive.

No translated Modelo or revision metadata exists in the current locale files. The migration can derive their canonical keys and seed Spanish from the current schema values. Authoring non-Spanish metadata remains new localization work rather than migration.

### The one-shot application needs a sealed oracle and one deletion boundary

The application should execute five stages: extract, classify, emit, compare, and cut over.

Extraction records source hashes and the complete old resolved matrix before production localization injection changes. Emission writes a staging tree outside the live registry. Comparison evaluates every `(modelo, revision, casilla, locale, field)` through the target resolver and records exact equality or an approved difference.

The current registry cache fingerprints every revision locale file together with schema data, and the compiled loader injects locales before constructing `ModeloDefinition`: `src/cadrumo/domain/calculations/registry/_loader.py:232`, `src/cadrumo/domain/calculations/registry/_loader.py:287`, and `src/cadrumo/domain/calculations/registry/_loader.py:1192`. The target design must separate schema and locale fingerprints before cutover.

Generated shared-catalogue changes and enrollment records can be reviewed Modelo by Modelo. For each Modelo, source hashes must still match extraction and the new resolver must pass exhaustive parity before production switches that Modelo and deletes all of its root and revision locale files. Mixed ownership is permitted only between Modelos during the campaign, never inside an enrolled Modelo. A final negative gate rejects every Modelo-local locale file, injected locale map, duplicate logical leaf, unresolved required translation, and production old-layout reader.

### The investigation did not validate translation correctness

The analysis classified stored and resolved values but did not judge linguistic quality, legal equivalence, or the correctness of proposed continuity chains. It did not author Spanish catalogue values or choose canonical wording among variants. Those are the explicit review surfaces produced by the migration manifest.

## Sources

- `src/cadrumo/domain/calculations/registry/_loader_locales.py:112`
- `src/cadrumo/domain/calculations/registry/_loader_locales.py:181`
- `src/cadrumo/domain/calculations/registry/_loader_locales.py:207`
- `src/cadrumo/domain/calculations/registry/_loader.py:232`
- `src/cadrumo/domain/calculations/registry/_loader.py:287`
- `src/cadrumo/domain/calculations/registry/_loader.py:1192`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:210`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:234`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:285`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:313`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py:317`
- `src/cadrumo/domain/calculations/registry/_schema.py:999`
- `src/cadrumo/domain/calculations/registry/_schema.py:1094`
- `src/cadrumo/domain/calculations/registry/_schema.py:1095`
- `src/cadrumo/domain/calculations/registry/_temporal.py:58`
- `src/cadrumo/locales/_modelo_manager.py:51`
- `src/cadrumo/locales/_modelo_manager.py:118`
- `src/cadrumo/locales/_modelo_manager.py:288`
- `src/cadrumo/locales/_modelo_manager.py:669`
- `src/cadrumo/locales/_modelo_manager.py:1017`
- `src/cadrumo/locales/_modelo_manager.py:1085`
- `src/cadrumo/locales/_modelo_manager.py:1093`
- `src/cadrumo/domain/calculations/registry/tests/test_registry_locales_parity.py:18`
- `src/cadrumo/application/transactions/_diagnostics.py:59`
- `src/cadrumo/application/transactions/_diagnostics.py:79`
- `src/cadrumo/core/i18n/tests/test_key_echo_resolution.py:1`
- `src/cadrumo/application/wizard/_translations.py:27`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2025/continuidad/1038-2024-2025-retired.toml:1`
- `2026-05-27-schema-hardening-casilla-continuity-contract-adr`
- `2026-08-04-modelo-localization-cascade-research`
- Read-only corpus inventory using `ModeloLocaleManager`, `load_modelo_directory_without_locales`, and the current root/revision resolution precedence on 2026-08-04.
