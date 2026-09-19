---
tags:
  - '#audit'
  - '#registry-edition-authoring'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:6fc57cb10f88b26920de3d449345766e278260bdd3457db8562bed53392ee8cc'
related: []
---
# `registry-edition-authoring` audit: `migration gate coupling`

## Scope

Read-only implementation audit of Modelo 100 storage migration, edition hydration, migration tests and related TOML governance. Findings assess the requested field/value delta authoring contract, not whether the older whole-row contract was implemented intentionally. No runtime code, validators or registry data were changed for this audit. No security permission or encryption mechanism was found to be the cause of the observed migration refusal.

## Findings

### whole-row-deltas | high | A changed field retains the entire member

Open. `dev/registry/edition_delta_migration.py:1045` compares complete casillas through `restatement_differences` and effective row equality. `_plan_family_drop` likewise drops whole members, not repeated fields within differing members. This cannot deliver field-level delta storage when only references or annotations differ. The measured 2020/2021 source comparison found 13,344 identical values among 14,125 shared field paths; 1,208 of 1,500 shared casillas match after excluding only four provenance/continuity annotation keys. That exclusion is a diagnostic sensitivity analysis, not permission to discard those keys. Preserve differing evidence as deltas while sharing unchanged payload.

### lineage-gates-storage | high | One unannotated predecessor row blocks the entire edition

Open. `_choose_drops` rejects the edition if any inherited row lacks `continuidad_id`, before considering independently identical payload. `dev/registry/compiler/_loader_internals.py:949` couples casilla inheritance to continuity identity. `dev/registry/tests/test_revision_edition_materialisation.py:308` explicitly expects a collision without lineage to fail. The focused command `uv run --no-sync pytest -q dev/registry/tests/test_revision_edition_materialisation.py -k collision-without-lineage` passed: 1 test, exit 0. This confirms the current refusal contract, not its suitability for storage deduplication. A storage reference need not assert legally grounded continuity.

### technical-failure-as-root | high | Tool limitations are persisted as no-predecessor declarations

Open. Live Modelo 100 revision manifests for 2021 through 2025 carry `predecessor.none` reasons naming a predecessor row without lineage. `dev/registry/edition_delta_migration.py:1018` accepts a dictionary declaration as a root without reconsidering storage inheritance. The staged reenrollment probe refused at 2021 with `predecessor_row_without_lineage`. A missing annotation is not evidence that unchanged data cannot be reconstructed from an earlier source. Genuine independent roots remain meaningful; these technical-failure declarations are the problematic use.

### whole-history-blocking | high | The first historical failure stops the whole modelo plan

Open. `dev/registry/edition_delta_migration.py:840` plans all ordered revisions and refuses at the first blocked edition. The observed 2020-to-2021 boundary therefore stops later enrollment even though both years precede the declared supported floor. Historical sources can still be dependencies; the missing mechanism is dependency-aware migration scope, not unconditional deletion of old sources.

### capability-storage-coupling | high | A capability downgrade forbids storage inheritance

Open. `_choose_predecessor` rejects a lower authority grade; `dev/registry/compiler/_loader_internals.py:842` enforces the corresponding loader restriction. `dev/registry/tests/test_edition_delta_migration.py:394` locks this behavior. Sharing an unchanged payload need not promote the successor's capability. Grade preservation belongs to the hydrated result and filing eligibility, not a blanket prohibition on storage reuse. This is a broader restriction, not the reproduced first Modelo 100 blocker.

### claim-pins-row | medium | Continuity evidence can force unrelated values to remain repeated

Open. `dev/registry/tests/test_edition_delta_migration.py:284` expects a row stating only a lineage claim to remain authored. The separate family-drop path can already relocate such claims into `lineage_attestations`, demonstrating that preserving a claim does not inherently require retaining its entire row. The migration paths should preserve the same claim semantics without requiring duplicate payload.

### apply-publication-coupling | medium | Local source replacement depends on broader authority acceptance

Open. `dev/registry/edition_delta_migration.py:2045` and `:2237` invoke `compile_validated_authority` before applying staged data, after the round-trip report. All report findings also inhibit application. This couples a local representation rewrite to broader authority checks. Distinguish failures introduced by the rewrite from unchanged pre-existing capability or evidence failures; do not report a source-only proof as authority-publication acceptance. This audit did not reproduce a separate export-fixture refusal.

### representation-review-scope | medium | Review metadata is attached to physical inheritance shape

Open design restriction. `src/cadrumo/domain/calculations/registry/schema_governance.py:208` requires `reviewed_against` to match the predecessor for a reviewed inherited edition. `dev/registry/compiler/edition_materialisation.py` resets review status when detaching an edition into full materialization. A representation-only transformation can therefore invalidate a review claim. Review extent must remain truthful, but should be evaluated against reviewed meaning and provenance rather than physical duplication. Not established as the first Modelo 100 blocker.

### coarse-family-exclusions | medium | Entire-family policies limit delta minimality

Open design restriction. `src/cadrumo/domain/calculations/registry/keyed_families.py` retains per-edition families. `_NEVER_STRIPPED_SCALARS` in `dev/registry/edition_delta_migration.py:1605` names `orden_aplicabilidad` and `casilla_source_refs`. `restated_families` disables inheritance for a whole family and requires explanatory cause/reason fields. These scopes can be meaningful, but the representation cannot share identical constituent values in all such cases. Changing the declarations alone would not fix missing hydration support.

### completion-signal | medium | Passing equivalence does not demonstrate completed deduplication

Open reporting gap. A migration outcome can report changes and no gate findings while only lifting defaults and retaining every member. Earlier default-only classification through `_delta_authored` has already been corrected and is not an open defect. Remaining reporting should distinguish semantic equivalence, actual inherited members, removed repeated fields and unresolved eligible duplication. A green round trip alone is not a completed delta migration.

## Recommendations

Address whole-row-deltas, lineage-gates-storage and technical-failure-as-root together: the architectural decision to formalize is separation of lossless storage identity from semantic continuity claims, with deterministic field overrides and explicit deletion semantics. Do not infer legal continuity from a repeated box number.

For whole-history-blocking, compute the dependency closure of the migration scope. For capability-storage-coupling and representation-review-scope, preserve capability and truthful review scope without forcing full-copy storage. For claim-pins-row and coarse-family-exclusions, use one hydration contract that preserves per-revision annotations and ordering while sharing unchanged values.

For apply-publication-coupling and completion-signal, distinguish source equivalence, delta minimality and authority publication acceptance. Retain exact typed hydration comparisons, reference closure, ordering checks, cycle and ambiguity detection, and concurrent-input validation. None of these requires storing duplicate payload.

TOML cleanup candidates are technical-failure uses of `predecessor.none.reason/legal_refs/source_refs`, representation-bound `reviewed_against`, and coarse `restated_families` declarations. `continuidad_id`, continuity evidence, `authority_grade`, source/legal references and review records are not generically disposable security keys: their misuse as storage gates is the finding. No current use of retired `source_default_dispositions` was found in the inspected surfaces. Retained lock sidecars are not evidence of an active lock or a Modelo 100 migration blocker.
