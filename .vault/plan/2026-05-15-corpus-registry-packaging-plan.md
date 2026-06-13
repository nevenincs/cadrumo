---
tags:
  - '#plan'
  - '#corpus-registry-packaging'
date: '2026-05-15'
modified: '2026-05-15'
tier: L2
related:
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
  - '[[2026-05-15-corpus-registry-packaging-research]]'
---


# `corpus-registry-packaging` plan

### Phase `P01` - resource-locator boundary and wheel-build wiring

Land the single resource-access boundary, the hatch force-include configuration that ships corpus and registry inside the wheel, the in-process and built-wheel test guards, and the external-constants idiom consolidation.

- [x] `P01.S01` - Implement packaged_data and as_path resource locator; `src/aeat/core/resources.py`.
- [x] `P01.S02` - Add real-behaviour Traversable leaf-presence assertions across every bundled subtree; `src/aeat/core/test_resources.py`.
- [x] `P01.S03` - Confirm hatch packages directive covers the relocated src/aeat/_data subtree without adding a force-include block; `pyproject.toml`.
- [x] `P01.S04` - Add built-wheel manifest guard that drives uv build --wheel and asserts every git-tracked src/aeat/_data path appears in the wheel archive under the aeat/_data prefix; `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`.
- [x] `P01.S05` - Migrate the external-constants loader from Path(__file__).parent to resources.files(__package__) to consolidate on the single resource-access idiom; `src/aeat/core/external_constants.py`.

### Phase `P02` - settings-mediated corpus consumers

Switch the defaults of the three Settings fields that expose corpus subtrees from the PROJECT_ROOT walk to resource-locator resolution while preserving env-override semantics, and confirm the existing domain loaders continue to function unchanged.

- [x] `P02.S06` - Switch aeat_manuals_root, aeat_normatives_root, aeat_vat_catalogue_root defaults to resource-locator resolution while preserving env-override semantics; `src/aeat/core/config.py`.
- [x] `P02.S07` - Refresh the Settings invariant tests where they assert the default-path shape of the three corpus fields; `src/aeat/core/test_settings_single_surface_invariant.py`.
- [x] `P02.S08` - Confirm the manuals loader continues to resolve via Settings without signature changes; `src/aeat/domain/manuals/_loader.py`.
- [x] `P02.S09` - Confirm the normatives loader continues to resolve via Settings without signature changes; `src/aeat/domain/normatives/_loader.py`.
- [x] `P02.S10` - Confirm the registry corpus projection continues to resolve manuals through Settings without signature changes; `src/aeat/application/registry/_corpus.py`.

### Phase `P03` - production hard-code migration

Migrate every PROJECT_ROOT / corpus / ... and PROJECT_ROOT / registry / aeat join in production code under application, adapters, domain, entrypoints, and core to the resource locator, removing the hidden coupling between the runtime and the source checkout.

- [x] `P03.S11` - Migrate the diagnostics registry-root resolution to packaged_data; `src/aeat/application/diagnostics.py`.
- [x] `P03.S12` - Migrate the filing runtime registry-root resolution to packaged_data; `src/aeat/application/filing/runtime.py`.
- [x] `P03.S13` - Migrate the filing package init registry-root resolution to packaged_data; `src/aeat/application/filing/__init__.py`.
- [x] `P03.S14` - Migrate the modelo actions registry-root resolution to packaged_data; `src/aeat/application/modelo/_actions.py`.
- [x] `P03.S15` - Migrate the verification registry-root resolution to packaged_data; `src/aeat/application/verification/_verify.py`.
- [x] `P03.S16` - Migrate the topics registry-root resolution to packaged_data; `src/aeat/application/topics/__init__.py`.
- [x] `P03.S17` - Migrate the declaracion inbound parser registry-root resolution to packaged_data; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [x] `P03.S18` - Migrate the sede declarations registry-root resolution to packaged_data; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [x] `P03.S19` - Migrate the VAT rates default registry path to packaged_data; `src/aeat/domain/vat/_rates.py`.
- [x] `P03.S20` - Migrate the VAT catalogue default registry root to packaged_data; `src/aeat/domain/vat/_catalogue.py`.
- [x] `P03.S21` - Migrate the recargo-equivalencia registry resolution to packaged_data; `src/aeat/domain/vat/_recargo_equivalencia.py`.
- [x] `P03.S22` - Migrate the rental imputacion-parameters registry resolution to packaged_data; `src/aeat/domain/rental/_imputacion_parameters.py`.
- [x] `P03.S23` - Migrate the deadline-recargo registry-root resolution to packaged_data; `src/aeat/domain/deadlines/_recargo.py`.
- [x] `P03.S24` - Migrate the festivos calendars registry-root resolution to packaged_data; `src/aeat/domain/deadlines/_festivos.py`.
- [x] `P03.S25` - Migrate the deadlines engine default registry resolution to packaged_data; `src/aeat/domain/deadlines/_engine.py`.
- [x] `P03.S26` - Migrate the categories registry-root resolution to packaged_data; `src/aeat/domain/categories/_registry.py`.
- [x] `P03.S27` - Migrate the user-profile schema registry resolution to packaged_data; `src/aeat/domain/user_profile/_loader.py`.
- [x] `P03.S28` - Migrate the modelo CLI command registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_modelo.py`.
- [x] `P03.S29` - Migrate the CLI common helpers registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_common.py`.
- [x] `P03.S30` - Migrate the live-app entrypoint registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `P03.S31` - Migrate the google calc CLI registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_config/_google.py`.
- [x] `P03.S32` - Migrate the registry CLI typer default for the official disenos-registro corpus path to packaged_data; `src/aeat/entrypoints/cli/registry.py`.
- [x] `P03.S33` - Drop the remaining PROJECT_ROOT corpus and registry joins from the config module while preserving the PROJECT_ROOT constant for var outputs; `src/aeat/core/config.py`.
- [x] `P03.S55` - Replace the Path(__file__).resolve().parents[5] walk with the packaged_data locator for the apoderamientos scopes resolution; `src/aeat/domain/auth/apoderamientos/_catalogue.py`.
- [x] `P03.S56` - Replace the seven module-level CWD-relative Path(registry/aeat) typer-argument defaults with packaged_data resolution; `src/aeat/entrypoints/cli/registry.py`.
- [x] `P03.S57` - Replace the module-level CWD-relative Path(registry/aeat) default with packaged_data resolution; `src/aeat/entrypoints/cli/_app_live.py`.
- [x] `P03.S58` - Replace the module-level CWD-relative Path(registry/aeat) default with packaged_data resolution; `src/aeat/application/registry/__init__.py`.
- [x] `P03.S59` - Replace the module-level CWD-relative Path(registry/aeat) default with packaged_data resolution; `src/aeat/application/live/__init__.py`.
- [x] `P03.S60` - Update the four production error-message strings that embed the old registry/aeat path prefix; `src/aeat/domain/`.
- [x] `P03.S61` - Migrate the eleven glob sites in registry and corpus loaders so they iterate Traversable.iterdir or use packaged_data with as_path materialisation; `src/aeat/domain/calculations/registry/_loader.py`.
- [x] `P03.S64` - Migrate the cached default_registry_authority singleton to packaged_data; `sequence this Step first within P03 because the singleton propagates through several production callers; `src/aeat/domain/calculations/registry/_authority.py`.
- [x] `P03.S65` - Switch the source_root parameter of ValidatedRegistryAuthority.load and default_registry_authority to the packaged_data root so corpus_ref and raw_evidence_locator strings inside registry TOMLs resolve relative to the bundled prefix; `src/aeat/domain/calculations/registry/_authority.py`.

### Phase `P04` - test surface migration and release documentation

Migrate every test module that joins PROJECT_ROOT against corpus or registry to the resource locator, run the project quality gate, and update the release-engineering documentation with the PyPI per-file-size implications of the in-wheel bundling decision.

- [x] `P04.S34` - Migrate the calculations registry test suite registry-root resolution to packaged_data; `src/aeat/domain/calculations/registry/`.
- [x] `P04.S35` - Migrate the VAT domain test suite registry and normatives resolution to packaged_data; `src/aeat/domain/vat/`.
- [x] `P04.S36` - Migrate the calculations row-set and detail-record tests to packaged_data; `src/aeat/application/calculations/`.
- [x] `P04.S37` - Migrate the aggregation test suite registry-root resolution to packaged_data; `src/aeat/application/aggregation/`.
- [x] `P04.S38` - Migrate the calc-sheets storage tests registry-root resolution to packaged_data; `src/aeat/application/storage/calc_sheets/`.
- [x] `P04.S39` - Migrate the filing application test suite registry-root resolution to packaged_data; `src/aeat/application/filing/`.
- [x] `P04.S40` - Migrate the modelo application test suite registry-root resolution to packaged_data; `src/aeat/application/modelo/`.
- [x] `P04.S41` - Migrate the registry corpus application tests to packaged_data; `src/aeat/application/registry/`.
- [x] `P04.S42` - Migrate the manuals domain tests to packaged_data and Settings overrides; `src/aeat/domain/manuals/`.
- [x] `P04.S43` - Migrate the normatives domain tests to packaged_data; `src/aeat/domain/normatives/`.
- [x] `P04.S44` - Migrate the rental imputacion test suite registry-root resolution to packaged_data; `src/aeat/domain/rental/`.
- [x] `P04.S45` - Migrate the user-profile registry-contract tests to packaged_data; `src/aeat/domain/user_profile/`.
- [x] `P04.S46` - Migrate the invoices iva-classification tests to packaged_data; `src/aeat/domain/invoices/`.
- [x] `P04.S47` - Migrate the sede outbound test suite registry, parity-replay and groi-samples resolution to packaged_data; `src/aeat/adapters/outbound/aeat/sede/`.
- [x] `P04.S48` - Migrate the CLI entrypoint test suite registry-root and corpus workbook-root resolution to packaged_data; `src/aeat/entrypoints/cli/`.
- [x] `P04.S49` - Run the project quality gate of ruff, ty, pytest, and structural audits across the touched surface; `justfile`.
- [x] `P04.S50` - Document the PyPI 100 MB per-file cap acknowledgement and the three release-time options (file-size grant request, future PDF extras split, private-index publication); `RELEASING.md`.
- [x] `P04.S62` - Migrate the nine f-string path-composition sites in tests that embed corpus and registry fragments to packaged_data composition; `src/aeat/domain/`.
- [x] `P04.S63` - Migrate the justificante parser tests that glob corpus/aeat_official PDFs to packaged_data composition; `src/aeat/adapters/inbound/justificante/`.
- [x] `P04.S66` - Audit the four locale YAML files for CLI help strings that quote the old corpus or registry path prefix and update any operator-visible mentions; `src/aeat/locales/`.

### Phase `P05` - physical relocation and operator-config update

Move corpus and registry under src/aeat/_data via git mv, rewrite the gitignore allow-list so the tracked Renta PDFs remain tracked under the new prefix, and refresh env/.env.example so the three operator-visible env-var defaults reflect the new layout. This phase EXECUTES BEFORE P01 despite its higher identifier; identifier order is append-only per the plan-hardening contract, but the Parallelization section below states the canonical execution order.

- [x] `P05.S51` - Relocate the corpus tree under src/aeat/_data via git mv preserving every tracked file; `corpus/ -> src/aeat/_data/corpus/`.
- [x] `P05.S52` - Relocate the registry tree under src/aeat/_data via git mv preserving every tracked file; `registry/ -> src/aeat/_data/registry/`.
- [x] `P05.S53` - Rewrite the gitignore allow-list and HTML-intermediate rules so the seven tracked Renta source.pdf files and the source.html directory rule reference the new src/aeat/_data prefix; `.gitignore`.
- [x] `P05.S54` - Update the three corpus-related env var defaults so the documented operator-override paths reflect the new src/aeat/_data prefix; `env/.env.example`.
