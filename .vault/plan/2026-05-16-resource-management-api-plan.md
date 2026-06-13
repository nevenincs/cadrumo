---
tags:
  - '#plan'
  - '#resource-management-api'
date: '2026-05-16'
modified: '2026-05-16'
tier: L2
related:
  - '[[2026-05-16-resource-management-api-adr]]'
  - '[[2026-05-16-resource-management-api-research]]'
  - '[[2026-05-16-resource-management-api-audit]]'
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
---


# `resource-management-api` plan

### Phase `P01` - foundation: Repository base + ResourceRegistry shell + resources() factory

Land the new src/aeat/core/resources/ package replacing the single-file module. Introduce Repository[T, K] base, ResourceKey discriminated union, ResourceLoadError hierarchy, empty ResourceRegistry shell, and resources() factory. Re-export packaged_data/bundled_path/as_path from a _boundary module so existing imports keep working. No consumer migrates yet; the slice is purely additive.

- [x] `P01.S01` - Convert src/aeat/core/resources.py into a package and move existing packaged_data, bundled_path, as_path into a _boundary submodule; `src/aeat/core/resources/_boundary.py`.
- [x] `P01.S02` - Implement the Repository protocol and a default base class with an Identity Map dict cache and clear_cache method; `src/aeat/core/resources/_repository.py`.
- [x] `P01.S03` - Implement the ResourceKey discriminated union plus the twelve typed key models (one per Repository); `src/aeat/core/resources/_keys.py`.
- [x] `P01.S04` - Implement the three top-level error classes ResourceLoadError, ResourceNotFoundError, ResourceValidationError, ResourceBackendError; `src/aeat/core/resources/_errors.py`.
- [x] `P01.S05` - Implement the ResourceRegistry dataclass and resources() factory function reading Settings once at construction; `src/aeat/core/resources/_registry.py`.
- [x] `P01.S06` - Re-export the foundation surface from the new package __init__ preserving backwards-compatible imports of packaged_data, bundled_path, as_path; `src/aeat/core/resources/__init__.py`.
- [x] `P01.S07` - Add real-behaviour foundation tests covering Repository base, ResourceKey discrimination, error hierarchy, and registry factory; `src/aeat/core/resources/test_registry.py`.

### Phase `P02` - singleton repositories

Implement eight singleton-keyed Repositories: apoderamientos, user_profile_schema, topics, recargo_bands, vat_rate_tables, legal_parameters, plus the two retiring module-level eager loads (VAT_CATALOGUES_BY_YEAR consumers and LIRPF_ART_85_IMPUTACION consumers). Each Repository owns its Identity Map.

- [x] `P02.S08` - Implement ApoderamientosRepository wrapping load_default_catalogue with K=None singleton convention and .singleton property; `src/aeat/core/resources/_repos/apoderamientos.py`.
- [x] `P02.S09` - Implement UserProfileSchemaRepository wrapping load_user_profile_schema as a singleton; `src/aeat/core/resources/_repos/user_profile.py`.
- [x] `P02.S10` - Implement TopicCatalogueRepository wrapping load_topic_catalogue as a singleton with _TOPIC_REGISTRY_ROOT folded in; `src/aeat/core/resources/_repos/topics.py`.
- [x] `P02.S11` - Implement RecargoBandsRepository wrapping load_recargo_bands as a singleton; `src/aeat/core/resources/_repos/recargo_bands.py`.
- [x] `P02.S12` - Implement VatRateTableRepository wrapping load_vat_rate_table as a singleton; `src/aeat/core/resources/_repos/vat_rate_tables.py`.
- [x] `P02.S13` - Implement LegalParameterRepository wrapping load_legal_parameters_only as a singleton; `src/aeat/core/resources/_repos/legal_parameters.py`.
- [x] `P02.S14` - Add real-behaviour tests for the six singleton Repositories covering get, .singleton sugar, and clear_cache; `src/aeat/core/resources/_repos/test_singletons.py`.

### Phase `P03` - year-keyed repositories

Implement three int-year-keyed Repositories: holiday_calendars, category_profiles, vat_catalogues. Each takes a Settings-derived root where applicable.

- [x] `P03.S15` - Implement HolidayCalendarRepository with int-year key wrapping load_holiday_calendar; `src/aeat/core/resources/_repos/holiday_calendars.py`.
- [x] `P03.S16` - Implement CategoryProfileRepository with int-year key wrapping load_category_profile_registry and resolve_category_profiles; `src/aeat/core/resources/_repos/category_profiles.py`.
- [x] `P03.S17` - Implement VatCatalogueRepository with int-year key wrapping load_vat_catalogues and resolve_catalogue; `absorb the AEAT_VAT_CATALOGUE_ROOT Settings field; `src/aeat/core/resources/_repos/vat_catalogues.py`.
- [x] `P03.S18` - Add real-behaviour tests for the three year-keyed Repositories; `src/aeat/core/resources/_repos/test_year_keyed.py`.

### Phase `P04` - manual repository with composite key

Implement ManualRepository with the composite (manual_id, year, part) Pydantic key. Subsume resolve_part_root, load_manual, load_section, iter_sections, find_rules, load_catalogue, load_manifest, verify_fetched_pdf, verify_manual_dir.

- [x] `P04.S19` - Implement ManualRepository with composite ManualKey covering resolve_part_root, load_manual, load_section, iter_sections, find_rules, load_catalogue, load_manifest, verify_fetched_pdf, verify_manual_dir; `src/aeat/core/resources/_repos/manuals.py`.
- [x] `P04.S20` - Add real-behaviour tests for ManualRepository covering composite key resolution, catalogue iteration, and section lookup; `src/aeat/core/resources/_repos/test_manuals.py`.

### Phase `P05` - normative repository

Implement NormativeRepository with a singleton catalogue plus typed lookup methods (find_reference, find_articulo). Settings env-override seam preserved for aeat_normatives_root.

- [x] `P05.S21` - Implement NormativeRepository with singleton catalogue plus find_reference and find_articulo lookup methods; `absorb the AEAT_NORMATIVES_ROOT Settings field; `src/aeat/core/resources/_repos/normatives.py`.
- [x] `P05.S22` - Add real-behaviour tests for NormativeRepository covering singleton get, reference lookup, and articulo lookup; `src/aeat/core/resources/_repos/test_normatives.py`.

### Phase `P06` - modelo repository as a facade over ValidatedRegistryAuthority

Implement ModeloRepository as a thin wrapper around the existing ValidatedRegistryAuthority. Preserve its validator and snapshot caches. Migrate the five separate ValidatedRegistryAuthority.load construction paths to resources().modelos.

- [x] `P06.S23` - Implement ModeloRepository as a thin facade over ValidatedRegistryAuthority preserving its validator and snapshot caches; `key is ModeloKey(id: str); `src/aeat/core/resources/_repos/modelos.py`.
- [x] `P06.S24` - Add real-behaviour tests for ModeloRepository covering get, all, and the authority backing surface; `src/aeat/core/resources/_repos/test_modelos.py`.
- [x] `P06.S25` - Wire all twelve Repositories into the ResourceRegistry dataclass and verify the resources() factory composes them correctly under Settings overrides; `src/aeat/core/resources/_registry.py`.

### Phase `P07` - production consumer migration

Migrate the 25-30 production consumer modules from their existing load_* / _DEFAULT_*_ROOT imports to from aeat.core.resources import resources. Order: domain layer first, then application, then adapters, then entrypoints CLI defaults.

- [x] `P07.S26` - Migrate the registry corpus module manuals normatives and topics resolution to resources(); `src/aeat/application/registry/_corpus.py`.
- [x] `P07.S27` - Migrate the registry application package init to resources(); `src/aeat/application/registry/__init__.py`.
- [x] `P07.S28` - Migrate the diagnostics version and repair surfaces to resources(); `src/aeat/application/diagnostics.py`.
- [x] `P07.S29` - Migrate the topics application package init to resources(); `src/aeat/application/topics/__init__.py`.
- [x] `P07.S30` - Migrate the filing runtime schema provider to resources(); `src/aeat/application/filing/runtime.py`.
- [x] `P07.S31` - Migrate the filing application package init to resources(); `src/aeat/application/filing/__init__.py`.
- [x] `P07.S32` - Migrate the verification declaracion verifier to resources(); `src/aeat/application/verification/_verify.py`.
- [x] `P07.S33` - Migrate the live filed data capture to resources(); `src/aeat/application/live/__init__.py`.
- [x] `P07.S34` - Migrate the modelo work-unit actions to resources(); `src/aeat/application/modelo/_actions.py`.
- [x] `P07.S35` - Migrate the renta ledger aggregation to resources(); `src/aeat/application/aggregation/_renta_ledger.py`.
- [x] `P07.S36` - Migrate the default_registry_authority singleton as a thin shim that delegates to resources().modelos to resources(); `src/aeat/domain/calculations/registry/_authority.py`.
- [x] `P07.S37` - Migrate the calculate_registry_snapshot lazy bundled_path import to resources(); `src/aeat/domain/calculations/registry/_formula_runtime.py`.
- [x] `P07.S38` - Migrate the run_registry_calculation_scenario wrapper to resources(); `src/aeat/domain/calculations/registry/_scenarios.py`.
- [x] `P07.S39` - Migrate the manuals loader public surface to delegate to resources().manuals to resources(); `src/aeat/domain/manuals/_loader.py`.
- [x] `P07.S40` - Migrate the manuals fetch and load_manifest to resources(); `src/aeat/domain/manuals/_fetch.py`.
- [x] `P07.S41` - Migrate the manuals verifier to resources(); `src/aeat/domain/manuals/_verify.py`.
- [x] `P07.S42` - Migrate the normatives loader public surface to delegate to resources().normatives to resources(); `src/aeat/domain/normatives/_loader.py`.
- [x] `P07.S43` - Migrate the normatives verifier to resources(); `src/aeat/domain/normatives/_verify.py`.
- [x] `P07.S44` - Migrate the vat catalogue module dropping the eager VAT_CATALOGUES_BY_YEAR module-level load to resources(); `src/aeat/domain/vat/_catalogue.py`.
- [x] `P07.S45` - Migrate the vat rates module to resources(); `src/aeat/domain/vat/_rates.py`.
- [x] `P07.S46` - Migrate the vat recargo-equivalencia parameter loader to resources(); `src/aeat/domain/vat/_recargo_equivalencia.py`.
- [x] `P07.S47` - Migrate the deadlines engine class internal authority bootstrap to resources(); `src/aeat/domain/deadlines/_engine.py`.
- [x] `P07.S48` - Migrate the deadlines festivos calendar loader to resources(); `src/aeat/domain/deadlines/_festivos.py`.
- [x] `P07.S49` - Migrate the deadlines recargo bands loader to resources(); `src/aeat/domain/deadlines/_recargo.py`.
- [x] `P07.S50` - Migrate the categories profile registry loader to resources(); `src/aeat/domain/categories/_registry.py`.
- [x] `P07.S51` - Migrate the categories corpus aggregator to resources(); `src/aeat/domain/categories/_corpus.py`.
- [x] `P07.S52` - Migrate the user_profile schema loader to resources(); `src/aeat/domain/user_profile/_loader.py`.
- [x] `P07.S53` - Migrate the apoderamientos catalogue loader to resources(); `src/aeat/domain/auth/apoderamientos/_catalogue.py`.
- [x] `P07.S54` - Migrate the rental imputacion-parameters module dropping the eager LIRPF_ART_85_IMPUTACION load to resources(); `src/aeat/domain/rental/_imputacion_parameters.py`.
- [x] `P07.S55` - Migrate the declaracion inbound parser to resources(); `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `P07.S56` - Migrate the sede outbound declarations module to resources(); `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `P07.S57` - Migrate the registry CLI command surface to resources(); `src/aeat/entrypoints/cli/registry.py`.
- [x] `P07.S58` - Migrate the live-app CLI surface to resources(); `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `P07.S59` - Migrate the CLI common helpers to resources(); `src/aeat/entrypoints/cli/_common.py`.
- [x] `P07.S60` - Migrate the modelo CLI command surface to resources(); `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `P07.S61` - Migrate the google calc CLI sync command to resources(); `src/aeat/entrypoints/cli/_config/_google.py`.

### Phase `P08` - test consumer migration

Migrate the ~100 test modules from their per-module _REGISTRY_ROOT constants and direct loader calls to resources(). Tests that override Settings continue to work because the factory reads Settings at the override point; conftest fixtures invoke resources.cache_clear().

- [x] `P08.S62` - Migrate the calculations registry test suite under registry/ from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/calculations/registry/`.
- [x] `P08.S63` - Migrate the manuals domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/manuals/`.
- [x] `P08.S64` - Migrate the normatives domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/normatives/`.
- [x] `P08.S65` - Migrate the vat domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/vat/`.
- [x] `P08.S66` - Migrate the deadlines domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/deadlines/`.
- [x] `P08.S67` - Migrate the categories domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/categories/`.
- [x] `P08.S68` - Migrate the user-profile domain test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/user_profile/`.
- [x] `P08.S69` - Migrate the apoderamientos test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/auth/apoderamientos/`.
- [x] `P08.S70` - Migrate the rental imputacion tests from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/domain/rental/`.
- [x] `P08.S71` - Migrate the calculations application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/calculations/`.
- [x] `P08.S72` - Migrate the aggregation application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/aggregation/`.
- [x] `P08.S73` - Migrate the filing application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/filing/`.
- [x] `P08.S74` - Migrate the modelo application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/modelo/`.
- [x] `P08.S75` - Migrate the registry application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/registry/`.
- [x] `P08.S76` - Migrate the verification application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/verification/`.
- [x] `P08.S77` - Migrate the live application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/live/`.
- [x] `P08.S78` - Migrate the topics application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/topics/`.
- [x] `P08.S79` - Migrate the calc-sheets storage application test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/application/storage/calc_sheets/`.
- [x] `P08.S80` - Migrate the declaracion inbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/inbound/declaracion/`.
- [x] `P08.S81` - Migrate the sede outbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/outbound/aeat/sede/`.
- [x] `P08.S82` - Migrate the google outbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/outbound/google/`.
- [x] `P08.S83` - Migrate the export outbound adapter test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/adapters/outbound/aeat/export/`.
- [x] `P08.S84` - Migrate the registry CLI test suite from per-module _REGISTRY_ROOT constants and direct loader calls to resources(); `src/aeat/entrypoints/cli/`.

### Phase `P09` - retirement of legacy surface

Delete the 11 production module-level _DEFAULT_*_ROOT constants. Delete the 20+ scattered @lru_cache decorators on loaders that have folded into Repositories. Remove the public load_* re-exports from domain __init__ files. Drop the eager module-level VAT_CATALOGUES_BY_YEAR and LIRPF_ART_85_IMPUTACION loads now that consumers go through Repositories.

- [x] `P09.S85` - Delete the eleven production module-level _DEFAULT_*_ROOT constants now that their Repository owns the root resolution; `src/aeat/domain/`.
- [x] `P09.S86` - Delete the scattered @lru_cache decorators on every loader that has folded into a Repository; `src/aeat/domain/`.
- [x] `P09.S87` - Remove the public load_* re-exports from domain package __init__ files; `src/aeat/domain/`.
- [x] `P09.S88` - Drop the eager VAT_CATALOGUES_BY_YEAR module-level load now that consumers go through resources().vat_catalogues; `src/aeat/domain/vat/_catalogue.py`.
- [x] `P09.S89` - Drop the eager LIRPF_ART_85_IMPUTACION module-level load now that consumers go through resources().legal_parameters; `src/aeat/domain/rental/_imputacion_parameters.py`.
- [x] `P09.S90` - Remove the legacy default_registry_authority shim once every caller has switched to resources().modelos; `src/aeat/domain/calculations/registry/_authority.py`.
- [x] `P09.S94` - Drop the eager VAT_RATE_TABLE module-level load now that consumers go through resources().vat_rate_tables; `src/aeat/domain/vat/_rates.py`.
- [x] `P09.S95` - Drop the eager LIVA_ART_161_RECARGO module-level load (via private _load_rates wrapper) now that consumers go through resources().legal_parameters; `src/aeat/domain/vat/_recargo_equivalencia.py`.
- [x] `P09.S96` - Audit every __init__.py re-export of loader symbols and prune the now-obsolete public load_* names from __all__; `src/aeat/domain/`.

### Phase `P10` - quality gate + structural guard + release docs

Run ruff + ty + pytest. Add a structural test asserting the registry is the only resource-access surface (greps for bundled_path and _DEFAULT_*_ROOT outside core/resources/). Update RELEASING.md or other operator-facing surfaces only if the migration changed them.

- [x] `P10.S91` - Run the project quality gate ruff, ty, pytest with the unit marker, and the structural audits declared in the justfile; `justfile`.
- [x] `P10.S92` - Add a structural test asserting resources() is the only resource-access surface in the project by grepping for bundled_path and _DEFAULT_*_ROOT outside core/resources/; `src/aeat/core/resources/test_single_surface_invariant.py`.
- [x] `P10.S93` - Update operator-facing release documentation only if the migration changed the operator surface; `RELEASING.md`.
