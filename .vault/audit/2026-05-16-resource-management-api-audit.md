---
tags:
  - '#audit'
  - '#resource-management-api'
date: '2026-05-16'
modified: '2026-05-16'
related:
  - "[[2026-05-16-resource-management-api-research]]"
  - "[[2026-05-15-corpus-registry-packaging-adr]]"
---



# `resource-management-api` audit: exhaustive call-site inventory of the existing resource surface

## Scope

Six parallel read-only Haiku Explore agents performed a mechanical
sweep of every Python file under `src/aeat/`, partitioned into
six disjoint scopes: application, adapters, domain (excluding
`calculations/registry`), `calculations/registry`, entrypoints,
and core/tests/locales. Each agent reported every occurrence of
(A) named loader imports and calls, (B) Settings attribute reads
for the three corpus fields, (C) `packaged_data`/`bundled_path`/
`as_path` calls, (D) direct TOML/JSON reads against bundled
data, (E) typer.Argument/Option defaults referencing resource
paths, (F) module-level constants defining a bundled-data root,
(G) loader function definitions, and (H) `@lru_cache`/`@cache`
decorators on those loaders.

100 % file coverage. Total scanned: ~1058 Python files. This
document is the synthesised inventory; the seven agent-result
sets back it.

## Findings

### TOTALS-001 | INFO | Aggregate hit counts

Loader imports/calls: ~250 across roughly 130 files.
Settings attribute reads for the three corpus fields: 11 hits
across 4 production modules and 1 test (`override_settings`).
Resource boundary calls (`bundled_path`, `packaged_data`,
`as_path`): ~180 across roughly 110 files.
Direct TOML/JSON/PDF/HTML reads against bundled data: ~130 hits
across the `domain/calculations/registry/` sub-tree and the
domain loaders.
typer.Argument/Option defaults referencing resource paths: 20+
in `src/aeat/entrypoints/cli/`.
Module-level constants defining a bundled-data root: 41 total
(11 in production code, 30+ in test files).
Loader function definitions: 31 named public loaders plus their
cached inner variants.
`@lru_cache`/`@cache` decorators on loaders: 20 in the
`calculations/registry` tree alone (`@lru_cache(maxsize=1)`,
`8`, `16`, `32`, `64`, `128`, `256`×4, `512`, `2048`, `4096`,
plus `@cache` unbounded on `default_registry_authority` and
three test helpers). At least 10 more across the other domain
loaders.

### SURFACE-001 | INFO | The 31 loader functions defined in the codebase

The codebase currently exposes the following named loader
public surfaces, grouped by domain area:

Calculations registry (`src/aeat/domain/calculations/registry/_loader.py`,
`_authority.py`, `_snapshot.py`, `_formula_runtime.py`,
`_scenarios.py`, `_parity_tapes.py`):
  - `load_modelo_file(path) -> ModeloDefinition`
  - `load_modelo_directory(directory) -> ModeloDefinition`
  - `load_catalogue_file(path) -> RegistryCatalogues`
  - `load_legal_parameters_only(root) -> Mapping[str, LegalParameter]`
  - `load_registry_tree(root) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]`
  - `ValidatedRegistryAuthority.load(root, *, source_root) -> ValidatedRegistryAuthority`
  - `default_registry_authority() -> ValidatedRegistryAuthority`
  - `build_snapshot(modelo, catalogues, *, source_root, filing_year, period) -> RegistrySnapshot`
  - `calculate_registry_snapshot(...) -> ...`
  - `run_registry_calculation_scenario(...) -> ...`
  - `load_parity_scenario(path) -> ParityScenario`
  - `load_parity_tape(path) -> ParityTape`
  - `RegistryQueryService` (class wrapping authority)
  - `RegistryValidator` (class)

Manuals (`src/aeat/domain/manuals/_loader.py`, `_fetch.py`,
`_verify.py`):
  - `resolve_part_root(*, manual_id, year, part, settings=None) -> Path`
  - `load_manual(*, manual_id, year, part, settings=None) -> Manual`
  - `load_section(part_root, section_ref) -> Section`
  - `load_catalogue(*, settings=None) -> ManualCatalogue`
  - `iter_sections(...) -> Iterator[Section]`
  - `find_rules(...) -> Iterator[Rule]`
  - `load_manifest(manifest_path) -> FetchedManualPart`
  - `verify_fetched_pdf(manifest, part_root) -> None`
  - `verify_manual_dir(...) -> ManualVerificationReport`

Normatives (`src/aeat/domain/normatives/_loader.py`,
`_lookup.py`, `_verify.py`):
  - `load_catalogue(*, settings=None) -> NormativeCatalogue`
  - `find_reference(catalogue, ref_id) -> NormativeReference`
  - `find_articulo(...) -> NormativeArticulo`
  - `verify_catalogue(...) -> NormativeVerificationReport`

VAT (`src/aeat/domain/vat/_catalogue.py`, `_rates.py`,
`_verify.py`, `_recargo_equivalencia.py`):
  - `load_vat_catalogue(path) -> VATCatalogue`
  - `load_vat_catalogues(root) -> Mapping[int, VATCatalogue]`
  - `resolve_catalogue(*, on) -> VATCatalogue`
  - `load_vat_rate_table(path) -> Mapping[EUMemberState, tuple[VATRate, ...]]`
  - `verify_catalogue(catalogue) -> VatVerificationReport`
  - `VAT_CATALOGUES_BY_YEAR: Mapping[int, VATCatalogue]` (module-level eager load)

Deadlines (`src/aeat/domain/deadlines/_engine.py`, `_festivos.py`,
`_recargo.py`):
  - `DeadlineEngine(*, registry_root=None, source_root=None, due_soon_days=14)`
  - `load_holiday_calendar(year) -> HolidayCalendar`
  - `load_recargo_bands(path=None) -> tuple[RecargoBand, ...]`

Categories (`src/aeat/domain/categories/_registry.py`):
  - `load_category_profile_file(path) -> Mapping[SpendingCategory, CategoryProfile]`
  - `load_category_profile_registry(root=_DEFAULT_PROFILE_ROOT) -> Mapping[int, Mapping[SpendingCategory, CategoryProfile]]`
  - `resolve_category_profiles(year) -> Mapping[SpendingCategory, CategoryProfile]`

User profile (`src/aeat/domain/user_profile/_loader.py`):
  - `load_user_profile_schema(path=DEFAULT_USER_PROFILE_SCHEMA_PATH) -> ProfileSchemaDefinition`

Topics (`src/aeat/application/topics/__init__.py`):
  - `load_topic_catalogue(root=None) -> TopicCatalogue`

Apoderamientos (`src/aeat/domain/auth/apoderamientos/_catalogue.py`):
  - `load_default_catalogue(path=None) -> ApoderamientosCatalogue`

Rental (`src/aeat/domain/rental/_imputacion_parameters.py`):
  - `LIRPF_ART_85_IMPUTACION: LirpfArt85ImputacionParameters` (module-level eager load via `load_legal_parameters_only`)

### MODULE-CONSTANT-001 | INFO | 11 production module-level _DEFAULT_*_ROOT constants

The following module-level constants resolve a bundled-data root
at import time via `bundled_path(...)`:

`src/aeat/domain/auth/apoderamientos/_catalogue.py:13` —
`_DEFAULT_CATALOGUE_PATH = bundled_path("registry", "aeat", "apoderamientos", "scopes.toml")`.

`src/aeat/domain/categories/_registry.py:29` —
`_DEFAULT_PROFILE_ROOT = bundled_path("registry", "aeat", "categories", "profiles")`.

`src/aeat/domain/deadlines/_engine.py:36,37` —
`_DEFAULT_REGISTRY_ROOT = bundled_path("registry", "aeat")` and
`_DEFAULT_SOURCE_ROOT = bundled_path()`.

`src/aeat/domain/deadlines/_festivos.py` — `_CALENDARS_DIR`
joined off the bundled registry calendars root.

`src/aeat/domain/deadlines/_recargo.py` — `_DEFAULT_BRACKET_PATH`
points at `registry/aeat/legal/ley-58-2003-recargo-bands.toml`.

`src/aeat/domain/user_profile/_loader.py:15` —
`DEFAULT_USER_PROFILE_SCHEMA_PATH = bundled_path("registry", "aeat", "user_profile", "schema.toml")`.

`src/aeat/domain/vat/_catalogue.py:19` —
`_DEFAULT_CATALOGUE_ROOT = bundled_path("registry", "aeat", "vat", "catalogues")`.

`src/aeat/domain/vat/_rates.py` — `_DEFAULT_RATE_REGISTRY`
points at `registry/aeat/vat/rates.toml`.

`src/aeat/application/topics/__init__.py:30` —
`_TOPIC_REGISTRY_ROOT = bundled_path("registry", "aeat", "topics")`.

`src/aeat/entrypoints/cli/registry.py:24,25` —
`_DEFAULT_REGISTRY_ROOT` and `_DEFAULT_WORKBOOK_ROOT`.

`src/aeat/entrypoints/cli/_app_live.py:16,17` —
`_DEFAULT_REGISTRY_ROOT` and `_DEFAULT_SOURCE_ROOT`.

### MODULE-CONSTANT-002 | INFO | 30+ test-file _REGISTRY_ROOT constants

Across the `domain/calculations/registry/` tests, at least 30
test modules declare their own module-level
`_REGISTRY_ROOT = bundled_path("registry", "aeat")` constant.
Examples: `test_authority.py`, `test_audit_oracle_*`,
`test_modelo_*_registry.py`, `test_formula_*`, `test_queries.py`,
`test_renta_*`, `test_registry_schema.py`,
`test_borrador_prefilled_schema.py`, `test_filing_schedule_selection.py`,
`test_cross_dependency_*`, `test_ledger_*`.

This pattern is the test-side mirror of the production
`_DEFAULT_*_ROOT` constants. After the resource-management API
lands, both surfaces collapse into one registry import.

### CACHE-001 | INFO | 20+ scattered cache decorators with arbitrary sizing

`domain/calculations/registry/`:
  - `_load_modelo_file_cached`: `@lru_cache(maxsize=256)`
  - `_load_modelo_directory_cached`: `@lru_cache(maxsize=64)`
  - `_load_catalogue_file_cached`: `@lru_cache(maxsize=128)`
  - `_load_registry_tree_cached`: `@lru_cache(maxsize=32)`
  - `_load_authority`: `@lru_cache(maxsize=16)`
  - `default_registry_authority`: `@cache` (unbounded)
  - `_extract_record_design_cached`: `@lru_cache(maxsize=256)`
  - `_extract_record_design_workbook_cached`: `@lru_cache(maxsize=256)`
  - `_extract_record_design_xls_workbook_cached`: `@lru_cache(maxsize=128)`
  - `_extract_record_design_pdf_cached`: `@lru_cache(maxsize=256)`
  - `_load_xml_dictionary_entries`: `@lru_cache(maxsize=256)`
  - Utilities in `_validate.py` at `@lru_cache(maxsize=4096)`
    and `@lru_cache(maxsize=256)`
  - Utilities in `_sources.py` at `@lru_cache(maxsize=2048)`
  - Utilities in `_legal.py` at `@lru_cache(maxsize=512)`
  - Multiple `@lru_cache(maxsize=1)` and `@lru_cache(maxsize=8)`
    helpers in tests.

`domain/manuals/_loader.py`:
  - `_load_manual_cached`: `@lru_cache(maxsize=128)`
  - `_load_section_cached`: `@lru_cache(maxsize=2048)`
  - `_load_catalogue_cached`: `@lru_cache(maxsize=1024)`

`domain/normatives/_loader.py`:
  - `_load_catalogue_cached`: `@lru_cache(maxsize=16)`

`domain/vat/_catalogue.py`:
  - `_load_vat_catalogue_cached`: `@lru_cache(maxsize=32)`
  - `_load_vat_catalogues_cached`: `@lru_cache(maxsize=8)`

`domain/vat/_rates.py`:
  - `_load_vat_rate_table_cached`: `@lru_cache(maxsize=16)`

`domain/deadlines/_recargo.py`:
  - `_load_recargo_bands_cached`: `@lru_cache(maxsize=16)`

`domain/deadlines/_festivos.py`:
  - `load_holiday_calendar`: `@lru_cache(maxsize=64)`

`domain/categories/_registry.py`:
  - `_load_category_profile_file_cached`: `@lru_cache(maxsize=32)`
  - `_load_category_profile_registry_cached`: `@lru_cache(maxsize=8)`

`domain/user_profile/_loader.py`:
  - `_load_user_profile_schema_cached`: `@lru_cache(maxsize=16)`

`application/topics/__init__.py`:
  - `_load_topic_catalogue_cached`: `@lru_cache(maxsize=16)`

Cache sizes are heuristic with no documented rationale. The data
volume is small (~26 modelos, ~7 manuals, ~200 normatives, ~10
VAT catalogues, handful of TOMLs each for the rest). A single
shared cache with one unbounded `@cache` per loader would consume
trivial memory while eliminating size-tuning noise.

### CALLSITE-PROD-001 | INFO | 25 production-code consumer modules

Application layer (Settings-mediated and direct):
  - `src/aeat/application/registry/_corpus.py` — manuals,
    normatives, topics resolution via Settings + delegated calls.
  - `src/aeat/application/registry/__init__.py` — registry
    authority bootstrap; `inspect_registry_tree`,
    `verify_registry_tree`, `audit_registry_oracles`,
    `verify_filed_state`, `verify_registry_workbooks`.
  - `src/aeat/application/diagnostics.py` — version + repair
    surfaces; constructs registry authority.
  - `src/aeat/application/topics/__init__.py` — eager
    topic-catalogue loader.
  - `src/aeat/application/filing/runtime.py` — runtime schema
    provider; constructs registry authority.
  - `src/aeat/application/filing/__init__.py` — cached snapshot
    builder; constructs authority.
  - `src/aeat/application/verification/_verify.py` — declaracion
    verification; constructs authority.
  - `src/aeat/application/live/__init__.py` — source-filed-data
    capture; constructs authority.
  - `src/aeat/application/modelo/_actions.py` — five calls to
    `ValidatedRegistryAuthority.load(_registry_root(), source_root=bundled_path())`.
  - `src/aeat/application/aggregation/_renta_ledger.py` — calls
    `resolve_category_profiles`.

Domain layer:
  - `src/aeat/domain/calculations/registry/_loader.py` — every
    `load_*` function.
  - `src/aeat/domain/calculations/registry/_authority.py` —
    `ValidatedRegistryAuthority`, `_load_authority`,
    `default_registry_authority`.
  - `src/aeat/domain/calculations/registry/_snapshot.py` —
    `_build_validated_snapshot`.
  - `src/aeat/domain/calculations/registry/_formula_runtime.py`
    — `calculate_registry_snapshot` + lazy `bundled_path` import.
  - `src/aeat/domain/calculations/registry/_scenarios.py` —
    `run_registry_calculation_scenario`.
  - `src/aeat/domain/manuals/_loader.py` — manual loaders.
  - `src/aeat/domain/manuals/_fetch.py` — `load_manifest`,
    `verify_fetched_pdf` + Settings access for HTTP timeout.
  - `src/aeat/domain/manuals/_verify.py` — `verify_manual_dir`.
  - `src/aeat/domain/normatives/_loader.py`, `_lookup.py`,
    `_verify.py`.
  - `src/aeat/domain/vat/_catalogue.py`, `_rates.py`, `_verify.py`,
    `_recargo_equivalencia.py`.
  - `src/aeat/domain/deadlines/_engine.py`, `_festivos.py`,
    `_recargo.py`.
  - `src/aeat/domain/categories/_registry.py`, `_corpus.py`.
  - `src/aeat/domain/user_profile/_loader.py`.
  - `src/aeat/domain/auth/apoderamientos/_catalogue.py`.
  - `src/aeat/domain/rental/_imputacion_parameters.py` —
    eager module-level load.

Adapters layer:
  - `src/aeat/adapters/inbound/declaracion/_parser.py` —
    constructs authority via `bundled_path` (1 call).
  - `src/aeat/adapters/outbound/aeat/sede/_declarations.py` —
    constructs authority (2 calls) + `load_registry_tree`.

Entrypoints layer:
  - `src/aeat/entrypoints/cli/registry.py` — 7 typer.Option
    defaults + module-level constants.
  - `src/aeat/entrypoints/cli/_app_live.py` — 2 typer.Option
    defaults + lazy authority construction.
  - `src/aeat/entrypoints/cli/_common.py` — 1 authority
    construction.
  - `src/aeat/entrypoints/cli/_modelo.py` — `_service()` factory
    using `RegistryQueryService(ValidatedRegistryAuthority.load(...))`.
  - `src/aeat/entrypoints/cli/_config/_google.py` — snapshot
    builder via `load_registry_tree` + `build_snapshot`.
  - `src/aeat/entrypoints/cli/_registry_corpus.py` — delegates
    to application-layer functions (no direct loader calls).

### CALLSITE-TEST-001 | INFO | ~100 test modules touch the loader surface

The test surface is concentrated in:
  - `src/aeat/domain/calculations/registry/` — ~65 test files,
    each typically defining its own
    `_REGISTRY_ROOT = bundled_path("registry", "aeat")` constant
    and calling `load_registry_tree`, `ValidatedRegistryAuthority`,
    `calculate_registry_snapshot`, or `RegistryValidator`.
  - `src/aeat/application/*/test_*.py` — ~12 test files calling
    `load_registry_tree`, `ValidatedRegistryAuthority.load`,
    `resolve_category_profiles`, or `override_settings`.
  - `src/aeat/domain/{manuals,normatives,vat,deadlines,categories,user_profile,auth}/test_*.py` — ~15 test files
    calling their domain-specific loaders.
  - `src/aeat/adapters/**/test_*.py` — ~6 test files calling
    `load_registry_tree` and `build_snapshot`.
  - `src/aeat/entrypoints/cli/test_*.py` — ~4 test files including
    `test_registry_cli.py` and `test_backend_boundary.py`.

### SETTINGS-001 | INFO | Three Settings env-overridable fields

`src/aeat/core/config.py:464,477,483` — three Pydantic Settings
fields with `default_factory` calls to `bundled_path(...)`:
  - `aeat_manuals_root` → `bundled_path("corpus", "manuals")`
  - `aeat_normatives_root` → `bundled_path("corpus", "normatives")`
  - `aeat_vat_catalogue_root` → `bundled_path("registry", "aeat", "vat")`

Consumed in production:
  - `src/aeat/domain/manuals/_loader.py:55` —
    `(settings or load_settings()).aeat_manuals_root`.
  - `src/aeat/domain/normatives/_loader.py:30` —
    `(settings or load_settings()).aeat_normatives_root`.
  - `src/aeat/application/registry/_corpus.py:744,745` —
    `resolved.aeat_manuals_root`.

Override-tested via `override_settings(aeat_normatives_root=...)`
in `src/aeat/application/registry/test_corpus.py`.

The VAT catalogue field has no in-production consumer that reads
it via Settings; the VAT loaders use the module-level
`_DEFAULT_*_ROOT` constants instead. This is an existing
inconsistency the new API should resolve.

### TYPER-001 | INFO | 9 typer-default surfaces using bundled paths

`src/aeat/entrypoints/cli/registry.py`:
  - `inspect` `--registry-root` default = `_DEFAULT_REGISTRY_ROOT`.
  - `verify` `--registry-root` default = `_DEFAULT_REGISTRY_ROOT`.
  - `audit-oracles` `--registry-root` default = `_DEFAULT_REGISTRY_ROOT`.
  - `verify-filed-state` `--registry-root` default = `_DEFAULT_REGISTRY_ROOT`.
  - `workbooks verify` `--root` default = `_DEFAULT_WORKBOOK_ROOT`.
  - `parity run` `--registry-root` default = `_DEFAULT_REGISTRY_ROOT`.
  - `parity replay` `--registry-root` default = `_DEFAULT_REGISTRY_ROOT`.

`src/aeat/entrypoints/cli/_app_live.py`:
  - `live filed capture-sources` `--registry-root` default =
    `_DEFAULT_REGISTRY_ROOT`.
  - `live filed capture-sources` `--source-root` default =
    `_DEFAULT_SOURCE_ROOT`.

Note: several `--source-root` flags in `registry.py` default to
`Path(".")` (CWD-relative) rather than `bundled_path()`; these
are independent of the bundled root because operators may want
to verify against a working tree. The new API will preserve this
seam.

### IMPORTLIB-001 | INFO | importlib.resources usage map across the codebase

The codebase's direct `importlib.resources` callers (not via
`aeat.core.resources`):
  - `src/aeat/core/resources.py:22` — `from importlib.resources import as_file, files`
    — the boundary itself.
  - `src/aeat/core/external_constants.py:15,120` —
    `files(__package__).joinpath("external_constants.toml").read_text(...)`
    — TOML external constants registry.
  - `src/aeat/core/i18n/_render.py:10,49,181` —
    `importlib.resources.files("aeat").joinpath("locales", ...)`
    — i18n locale YAML loader.
  - `src/aeat/adapters/persistence/storage/master_key/_recovery.py:113-119` —
    `resources.files(__package__).joinpath("_bip39_wordlist.txt")`
    — BIP-39 wordlist.

The new resource-management API consolidates the bundled-data
surface but leaves these four narrow special-case loaders alone
(they are not bundled-data resources; they are package-internal
files used by a specific subsystem).

### ARCH-001 | INFO | The migration shape that the audit implies

The new `ResourceRegistry` must subsume:
  - 31 named public loaders.
  - 11 production module-level `_DEFAULT_*_ROOT` constants.
  - 30+ test-side `_REGISTRY_ROOT` constants.
  - 20+ scattered `@lru_cache` decorators.
  - 5 separate construction paths for
    `ValidatedRegistryAuthority` in application/adapters/CLI.
  - 9 typer.Argument/Option defaults referring to bundled roots.
  - 3 Settings env-overridable fields (manuals, normatives, vat).
  - Module-level eager loads in `domain.vat._catalogue`
    (`VAT_CATALOGUES_BY_YEAR`) and
    `domain.rental._imputacion_parameters` (`LIRPF_ART_85_IMPUTACION`).

Estimated file touch count for the migration:
  - Production modules: ~25-30 (the consumer surface).
  - Test modules: ~100 (each test moves from its own
    `bundled_path` constant or direct loader call to a
    `resources()` import).
  - CLI typer defaults: 9 sites in 2 files.

The diff shape is comparable to the corpus-registry-packaging
migration. A focused executor can land it in 2-3 working days
with the same per-bucket discipline.

### NULL-001 | INFO | Files with zero relevant hits

Across the six agent sweeps the following major file groups have
ZERO relevant hits (verification of coverage rather than an
omission):
  - 272 of 294 files in `src/aeat/application/`.
  - 256 of 298 files in `src/aeat/adapters/`.
  - Most of `src/aeat/core/` except `config.py`,
    `external_constants.py`, `i18n/_render.py`, `resources.py`,
    `test_resources.py`, `test_external_constants.py`,
    `test_config.py`.
  - 13 of ~30 files in `src/aeat/entrypoints/cli/`.

The Null hits confirm the loader surface is narrow even though
the call surface is wide. ~25 modules define loaders; ~130
modules call them.

## Recommendations

The findings ratify the leading-candidate pattern recommended by
the research artefact (Sketch A — `Repository[T, K]` per resource
type, with a central `ResourceRegistry` aggregating them and a
single `resources()` factory). The migration sequence the plan
should follow:

1. Land the `Repository[T, K]` base + the central
   `ResourceRegistry` skeleton in `src/aeat/core/resources/`,
   alongside the existing `bundled_path` boundary. The new code
   is purely additive at this stage; nothing migrates yet.
2. Implement one Repository per resource kind, starting with
   the simplest singletons (apoderamientos, user-profile,
   topics, recargo-bands) and ending with the modelos
   Repository (which delegates to `ValidatedRegistryAuthority`).
3. Migrate consumers Repository-by-Repository: each Repository
   ships with its own slice of consumer migrations (production
   first, tests second), so the surface area of each commit
   stays bounded.
4. Retire the per-module `_DEFAULT_*_ROOT` constants once their
   Repository's consumers have all moved over.
5. Retire the per-module `@lru_cache` decorators once their
   loader has folded into the Repository (the Repository owns
   the cache).
6. Close with (a) a structural test that asserts the registry
   is the only resource-access surface in the project, and (b)
   a deprecation pass that removes the legacy `load_*` public
   functions from the domain `__init__.py` re-exports.

The audit document is the call-site contract for the migration;
each finding maps to one or more migration steps in the next
plan.
