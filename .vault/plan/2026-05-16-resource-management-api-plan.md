---
tags:
  - '#plan'
  - '#resource-management-api'
date: '2026-05-16'
tier: L2
related:
  - '[[2026-05-16-resource-management-api-adr]]'
  - '[[2026-05-16-resource-management-api-research]]'
  - '[[2026-05-16-resource-management-api-audit]]'
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `resource-management-api` plan

Consolidate the 31 named loader functions, 11 production module-
level `_DEFAULT_*_ROOT` constants, 20+ scattered `@lru_cache`
decorators, 5 separate `ValidatedRegistryAuthority.load`
construction paths, and 9 CLI typer-argument defaults behind a
single typed `Repository[T, K]` per resource type registry at
`aeat.core.resources`. Builds directly on the corpus-registry-
packaging boundary; the existing `packaged_data`, `bundled_path`,
`as_path` surface stays exposed via the new package's `_boundary`
module.

## Proposed Changes

Twelve Repositories cover the existing surface: six singletons
(apoderamientos, user-profile schema, topics, recargo bands, VAT
rate tables, legal parameters), three year-keyed (holiday
calendars, category profiles, VAT catalogues), one composite-
keyed (manuals via `(manual_id, year, part)`), one singleton
with rich lookup (normatives), and one façade over
`ValidatedRegistryAuthority` (modelos).

The Settings env-override seam for `aeat_manuals_root`,
`aeat_normatives_root`, and `aeat_vat_catalogue_root` is
preserved verbatim; the `resources()` factory reads Settings
once at construction and hands resolved roots to the three
relevant Repository constructors. Cache surface collapses from
20+ heuristic `@lru_cache` decorators (sizes 1 through 4096) to
one unbounded `dict[K, T]` Identity Map per Repository. The
error model gains three top-level types
(`ResourceNotFoundError`, `ResourceValidationError`,
`ResourceBackendError`) that superclass the existing per-domain
errors without breaking existing `except` clauses.

A pre-execution discovery sweep using parallel Sonnet agents on
top of the prior Haiku sweep surfaced two classes of test that
must be treated differently:

(a) Tests that load a typed domain resource (a `Manual`, a
`VATCatalogue`, a `ModeloDefinition`, etc.) migrate to the
Repository surface: `resources().manuals.get(...)` replaces
`load_manual(...)`, etc. The semantic shape is preserved.

(b) Tests that deliberately read a raw bundled file via
`bundled_path(...).read_text()` or `bundled_path(...).glob(...)`
to verify the on-disk tree SHAPE (the existence of a manifest,
the presence of a TOML key, the count of files in a directory)
STAY on the `bundled_path` boundary and do not migrate to
Repository calls. These tests test the data layout itself, not
the Repository contract. The structural-guard test in P10.S92
explicitly allow-lists this pattern: direct `bundled_path`
reads are permitted inside test files that verify the data-
tree shape; only consumer code in production paths is guarded.

The discovery sweep also identified two additional eager module-
level loads beyond the four originally documented in the ADR:
`VAT_RATE_TABLE` in `domain.vat._rates:118` and
`LIVA_ART_161_RECARGO` in `domain.vat._recargo_equivalencia:114`
(set via a private `_load_rates` wrapper that lazily imports
`load_legal_parameters_only`). These retire in P09 alongside the
originally-named eager loads. The sweep also catalogued every
`__init__.py` re-export of loader symbols across 19 packages;
P09.S96 prunes the now-obsolete public `load_*` names from
`__all__`.

The migration is sliceable Repository by Repository. Each slice
introduces one Repository, migrates its production consumers,
migrates its test consumers, and retires its legacy
`_DEFAULT_*_ROOT` constant. The diff is mechanical and the
quality gate runs at every phase boundary. All identifier-
affecting structure under the Steps section is owned by the
`vault plan` CLI.

## Steps

### Phase `P01` - foundation: Repository base + ResourceRegistry shell + resources() factory

Land the new src/aeat/core/resources/ package replacing the single-file module. Introduce Repository[T, K] base, ResourceKey discriminated union, ResourceLoadError hierarchy, empty ResourceRegistry shell, and resources() factory. Re-export packaged_data/bundled_path/as_path from a _boundary module so existing imports keep working. No consumer migrates yet; the slice is purely additive.

- [ ] `P01.S01` - Convert src/aeat/core/resources.py into a package and move existing packaged_data, bundled_path, as_path into a _boundary submodule; `src/aeat/core/resources/_boundary.py`.
- [ ] `P01.S02` - Implement the Repository protocol and a default base class with an Identity Map dict cache and clear_cache method; `src/aeat/core/resources/_repository.py`.
- [ ] `P01.S03` - Implement the ResourceKey discriminated union plus the twelve typed key models (one per Repository); `src/aeat/core/resources/_keys.py`.
- [ ] `P01.S04` - Implement the three top-level error classes ResourceLoadError, ResourceNotFoundError, ResourceValidationError, ResourceBackendError; `src/aeat/core/resources/_errors.py`.
- [ ] `P01.S05` - Implement the ResourceRegistry dataclass and resources() factory function reading Settings once at construction; `src/aeat/core/resources/_registry.py`.
- [ ] `P01.S06` - Re-export the foundation surface from the new package __init__ preserving backwards-compatible imports of packaged_data, bundled_path, as_path; `src/aeat/core/resources/__init__.py`.
- [ ] `P01.S07` - Add real-behaviour foundation tests covering Repository base, ResourceKey discrimination, error hierarchy, and registry factory; `src/aeat/core/resources/test_registry.py`.

### Phase `P02` - singleton repositories

Implement eight singleton-keyed Repositories: apoderamientos, user_profile_schema, topics, recargo_bands, vat_rate_tables, legal_parameters, plus the two retiring module-level eager loads (VAT_CATALOGUES_BY_YEAR consumers and LIRPF_ART_85_IMPUTACION consumers). Each Repository owns its Identity Map.

- [ ] `P02.S08` - Implement ApoderamientosRepository wrapping load_default_catalogue with K=None singleton convention and .singleton property; `src/aeat/core/resources/_repos/apoderamientos.py`.
- [ ] `P02.S09` - Implement UserProfileSchemaRepository wrapping load_user_profile_schema as a singleton; `src/aeat/core/resources/_repos/user_profile.py`.
- [ ] `P02.S10` - Implement TopicCatalogueRepository wrapping load_topic_catalogue as a singleton with _TOPIC_REGISTRY_ROOT folded in; `src/aeat/core/resources/_repos/topics.py`.
- [ ] `P02.S11` - Implement RecargoBandsRepository wrapping load_recargo_bands as a singleton; `src/aeat/core/resources/_repos/recargo_bands.py`.
- [ ] `P02.S12` - Implement VatRateTableRepository wrapping load_vat_rate_table as a singleton; `src/aeat/core/resources/_repos/vat_rate_tables.py`.
- [ ] `P02.S13` - Implement LegalParameterRepository wrapping load_legal_parameters_only as a singleton; `src/aeat/core/resources/_repos/legal_parameters.py`.
- [ ] `P02.S14` - Add real-behaviour tests for the six singleton Repositories covering get, .singleton sugar, and clear_cache; `src/aeat/core/resources/_repos/test_singletons.py`.

### Phase `P03` - year-keyed repositories

Implement three int-year-keyed Repositories: holiday_calendars, category_profiles, vat_catalogues. Each takes a Settings-derived root where applicable.

- [ ] `P03.S15` - Implement HolidayCalendarRepository with int-year key wrapping load_holiday_calendar; `src/aeat/core/resources/_repos/holiday_calendars.py`.
- [ ] `P03.S16` - Implement CategoryProfileRepository with int-year key wrapping load_category_profile_registry and resolve_category_profiles; `src/aeat/core/resources/_repos/category_profiles.py`.
- [ ] `P03.S17` - Implement VatCatalogueRepository with int-year key wrapping load_vat_catalogues and resolve_catalogue; `absorb the AEAT_VAT_CATALOGUE_ROOT Settings field; `src/aeat/core/resources/_repos/vat_catalogues.py`.
- [ ] `P03.S18` - Add real-behaviour tests for the three year-keyed Repositories; `src/aeat/core/resources/_repos/test_year_keyed.py`.

### Phase `P04` - manual repository with composite key

Implement ManualRepository with the composite (manual_id, year, part) Pydantic key. Subsume resolve_part_root, load_manual, load_section, iter_sections, find_rules, load_catalogue, load_manifest, verify_fetched_pdf, verify_manual_dir.

- [ ] `P04.S19` - Implement ManualRepository with composite ManualKey covering resolve_part_root, load_manual, load_section, iter_sections, find_rules, load_catalogue, load_manifest, verify_fetched_pdf, verify_manual_dir; `src/aeat/core/resources/_repos/manuals.py`.
- [ ] `P04.S20` - Add real-behaviour tests for ManualRepository covering composite key resolution, catalogue iteration, and section lookup; `src/aeat/core/resources/_repos/test_manuals.py`.

### Phase `P05` - normative repository

Implement NormativeRepository with a singleton catalogue plus typed lookup methods (find_reference, find_articulo). Settings env-override seam preserved for aeat_normatives_root.

- [ ] `P05.S21` - Implement NormativeRepository with singleton catalogue plus find_reference and find_articulo lookup methods; `absorb the AEAT_NORMATIVES_ROOT Settings field; `src/aeat/core/resources/_repos/normatives.py`.
- [ ] `P05.S22` - Add real-behaviour tests for NormativeRepository covering singleton get, reference lookup, and articulo lookup; `src/aeat/core/resources/_repos/test_normatives.py`.

### Phase `P06` - modelo repository as a facade over ValidatedRegistryAuthority

Implement ModeloRepository as a thin wrapper around the existing ValidatedRegistryAuthority. Preserve its validator and snapshot caches. Migrate the five separate ValidatedRegistryAuthority.load construction paths to resources().modelos.

- [ ] `P06.S23` - Implement ModeloRepository as a thin facade over ValidatedRegistryAuthority preserving its validator and snapshot caches; `key is ModeloKey(id: str); `src/aeat/core/resources/_repos/modelos.py`.
- [ ] `P06.S24` - Add real-behaviour tests for ModeloRepository covering get, all, and the authority backing surface; `src/aeat/core/resources/_repos/test_modelos.py`.
- [ ] `P06.S25` - Wire all twelve Repositories into the ResourceRegistry dataclass and verify the resources() factory composes them correctly under Settings overrides; `src/aeat/core/resources/_registry.py`.

### Phase `P07` - production consumer migration

Migrate the 25-30 production consumer modules from their existing load_* / _DEFAULT_*_ROOT imports to from aeat.core.resources import resources. Order: domain layer first, then application, then adapters, then entrypoints CLI defaults.

- [ ] `P07.S26` - Migrate the registry corpus module manuals normatives and topics resolution to resources(); `src/aeat/application/registry/_corpus.py`.
- [ ] `P07.S27` - Migrate the registry application package init to resources(); `src/aeat/application/registry/__init__.py`.
- [ ] `P07.S28` - Migrate the diagnostics version and repair surfaces to resources(); `src/aeat/application/diagnostics.py`.
- [ ] `P07.S29` - Migrate the topics application package init to resources(); `src/aeat/application/topics/__init__.py`.
- [ ] `P07.S30` - Migrate the filing runtime schema provider to resources(); `src/aeat/application/filing/runtime.py`.
- [ ] `P07.S31` - Migrate the filing application package init to resources(); `src/aeat/application/filing/__init__.py`.
- [ ] `P07.S32` - Migrate the verification declaracion verifier to resources(); `src/aeat/application/verification/_verify.py`.
- [ ] `P07.S33` - Migrate the live filed data capture to resources(); `src/aeat/application/live/__init__.py`.
- [ ] `P07.S34` - Migrate the modelo work-unit actions to resources(); `src/aeat/application/modelo/_actions.py`.
- [ ] `P07.S35` - Migrate the renta ledger aggregation to resources(); `src/aeat/application/aggregation/_renta_ledger.py`.
- [ ] `P07.S36` - Migrate the default_registry_authority singleton as a thin shim that delegates to resources().modelos to resources(); `src/aeat/domain/calculations/registry/_authority.py`.
- [ ] `P07.S37` - Migrate the calculate_registry_snapshot lazy bundled_path import to resources(); `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [ ] `P07.S38` - Migrate the run_registry_calculation_scenario wrapper to resources(); `src/aeat/domain/calculations/registry/_scenarios.py`.
- [ ] `P07.S39` - Migrate the manuals loader public surface to delegate to resources().manuals to resources(); `src/aeat/domain/manuals/_loader.py`.
- [ ] `P07.S40` - Migrate the manuals fetch and load_manifest to resources(); `src/aeat/domain/manuals/_fetch.py`.
- [ ] `P07.S41` - Migrate the manuals verifier to resources(); `src/aeat/domain/manuals/_verify.py`.
- [ ] `P07.S42` - Migrate the normatives loader public surface to delegate to resources().normatives to resources(); `src/aeat/domain/normatives/_loader.py`.
- [ ] `P07.S43` - Migrate the normatives verifier to resources(); `src/aeat/domain/normatives/_verify.py`.
- [ ] `P07.S44` - Migrate the vat catalogue module dropping the eager VAT_CATALOGUES_BY_YEAR module-level load to resources(); `src/aeat/domain/vat/_catalogue.py`.
- [ ] `P07.S45` - Migrate the vat rates module to resources(); `src/aeat/domain/vat/_rates.py`.
- [ ] `P07.S46` - Migrate the vat recargo-equivalencia parameter loader to resources(); `src/aeat/domain/vat/_recargo_equivalencia.py`.
- [ ] `P07.S47` - Migrate the deadlines engine class internal authority bootstrap to resources(); `src/aeat/domain/deadlines/_engine.py`.
- [ ] `P07.S48` - Migrate the deadlines festivos calendar loader to resources(); `src/aeat/domain/deadlines/_festivos.py`.
- [ ] `P07.S49` - Migrate the deadlines recargo bands loader to resources(); `src/aeat/domain/deadlines/_recargo.py`.
- [ ] `P07.S50` - Migrate the categories profile registry loader to resources(); `src/aeat/domain/categories/_registry.py`.
- [ ] `P07.S51` - Migrate the categories corpus aggregator to resources(); `src/aeat/domain/categories/_corpus.py`.
- [ ] `P07.S52` - Migrate the user_profile schema loader to resources(); `src/aeat/domain/user_profile/_loader.py`.
- [ ] `P07.S53` - Migrate the apoderamientos catalogue loader to resources(); `src/aeat/domain/auth/apoderamientos/_catalogue.py`.
- [ ] `P07.S54` - Migrate the rental imputacion-parameters module dropping the eager LIRPF_ART_85_IMPUTACION load to resources(); `src/aeat/domain/rental/_imputacion_parameters.py`.
- [ ] `P07.S55` - Migrate the declaracion inbound parser to resources(); `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [ ] `P07.S56` - Migrate the sede outbound declarations module to resources(); `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `P07.S57` - Migrate the registry CLI command surface to resources(); `src/aeat/entrypoints/cli/registry.py`.
- [ ] `P07.S58` - Migrate the live-app CLI surface to resources(); `src/aeat/entrypoints/cli/_app_live.py`.
- [ ] `P07.S59` - Migrate the CLI common helpers to resources(); `src/aeat/entrypoints/cli/_common.py`.
- [ ] `P07.S60` - Migrate the modelo CLI command surface to resources(); `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P07.S61` - Migrate the google calc CLI sync command to resources(); `src/aeat/entrypoints/cli/_config/_google.py`.

### Phase `P08` - test consumer migration

Migrate the ~100 test modules from their per-module _REGISTRY_ROOT constants and direct loader calls to resources(). Tests that override Settings continue to work because the factory reads Settings at the override point; conftest fixtures invoke resources.cache_clear().

- [ ] `P08.S62` - Migrate the calculations registry test suite under registry/ from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/calculations/registry/`.
- [ ] `P08.S63` - Migrate the manuals domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/manuals/`.
- [ ] `P08.S64` - Migrate the normatives domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/normatives/`.
- [ ] `P08.S65` - Migrate the vat domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/vat/`.
- [ ] `P08.S66` - Migrate the deadlines domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/deadlines/`.
- [ ] `P08.S67` - Migrate the categories domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/categories/`.
- [ ] `P08.S68` - Migrate the user-profile domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/user_profile/`.
- [ ] `P08.S69` - Migrate the apoderamientos test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/auth/apoderamientos/`.
- [ ] `P08.S70` - Migrate the rental imputacion tests from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/rental/`.
- [ ] `P08.S71` - Migrate the calculations application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/calculations/`.
- [ ] `P08.S72` - Migrate the aggregation application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/aggregation/`.
- [ ] `P08.S73` - Migrate the filing application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/filing/`.
- [ ] `P08.S74` - Migrate the modelo application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/modelo/`.
- [ ] `P08.S75` - Migrate the registry application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/registry/`.
- [ ] `P08.S76` - Migrate the verification application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/verification/`.
- [ ] `P08.S77` - Migrate the live application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/live/`.
- [ ] `P08.S78` - Migrate the topics application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/topics/`.
- [ ] `P08.S79` - Migrate the calc-sheets storage application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/storage/calc_sheets/`.
- [ ] `P08.S80` - Migrate the declaracion inbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/inbound/declaracion/`.
- [ ] `P08.S81` - Migrate the sede outbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/outbound/aeat/sede/`.
- [ ] `P08.S82` - Migrate the google outbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/outbound/google/`.
- [ ] `P08.S83` - Migrate the export outbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/outbound/aeat/export/`.
- [ ] `P08.S84` - Migrate the registry CLI test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/entrypoints/cli/`.

### Phase `P09` - retirement of legacy surface

Delete the 11 production module-level _DEFAULT_*_ROOT constants. Delete the 20+ scattered @lru_cache decorators on loaders that have folded into Repositories. Remove the public load_* re-exports from domain __init__ files. Drop the eager module-level VAT_CATALOGUES_BY_YEAR and LIRPF_ART_85_IMPUTACION loads now that consumers go through Repositories.

- [ ] `P09.S85` - Delete the eleven production module-level _DEFAULT_*_ROOT constants now that their Repository owns the root resolution; `src/aeat/domain/`.
- [ ] `P09.S86` - Delete the scattered @lru_cache decorators on every loader that has folded into a Repository; `src/aeat/domain/`.
- [ ] `P09.S87` - Remove the public load_* re-exports from domain package __init__ files; `src/aeat/domain/`.
- [ ] `P09.S88` - Drop the eager VAT_CATALOGUES_BY_YEAR module-level load now that consumers go through resources().vat_catalogues; `src/aeat/domain/vat/_catalogue.py`.
- [ ] `P09.S89` - Drop the eager LIRPF_ART_85_IMPUTACION module-level load now that consumers go through resources().legal_parameters; `src/aeat/domain/rental/_imputacion_parameters.py`.
- [ ] `P09.S90` - Remove the legacy default_registry_authority shim once every caller has switched to resources().modelos; `src/aeat/domain/calculations/registry/_authority.py`.
- [ ] `P09.S94` - Drop the eager VAT_RATE_TABLE module-level load now that consumers go through resources().vat_rate_tables; `src/aeat/domain/vat/_rates.py`.
- [ ] `P09.S95` - Drop the eager LIVA_ART_161_RECARGO module-level load (via private _load_rates wrapper) now that consumers go through resources().legal_parameters; `src/aeat/domain/vat/_recargo_equivalencia.py`.
- [ ] `P09.S96` - Audit every __init__.py re-export of loader symbols and prune the now-obsolete public load_* names from __all__; `src/aeat/domain/`.

### Phase `P10` - quality gate + structural guard + release docs

Run ruff + ty + pytest. Add a structural test asserting the registry is the only resource-access surface (greps for bundled_path and _DEFAULT_*_ROOT outside core/resources/). Update RELEASING.md or other operator-facing surfaces only if the migration changed them.

- [ ] `P10.S91` - Run the project quality gate ruff, ty, pytest with the unit marker, and the structural audits declared in the justfile; `justfile`.
- [ ] `P10.S92` - Add a structural test asserting resources() is the only resource-access surface in the project by grepping for bundled_path and _DEFAULT_*_ROOT outside core/resources/; `src/aeat/core/resources/test_single_surface_invariant.py`.
- [ ] `P10.S93` - Update operator-facing release documentation only if the migration changed the operator surface; `RELEASING.md`.

## Parallelization

The canonical execution order is `P01 -> P02 -> P03 -> P04 ->
P05 -> P06 -> P07 -> P08 -> P09 -> P10`. Within phases:

P01 (foundation) is strictly sequential because the steps build
on each other: S01 (package conversion) precedes S02 (Repository
base), which precedes S03 (key models), S04 (errors), S05
(registry), S06 (init re-exports), and S07 (foundation tests).

P02 (singleton repositories) parallelises freely across its six
Repository implementations (S08-S13). S14 (tests) strictly
follows.

P03 (year-keyed repositories) parallelises across S15-S17. S18
(tests) strictly follows.

P04 (manuals) and P05 (normatives) are independent of P02-P03
once P01 is in place and can run alongside P02-P03 if a
parallel executor is available. P04 has 2 sequential steps; P05
has 2 sequential steps.

P06 (modelos) strictly follows P01-P05 because the registry-wire
step (S25) needs every Repository class to exist first.

P07 (production consumer migration) strictly follows P06 because
consumers call `resources()` which composes every Repository.
Within P07, the 36 file-scoped steps parallelise freely; conflicts
arise only when two steps touch the same file, which file
scoping prevents.

P08 (test consumer migration) strictly follows P07. The 23
cohesive-area steps parallelise across test directories;
conflicts are prevented by the directory-disjoint scoping.

P09 (retirement) strictly follows P08 because the legacy
constants and decorators can only be removed once no consumer
references them. Within P09, S85-S90 plus S94-S96 may all run
in parallel (each step is file-disjoint).

P10 (quality gate) strictly follows P09. S91, S92, S93 may run
in parallel.

## Verification

The plan is complete when every Step is closed and the
following real-behaviour checks pass:

The foundation tests in `src/aeat/core/resources/test_registry.py`
and the per-Repository test modules under
`src/aeat/core/resources/_repos/test_*.py` exercise every
Repository's `get`, `find`, `all`, `clear_cache`, and the
singleton `.singleton` sugar with real bundled data.

The structural single-surface invariant test in
`src/aeat/core/resources/test_single_surface_invariant.py`
greps the project for any `bundled_path(` or
`_DEFAULT_*_ROOT =` outside `src/aeat/core/resources/` and
fails the gate if any are found. The test catches future
regressions where a contributor adds a parallel resource-access
surface.

No occurrence of `load_registry_tree`, `load_modelo_file`,
`load_modelo_directory`, `load_catalogue_file`,
`load_legal_parameters_only`, `load_manual`, `load_section`,
`iter_sections`, `find_rules`, `resolve_part_root`,
`load_manifest`, `verify_fetched_pdf`, `verify_manual_dir`,
`load_catalogue` (manuals or normatives), `find_reference`,
`find_articulo`, `verify_catalogue`, `load_vat_catalogue`,
`load_vat_catalogues`, `resolve_catalogue`, `load_vat_rate_table`,
`load_recargo_bands`, `load_holiday_calendar`,
`load_category_profile_file`, `load_category_profile_registry`,
`resolve_category_profiles`, `load_user_profile_schema`,
`load_topic_catalogue`, or `load_default_catalogue` is imported
or called from any consumer module outside its owning Repository
implementation.

No occurrence of `_DEFAULT_CATALOGUE_PATH`,
`_DEFAULT_PROFILE_ROOT`, `_DEFAULT_REGISTRY_ROOT`,
`_DEFAULT_SOURCE_ROOT`, `_CALENDARS_DIR`,
`_DEFAULT_BRACKET_PATH`, `DEFAULT_USER_PROFILE_SCHEMA_PATH`,
`_DEFAULT_CATALOGUE_ROOT`, `_DEFAULT_RATE_REGISTRY`,
`_TOPIC_REGISTRY_ROOT`, or `_DEFAULT_WORKBOOK_ROOT` remains
anywhere under `src/aeat/`.

No module-level eager load of bundled data remains (the
historical `VAT_CATALOGUES_BY_YEAR`, `VAT_RATE_TABLE`,
`LIRPF_ART_85_IMPUTACION`, and `LIVA_ART_161_RECARGO` module-
level constants are gone; their consumers go through Repository
methods).

The Settings env-override seam continues to work for
`AEAT_MANUALS_ROOT`, `AEAT_NORMATIVES_ROOT`, and
`AEAT_VAT_CATALOGUE_ROOT`. Override tests under
`src/aeat/application/registry/test_corpus.py` and any test that
uses `override_settings(aeat_*_root=...)` pass without
modification.

The full project quality gate completes clean: ruff, ty,
pytest with the unit marker, and the structural audits
declared in the justfile.

The built-wheel manifest assertion from the prior corpus-
registry-packaging feature in
`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`
continues to pass; the new `src/aeat/core/resources/` package
rides along inside the existing `packages = ["src/aeat"]`
hatchling directive.
