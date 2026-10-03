# Usage ratios and user-profile domain

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-153` · **Topic:** [Business and taxpayer domain](../topics/business-and-taxpayer-domain.md)

<!-- preserved:article -->
## Scope

This chunk covers 15 files (4,255 lines; 38,832 measured tokens) across `domain/usage_ratios` and `domain/user_profile`. It includes per-category usage-ratio profiles, censo-derived home-office ratios and concurrency locking; the profile schema, values, labels, and registry contract; setup answers and workforce facts; forward migration; quarter-set parsing; and a portable-export record. It does not include the persistence adapters, setup wizard, or sealed archive transport.

## Product capabilities

Usage-ratio profiles hold operator overrides for business-use proportions, separate from legal IVA prorrata. Eligibility comes from the complete category-profile corpus under a generation-pinned authority rather than from one filing year, so a saved override can remain readable across year changes. Profiles are frozen, ratio-bounded, canonicalized by category order, and resolved purely after decoding. The transaction-reference validator requires a concrete eligible spending category, equality between the row category and ratio ID, an active profile entry, and—when the row has one—agreement between `business_pct` and the profile ratio. Home-office ratios are derived from censo affectation and the selected year's category multiplier; a per-bucket file lock protects the adapter’s read-modify-save sequence from lost updates (usage-ratio profile (`src/cadrumo/domain/usage_ratios/model.py`), censo derivation and lock (`src/cadrumo/domain/usage_ratios/service.py`)).

The user-profile schema declares fields, types, requiredness, effective dating, sensitivity, enum values, model selectors, schedule predicates, numeric bounds, and legal references. Schema methods provide canonical path lookup and selector-to-field resolution; derived selectors are anchored, placeholder-checked patterns that declare engine-owned namespaces without supplying values. A registry-contract walk compares Modelo profile bindings, filing schedules, deadlines, and cross-reference applicability predicates to that schema, returning typed blocking errors and nonblocking coverage warnings (schema declarations (`src/cadrumo/domain/user_profile/schema.py`), registry contract (`src/cadrumo/domain/user_profile/registry_contract.py`)).

Profile values distinguish a live editable record from immutable filing snapshots. Creation and decoding require explicit pinned create/decode contexts; schema identity and provenance are validated against that exact schema. Fact restoration converts canonical JSON strings back to dates, booleans, and decimals without turning leading-zero identifiers such as postcodes into numbers. Record revisions require a previous digest after the first revision, records carry a canonical content digest, and snapshots sort and hash their facts and revalidate that hash on load. Schema 6→7 migration removes only stored false values for three legacy payer facts, preserves true answers, records cleared paths as event data, and exposes which cleared facts still need an answer. Setup answers are a separate typed wizard model with explicit blank sentinels and registry-backed tax tokens; quarter sets are validated and emitted in canonical order (fact restoration and digests (`src/cadrumo/domain/user_profile/values.py`), snapshot creation (`src/cadrumo/domain/user_profile/values.py`), migration (`src/cadrumo/domain/user_profile/schema_migration.py`), setup answers (`src/cadrumo/domain/user_profile/setup_answers.py`)).

Other profile helpers supply localized labels and structured field help, validate indexed annual workforce facts as observed or committed values, and define a v3 portable bundle containing the profile, financial-history records, decrypted secure-object payloads encoded as canonical base64, and a namespace-coverage manifest. The bundle carries natural object keys and sensitivity classifications so recipient-side adapters can re-key and re-encrypt data. Its schema version is mandatory; recipient bundle lineage owns version acceptance and migration (profile labels (`src/cadrumo/domain/user_profile/labels.py`), workforce records (`src/cadrumo/domain/user_profile/plantilla_media.py`), portable bundle (`src/cadrumo/domain/user_profile/portable_export.py`)).

## Security and quality assessment

The domain uses strict frozen records, path/type validation, declared sensitivity classes, immutable hashes, and pinned schema contexts to limit drift between stored values and the schema that interprets them. Profile snapshots are integrity-checked against their canonical content; profile IDs are generated UUIDs rather than taxpayer identifiers. The portable bundle deliberately holds decrypted object payload bytes in its model, so the archive layer must provide the confidentiality and integrity protection described by its import/export contract. This chunk has only the payload shape, not that cryptographic transport. Its coverage manifest validates names and nonnegative row counts but does not, within this model, prove that carried and excluded namespaces are disjoint or that counts match the actual carried rows; the transport-aware workflow must enforce those relationships.

Several local contract mismatches need attention. First, the home-office derivation docstring says an affectation ratio of 100% is forbidden, but the range check rejects only values below zero or above one; exactly `1` reaches the derivation and can produce a full ratio for ownership categories. This confirms a local acceptance mismatch, while end-to-end impact depends on whether the censo write/read boundary already rejects `office_m2 == total_m2`. Enforce the stated strict upper bound here or make the accepted legal range consistent across the censo and usage-ratio paths (range check (`src/cadrumo/domain/usage_ratios/service.py`)).

Second, profile label helpers claim to fall back to the schema’s declared title/description, but `profile_section_title` and `profile_field_label` call `tr` without passing `section.title` or `field.description` as a default. The field helper receives the full `field` object yet only uses its key. On a missing translation, this implementation cannot provide the documented schema-text fallback; the locale catalog or scaffolder may mask the gap in normal operation, but the public helper contract is not self-sufficient (label lookups (`src/cadrumo/domain/user_profile/labels.py`), field-label lookup (`src/cadrumo/domain/user_profile/labels.py`)).

Third, snapshot creation documents a deterministic default ID derived from profile state, but `new_profile_snapshot_id` includes a fresh UUID and `create_user_profile_snapshot` uses it when no ID is supplied. Snapshot contents and canonical hash are deterministic for identical inputs, but the default snapshot ID is intentionally unique, not reproducible. Callers relying on idempotent snapshot IDs should supply an explicit ID or correct the documentation (ID generator (`src/cadrumo/domain/user_profile/values.py`), default selection (`src/cadrumo/domain/user_profile/values.py`)).

Setup-answer date validators use `date.fromisoformat` directly, while the central profile schema explicitly limits date strings to the extended `YYYY-MM-DD` spelling. The wizard model therefore does not state or enforce the same lexical contract at this boundary. Route answers through the shared strict date parser/shape check so the value accepted during setup is the same value the persisted profile accepts (setup date validators (`src/cadrumo/domain/user_profile/setup_answers.py`), profile date rule (`src/cadrumo/domain/user_profile/schema.py`)).

## Dependencies and follow-up

The profile domain depends on compiled authority contexts, registry-derived category and tax vocabularies, core hashes/time/identity, and application/adapter layers for persistence, censo guarding, setup, and portable archive sealing. Confirm the strict censo ratio invariant at both write and calculation boundaries; repair label fallback and snapshot-ID documentation; align setup date parsing with the profile schema; and validate portable-manifest coverage against actual rows before import. The version-6 migration record also accepts arbitrary `from_version`/`to_version` values at its model boundary, although its functions and constants describe only the 6→7 hop; callers should ensure events cannot claim a different transition. No tests, adapters, or callers are included here, so this review cannot establish how these model-level gaps affect actual saves, exports, or calculations.

## Complete assigned-file coverage

- `src/cadrumo/domain/usage_ratios/__init__.py`
- `src/cadrumo/domain/usage_ratios/errors.py`
- `src/cadrumo/domain/usage_ratios/model.py`
- `src/cadrumo/domain/usage_ratios/service.py`
- `src/cadrumo/domain/user_profile/__init__.py`
- `src/cadrumo/domain/user_profile/errors.py`
- `src/cadrumo/domain/user_profile/labels.py`
- `src/cadrumo/domain/user_profile/plantilla_media.py`
- `src/cadrumo/domain/user_profile/portable_export.py`
- `src/cadrumo/domain/user_profile/quarter_sets.py`
- `src/cadrumo/domain/user_profile/registry_contract.py`
- `src/cadrumo/domain/user_profile/schema.py`
- `src/cadrumo/domain/user_profile/schema_migration.py`
- `src/cadrumo/domain/user_profile/setup_answers.py`
- `src/cadrumo/domain/user_profile/values.py`
<!-- /preserved:article -->
