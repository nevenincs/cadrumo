---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ff9204c9ab81ca8d4a55c2a249f8c7c9e221c86adb1a614929dadba081c2abb4'
related:
  - "[[2026-08-03-canonical-storage-management-adr]]"
  - "[[2026-08-03-canonical-storage-management-research]]"
---
# `canonical-storage-management` audit: `Dev product boundary and storage CLI review`

## Scope

This review assessed the implementation against amendment rulings R24-R30 of the accepted canonical-storage-management ADR. The inspected surface covered the four-value `StorageArea` command contract and text rendering, public JSON and operator-surface projections, registry maintenance relocation, live-state and bucket-layout naming, compatibility residue, Hatch wheel/sdist selection, and the real-artifact boundary test.

Read-only verification exercised the exact installed console paths for `config storage show --help`, `config storage reclaim --help`, `config storage list`, `app registry --help`, and the repository-only `dev.registry.maintenance_cli --help`. A focused real-behavior test run covering storage management, storage CLI, registry CLI/payloads, dev parity/workbook behavior, and real wheel/sdist builds completed with 50 passing tests. Focused Ruff validation passed. Focused basedpyright reported two existing private-usage diagnostics for `_emit_envelope`; those diagnostics were outside the amendment-specific findings below and were not treated as proof of this boundary's correctness.

The artifact gate confirms that the built wheel and sdist exclude `.vault/`, `.vaultspec/`, and `dev/`. The product registry help no longer registers oracle-audit, workbook-verification, or parity run/replay leaves. Public storage JSON tested in this review contains no category, scope, node-kind, settings-field, bucket-id, or secret-store leaf projection.

## Findings

### storage-area-placement | medium | The new closed operator axis is outside core

`StorageArea` is declared in `src/cadrumo/application/storage_management/_models.py`. The always-on typed-boundary rule requires every constant-like closed axis to be a `StrEnum` in `core/`; R25 introduces exactly such an axis and does not authorize an application-layer exception. Keeping the public enum in the application package makes the CLI vocabulary depend on a placement that contradicts the repository's canonical ownership rule.

### internal-taxonomy-operator-contract | medium | The operator contract still names storage categories

The shipped CRUD/operator-surface catalogue registers the storage noun as `storage_category`, describes reset and initialization in category terms, and pins that wording in its tests. R26 explicitly prohibits `StorageCategory` and its internal vocabulary from operator-surface manifests. The executable CLI and JSON payloads correctly use areas, but the second shipped operator contract still records the retired internal noun and can drift independently from the actual four-area surface.

### storage-text-localization | medium | Readable layout is still rendered in hard-coded English

The table alignment and notice wrapping are visually readable, but `_storage_cli.py` hard-codes labels such as `Storage root`, `Areas`, `Lifecycle`, `Occupancy`, `Footprint`, and the `Info:` prefix. On the default Spanish invocation verified in this review, those labels render in English while the notice body renders in Spanish. The tests explicitly pin the English fragments. This leaves the four-locale product with a mixed-language informational surface and does not fully resolve the user-facing output-quality defect that motivated the amendment.

### retired-storage-documentation | medium | Removed audit and parity storage remains documented

`docs/reference/environment-overrides.md` still advertises `CADRUMO_AUDIT_DIR` and `CADRUMO_REGISTRY_PARITY_STORE_DIR`, even though R27, R28, and R30 require those product settings and their documentation to be deleted outright. The shipped bucket package docstring also still claims that bucket provisioning exposes a `db/`, `blobs/`, and `audit/` tree after R29 removed the writer-less audit directory. These stale claims direct operators and maintainers toward surfaces the implementation intentionally no longer recognizes.

### dev-parity-residue | high | A dev-only parity helper remains in the shipped package

`src/cadrumo/domain/calculations/registry/_scenario_filing_period.py` is now consumed only by `dev/registry/_parity_tapes.py` and wheel-excluded tests. Its own documentation identifies it as a shared validator for a parity scenario model that has moved to `dev/registry`. This is executable maintainer-only parity machinery left under `src/cadrumo`, directly violating R24's categorical product boundary and R27's capability-based relocation. The dev tape module additionally reaches both this helper and `selector_period_matches_request` through private product-module imports instead of the owning registry facade, contrary to the canonical import boundary.

## Recommendations

- Move `StorageArea` to its canonical `core/` owner, export it through the core facade, and update application, CLI, MCP/schema, and tests to import that one definition.
- Rename the storage CRUD/operator-surface noun to `storage_area`, rewrite its lifecycle commentary around aggregate areas, and add a gate that refuses internal storage-taxonomy vocabulary in shipped operator contracts.
- Put every storage text label and notice prefix through the locale catalogue authority in all four locales; update the real CLI tests to assert one coherent selected language while retaining the alignment and wrapping assertions.
- Regenerate the environment-overrides reference through its owning documentation generator after removing both retired variables, and correct the bucket package documentation to the live `db/` plus `blobs/` layout.
- Move the scenario-filing-period hydrator into `dev/registry` with the parity models that exclusively consume it. For the period-selector primitive that still has product consumers, promote the necessary symbol through the registry facade before importing it from dev; do not retain private-module reaches or a product re-export bridge for the dev-only helper.

The implementation should not be marked complete until the high finding and all R24-R30 medium findings are closed and the same exact console, focused test, artifact, locale, generated-document, Ruff, and type-check evidence is rerun.

## Re-review resolution log

### storage-area-placement | resolved | Core now owns the operator axis

`StorageArea` now originates in `src/cadrumo/core/_storage_taxonomy.py`, is exported by the canonical `cadrumo.core` facade, and is imported from that facade by the application service/models/errors, CLI payload and handler modules, and focused tests. No application-layer duplicate or re-export remains.

### internal-taxonomy-operator-contract | resolved | The shipped operator noun is storage area

The CRUD/operator-surface catalogue now registers `storage_area`; its commentary describes aggregate-area lifecycle operations, and the focused catalogue test pins the corrected noun. The executable public payload remains topology-neutral.

### retired-storage-documentation | resolved | Retired settings and bucket audit claims are absent

The CLI-owned environment reference is fresh according to `python -m dev.docs.env_reference --check`. Neither it nor `env/.env.example` contains the retired audit, registry-parity-store, workbook-timeout, or LibreOffice settings. The bucket package no longer documents an `audit/` child, and the reviewed bucket-layout and bucket-maintenance source contains no audit-directory field or test residue. Product `Settings` no longer declares a LibreOffice executable; workbook execution resolves that contributor concern under `dev/registry`.

### dev-parity-residue | resolved | Exclusive parity support is repository-only

The scenario-filing-period hydrator now lives under `dev/registry`; the old product module is absent and no shipped non-test module imports `dev`. The dev parity tape imports the product-shared period-selector function through the canonical registry facade, which now explicitly exports it, rather than reaching a private product module.

### storage-text-localization | medium | Spanish error and area values remain mixed-language

The correction localizes table headings, lifecycle values, occupancy values, Boolean labels, issue detail, and notice prefixes in all four catalogues. The exact Spanish list, show, and check commands are substantially improved and visually coherent around those fields. The finding is not fully resolved, however: text-mode area values still render as the English public tokens `state`, `logs`, `cache`, and `exports`, because the area column and show field emit `row.area.value` directly instead of a localized display label. More importantly, exact Spanish reclaim refusals still begin with the English shared heading `Refused`, interpolate the English reason `the area contains durable state`, and print English context keys. The unconfirmed path likewise emits `Refused` before its otherwise Spanish message. The focused Spanish success test only excludes two former English headings and therefore cannot catch either remaining mixed-language path.

### focused-proof | resolved | Corrected boundary passes its focused gates

A focused run spanning storage CLI and services, the operator CRUD catalogue, core taxonomy, dev parity/workbook behavior, environment-reference/config alignment, and the real wheel/sdist content gate completed with 161 passing tests. Focused Ruff validation passed. The generated environment reference check passed. The broader locale scaffold check remains red on ten missing and eleven extra keys per locale from concurrent unrelated modelo, ledger, overview, and root-landing work; none of those reported keys belongs to `cli.config.storage`, so it is not evidence against the storage corrections but it prevents claiming a globally clean locale gate.

## Re-review recommendation

Keep `StorageArea`'s canonical wire and argument tokens stable, but introduce localized text-mode display values for the four areas and use them in list, show, and storage-specific refusal prose. Route the storage refusal heading, reason, and human-facing context labels through the selected locale as well. Extend the Spanish real-CLI test to cover every area display value plus both durable and unconfirmed reclaim refusals; the current two-negative-string assertion is too narrow to establish one coherent output language.
