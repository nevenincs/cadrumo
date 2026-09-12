---
tags:
  - '#adr'
  - '#binding-schema'
date: '2026-09-11'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:425979c22bdea81a58bcca2461f8f1f5d18406cd8db84b199deda2adb6fdec82'
related:
  - "[[2026-09-11-binding-schema-provider-enrollment-design-research]]"
  - "[[2026-09-11-binding-schema-research]]"
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---

# `binding-schema` adr: `closed provider union and registration authority for revision-local bindings` | (**status:** `accepted`)

## Problem Statement

A binding is the timeless semantic join point between a data source and a form slot. Today its revision-local declaration is `source` plus an untyped `selector` mapping, hydrated by a lookup dict, validated by a second dict, and routed by a third table in application code. The declared type is open, the serialized form is not self-describing, seven authored source kinds reach calculation with no route owner, relations restate every temporal and source axis of the prefill binding, and one selector carries an absolute filing year. The edition-authoring decision now inherits bindings by edition-free identifier, so the declaration must carry stable intent only and close, through one enrolled authority, to a typed terminal origin. Evidence: `2026-09-11-binding-schema-provider-enrollment-design-research`, `2026-09-11-binding-schema-research`.

## Considerations

- Hydration into per-family models is enrolled; the closed type, single enrollment authority, and self-describing serialization are not (`2026-09-11-binding-schema-research`, partial-migration finding).
- Route ownership already enforces one owner per kind, unique resolver ids, and complete coverage at import time; those invariants can move, not be rebuilt (`2026-09-11-binding-schema-provider-enrollment-design-research`, enrollment matrix).
- Governed facts already ship a real discriminated union and a provider-registration compiler seam (`2026-09-09-facts-registry-governed-fact-catalogue-adr`).
- Any family whose members carry a stable edition-free identity key inherits across editions under one general rule; a binding keys on its identifier, withdrawal is an authored retirement in `binding_evolutions`, and no per-binding lineage field exists (`2026-09-09-registry-edition-authoring-adr`, "What a successor edition declares").
- No released public compatibility floor exists, so displaced shapes are removed in the same change (`no-legacy-compatibility`).
- Fourteen resolver sites re-read selector fields; the cut is only complete when they narrow on typed members.

## Considered options

- **Keep `source + selector` and harden the three dispatch tables.** Least corpus churn; leaves the type open, serialization untagged, and enrollment split across tables that can disagree. Rejected.
- **Move bindings into the governed-facts catalogue.** Gains the union and registration seam for free; conflicts with the accepted facts scope and conflates a value-production route with a governed fact. Rejected.
- **Replace the content of revision-local `bindings/*.toml` with `BindingDefinition(provider=BindingProvider)` and one `BindingProviderRegistration` authority.** Preserves the enrolled loader and authority flow, closes the type, and makes enrollment a single join. Chosen.
- **Relations kept separate with a typed `relation_id` reference.** Would require bidirectional closure validation and keep a second identified family with its own evolutions section, all to preserve a declaration that duplicates every axis of the provider. Rejected.
- **Relations absorbed into `RelationPrefillProvider`.** One declaration per join; deletes the duplicate temporal grammar. Chosen.

## Constraints

- The binding merge in the edition materialiser is scheduled after the casilla migration. The corpus is therefore rewritten to the provider shape now while remaining full-copy per edition; dropping restated rows under the inheritance rule is a separate step sequenced behind the materialiser.
- The bundled authority artifact in the current checkout is stale relative to the authored tree, so runtime-parity proof requires a fresh publication before acceptance gates run.
- The identifier rename tool must treat the `modelo-232-2016.*` and `modelo-232-2018.*` pairs as one lineage, and the edition-token detector must split on `.` as well as `-` and `:`.
- Pydantic discriminated unions need a literal `kind` on every member; `BindingSourceKind` values are the literal set, with mesh-only members excluded from the union.

## Implementation

The authored row becomes `id`, `provider`, `value`, `aggregation`, `applicability`, `terminal_origins`, `authorship`, `aeat_prefilled`, and evidence references; `provider` is a closed union discriminated on `kind`, and each provider carrying a source coordinate embeds one closed relative `temporal` member. Absolute years and revision identifiers are refused in authored TOML. A `BindingProviderRegistration` in its own public module joins each kind to its model, validator, permitted value channels, aggregation operations, terminal-origin classes, output shape, disposition, route owner or explicit non-runtime ownership, and authoring support; the selector, validator, and route tables become derived views or are deleted, and the import-time route invariants move onto it. The compiler refuses unregistered kinds, registrations without model, validator, or route, channel and cardinality mismatches, terminal-origin classes the registration cannot produce, unreferenced bindings without an explicit disposition, and alternates whose value contract differs from the primary. The runtime provenance model is unchanged; a new check asserts the resolved origin class falls inside the authored expectation. Compiler-derived metadata (occurrence coordinate, inherited-from edition, fragment path, ordinal, fingerprint, reverse consumer index) is emitted, not authored. Relations are absorbed, `relations/*.toml` and the relation models are deleted, and each former relation target carries its own provider declaration. Two consequences of absorption decided on the corpus evidence: the temporal union gains a `filing_year_offset_by_target_period` member (a mapping from target period to year offset plus source periods) because modelo 202's art. 40.2 LIS instalment takes the base from two filing years back at 1P and one year back at 2P and 3P, a legal variation that is authored as typed data rather than split across two binding identities; and because `CalculationRevision.relation_overrides` is persisted keyed by relation id and feeds the revision-id hash, the cut carries a forward, deterministic, idempotent stored-data migration that rekeys those overrides to binding ids from a frozen relation-to-binding table captured from the pre-cut corpus and records the old-to-new revision id pairs it produces. The corpus is rewritten in one hard cut using the rename tool's pattern, after which the inheritance rule removes restated rows. A binding's value channel alone says whether it yields a row collection: `channel = row_set` means rows and `data_type` is then the per-row element type (`money`, `integer`, `boolean`, `text`, `date`, `enum`), the retired `rows` data type is removed from `BindingDataType`, a scalar channel keeps the existing one-to-one `data_type`/`channel` table, and because two distinct row channels exist at runtime — the grouped row-set assembler for the families enrolled in `ROW_SET_GROUPING_FOR_BINDING_SOURCE` and provider-native row emission for the invoice, inventory, and repeating-profile families — `row_grouping` is optional on the contract and its presence is required, and required to equal the canonical entry, exactly when the registration's derived `row_assembly` is `grouped`, refused when it is `provider_native`.

## Rationale

The registration authority is the knockout: every other option leaves at least two tables that must agree for a provider kind to be real, and the seven unowned kinds are the proof that they do not. Absorbing relations wins because the research shows every relation field except `kind` and `dependency_role` is already a provider or temporal field, and keeping relations would carry a second identified family through the general inheritance rule for a declaration that adds nothing. The four decisions recorded here were settled with the edition-authoring supervisor on the research evidence: the unowned kinds are an enrollment defect (status partial, refused once the registration lands, ROWS exemption retired in the same change); relations are absorbed; the inventory absolute year is a defect replaced by a temporal member; the 232 pairs collapse to one edition-free identifier declared once and inherited.

## Consequences

Gains: one self-describing authored shape, one enrollment authority, no untagged serialization, refusal of absolute coordinates, deletion of the relation family and its duplicate grammar, and a compile-time terminal-origin contract that runtime provenance can be audited against. Difficulties: a corpus rewrite of every binding row and every relation, fourteen resolver edits across owners, and coordination with the in-flight materialiser. Pitfalls: the union must not be declared landed until the registration table is the only dispatch source and the three "discriminated" docstrings are gone; a `deferred` disposition must remain visible in calculation diagnostics rather than becoming a new silent gap. Opens: generated bindings with authoring lineage, and a reverse consumer index that retires the four ad-hoc alternate-binding re-splats. Debt recorded: `src/cadrumo/domain/iva_compensation/filed_derivation.py` reaches for `RegistryQueryService` in `src/cadrumo/domain/calculations/registry/queries.py`, and the provider cut had to make that import `TYPE_CHECKING`-only to break the cycle `schema -> binding_provider -> iva_compensation_annual_partition_bindings -> filed_derivation -> queries -> schema`; the import trick hides a domain module depending on a query service, and the fix is to pass the needed revision data into `filed_derivation` rather than the service.
