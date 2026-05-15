---
tags:
  - '#plan'
  - '#corpus-registry-packaging'
date: '2026-05-15'
tier: L2
related:
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
  - '[[2026-05-15-corpus-registry-packaging-research]]'
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

# `corpus-registry-packaging` plan

Migrate the runtime resolution of the on-disk corpus and registry
trees off the project-root walk in the config module onto a single
packaged-resource boundary, and update the wheel build target so the
trees ship inside the installed distribution at `aeat/_data/corpus/`
and `aeat/_data/registry/`. The migration lands the boundary first,
then the Settings-mediated consumers, then the production hard-codes,
then the test surface, then the release-engineering documentation
update.

## Proposed Changes

The accepted ADR ratifies bundling both top-level data trees inside
the wheel via hatchling force-include, exposed through a new boundary
at `src/aeat/core/resources.py` that returns a `Traversable` rooted at
`importlib.resources.files("aeat").joinpath("_data", ...)`. The
Settings env-override seam for the three corpus subtrees is
preserved; only their defaults switch from the broken project-root
walk to a resource-locator resolution. Hard-coded
`PROJECT_ROOT / "registry" / "aeat"` and
`PROJECT_ROOT / "corpus" / "..."` joins move to the locator directly.
Test modules follow the same migration with no new mocks, fakes, or
skips. Two real-behaviour test guards lock the contract: an
in-process leaf-presence assertion and a built-wheel manifest
assertion that drives `uv build --wheel` end-to-end.

All identifier-affecting structure under the Steps section is owned
by the `vault plan` CLI; nothing in the Phase or Step rows is
hand-written.

## Steps

### Phase `P01` - resource-locator boundary and wheel-build wiring

Land the single resource-access boundary, the hatch force-include configuration that ships corpus and registry inside the wheel, the in-process and built-wheel test guards, and the external-constants idiom consolidation.

- [ ] `P01.S01` - Implement packaged_data and as_path resource locator; `src/aeat/core/resources.py`.
- [ ] `P01.S02` - Add real-behaviour Traversable leaf-presence assertions across every bundled subtree; `src/aeat/core/test_resources.py`.
- [ ] `P01.S03` - Add hatch wheel force-include entries for corpus and registry while keeping the existing narrow include entries; `pyproject.toml`.
- [ ] `P01.S04` - Add built-wheel manifest guard that drives uv build --wheel and asserts every git-tracked corpus and registry path appears at the aeat/_data prefix; `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`.
- [ ] `P01.S05` - Migrate the external-constants loader from Path(__file__).parent to resources.files(__package__) to consolidate on the single resource-access idiom; `src/aeat/core/external_constants.py`.

### Phase `P02` - settings-mediated corpus consumers

Switch the defaults of the three Settings fields that expose corpus subtrees from the PROJECT_ROOT walk to resource-locator resolution while preserving env-override semantics, and confirm the existing domain loaders continue to function unchanged.

- [ ] `P02.S06` - Switch aeat_manuals_root, aeat_normatives_root, aeat_vat_catalogue_root defaults to resource-locator resolution while preserving env-override semantics; `src/aeat/core/config.py`.
- [ ] `P02.S07` - Refresh the Settings invariant tests where they assert the default-path shape of the three corpus fields; `src/aeat/core/test_settings_single_surface_invariant.py`.
- [ ] `P02.S08` - Confirm the manuals loader continues to resolve via Settings without signature changes; `src/aeat/domain/manuals/_loader.py`.
- [ ] `P02.S09` - Confirm the normatives loader continues to resolve via Settings without signature changes; `src/aeat/domain/normatives/_loader.py`.
- [ ] `P02.S10` - Confirm the registry corpus projection continues to resolve manuals through Settings without signature changes; `src/aeat/application/registry/_corpus.py`.

### Phase `P03` - production hard-code migration

Migrate every PROJECT_ROOT / corpus / ... and PROJECT_ROOT / registry / aeat join in production code under application, adapters, domain, entrypoints, and core to the resource locator, removing the hidden coupling between the runtime and the source checkout.

- [ ] `P03.S11` - Migrate the diagnostics registry-root resolution to packaged_data; `src/aeat/application/diagnostics.py`.
- [ ] `P03.S12` - Migrate the filing runtime registry-root resolution to packaged_data; `src/aeat/application/filing/runtime.py`.
- [ ] `P03.S13` - Migrate the filing package init registry-root resolution to packaged_data; `src/aeat/application/filing/__init__.py`.
- [ ] `P03.S14` - Migrate the modelo actions registry-root resolution to packaged_data; `src/aeat/application/modelo/_actions.py`.
- [ ] `P03.S15` - Migrate the verification registry-root resolution to packaged_data; `src/aeat/application/verification/_verify.py`.
- [ ] `P03.S16` - Migrate the topics registry-root resolution to packaged_data; `src/aeat/application/topics/__init__.py`.
- [ ] `P03.S17` - Migrate the declaracion inbound parser registry-root resolution to packaged_data; `src/aeat/adapters/inbound/declaracion/_parser.py`.
- [ ] `P03.S18` - Migrate the sede declarations registry-root resolution to packaged_data; `src/aeat/adapters/outbound/aeat/sede/_declarations.py`.
- [ ] `P03.S19` - Migrate the VAT rates default registry path to packaged_data; `src/aeat/domain/vat/_rates.py`.
- [ ] `P03.S20` - Migrate the VAT catalogue default registry root to packaged_data; `src/aeat/domain/vat/_catalogue.py`.
- [ ] `P03.S21` - Migrate the recargo-equivalencia registry resolution to packaged_data; `src/aeat/domain/vat/_recargo_equivalencia.py`.
- [ ] `P03.S22` - Migrate the rental imputacion-parameters registry resolution to packaged_data; `src/aeat/domain/rental/_imputacion_parameters.py`.
- [ ] `P03.S23` - Migrate the deadline-recargo registry-root resolution to packaged_data; `src/aeat/domain/deadlines/_recargo.py`.
- [ ] `P03.S24` - Migrate the festivos calendars registry-root resolution to packaged_data; `src/aeat/domain/deadlines/_festivos.py`.
- [ ] `P03.S25` - Migrate the deadlines engine default registry resolution to packaged_data; `src/aeat/domain/deadlines/_engine.py`.
- [ ] `P03.S26` - Migrate the categories registry-root resolution to packaged_data; `src/aeat/domain/categories/_registry.py`.
- [ ] `P03.S27` - Migrate the user-profile schema registry resolution to packaged_data; `src/aeat/domain/user_profile/_loader.py`.
- [ ] `P03.S28` - Migrate the modelo CLI command registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_modelo.py`.
- [ ] `P03.S29` - Migrate the CLI common helpers registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_common.py`.
- [ ] `P03.S30` - Migrate the live-app entrypoint registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_app_live.py`.
- [ ] `P03.S31` - Migrate the google calc CLI registry-root resolution to packaged_data; `src/aeat/entrypoints/cli/_config/_google.py`.
- [ ] `P03.S32` - Migrate the registry CLI typer default for the official disenos-registro corpus path to packaged_data; `src/aeat/entrypoints/cli/registry.py`.
- [ ] `P03.S33` - Drop the remaining PROJECT_ROOT corpus and registry joins from the config module while preserving the PROJECT_ROOT constant for var outputs; `src/aeat/core/config.py`.

### Phase `P04` - test surface migration and release documentation

Migrate every test module that joins PROJECT_ROOT against corpus or registry to the resource locator, run the project quality gate, and update the release-engineering documentation with the PyPI per-file-size implications of the in-wheel bundling decision.

- [ ] `P04.S34` - Migrate the calculations registry test suite registry-root resolution to packaged_data; `src/aeat/domain/calculations/registry/`.
- [ ] `P04.S35` - Migrate the VAT domain test suite registry and normatives resolution to packaged_data; `src/aeat/domain/vat/`.
- [ ] `P04.S36` - Migrate the calculations row-set and detail-record tests to packaged_data; `src/aeat/application/calculations/`.
- [ ] `P04.S37` - Migrate the aggregation test suite registry-root resolution to packaged_data; `src/aeat/application/aggregation/`.
- [ ] `P04.S38` - Migrate the calc-sheets storage tests registry-root resolution to packaged_data; `src/aeat/application/storage/calc_sheets/`.
- [ ] `P04.S39` - Migrate the filing application test suite registry-root resolution to packaged_data; `src/aeat/application/filing/`.
- [ ] `P04.S40` - Migrate the modelo application test suite registry-root resolution to packaged_data; `src/aeat/application/modelo/`.
- [ ] `P04.S41` - Migrate the registry corpus application tests to packaged_data; `src/aeat/application/registry/`.
- [ ] `P04.S42` - Migrate the manuals domain tests to packaged_data and Settings overrides; `src/aeat/domain/manuals/`.
- [ ] `P04.S43` - Migrate the normatives domain tests to packaged_data; `src/aeat/domain/normatives/`.
- [ ] `P04.S44` - Migrate the rental imputacion test suite registry-root resolution to packaged_data; `src/aeat/domain/rental/`.
- [ ] `P04.S45` - Migrate the user-profile registry-contract tests to packaged_data; `src/aeat/domain/user_profile/`.
- [ ] `P04.S46` - Migrate the invoices iva-classification tests to packaged_data; `src/aeat/domain/invoices/`.
- [ ] `P04.S47` - Migrate the sede outbound test suite registry, parity-replay and groi-samples resolution to packaged_data; `src/aeat/adapters/outbound/aeat/sede/`.
- [ ] `P04.S48` - Migrate the CLI entrypoint test suite registry-root and corpus workbook-root resolution to packaged_data; `src/aeat/entrypoints/cli/`.
- [ ] `P04.S49` - Run the project quality gate of ruff, ty, pytest, and structural audits across the touched surface; `justfile`.
- [ ] `P04.S50` - Document the PyPI 100 MB per-file cap acknowledgement and the three release-time options (file-size grant request, future PDF extras split, private-index publication); `RELEASING.md`.

## Parallelization

P01 must land first as a single coherent slice; nothing downstream
can resolve packaged data until the boundary, the hatch
configuration, and the in-process leaf-presence guard are in place.
Within P01, S01 strictly precedes S02 (the test imports the
locator). S03 may land alongside S01 because hatch configuration is
independent of the runtime locator. S04 strictly follows S03
because the built-wheel guard requires the force-include rules to
be in place. S05 is independent of the rest of P01 and may land in
parallel.

P02 strictly follows P01 because Settings defaults call into the
locator. Within P02, S06 must precede S07 (the invariant tests read
the new defaults). S08, S09, and S10 are confirmation checks that
run after S06 lands and may execute in parallel.

P03 strictly follows P02. Within P03 every step is independent at
the file level and may be parallelised freely once the locator is
available; conflicts arise only when two steps touch the same file,
which the per-file scoping prevents. P03.S33 (the final config
module cleanup) must land last in P03 because it removes any
remaining join the prior steps still relied on indirectly.

P04 strictly follows P03. The test-area steps S34 through S48 are
file-scoped to disjoint directories and may run in parallel. S49
strictly follows S48 because the quality gate is the verification
of the prior work. S50 is documentation-only and may run alongside
S49.

## Verification

The plan is complete when every Step is closed and the following
real-behaviour checks pass:

The in-process resource-locator leaf-presence test in
`src/aeat/core/test_resources.py` passes against the installed
package surface, covering at least one representative leaf in each
top-level subtree under `aeat/_data/`.

The built-wheel manifest assertion in
`src/aeat/tests/test_wheel_bundles_corpus_and_registry.py` passes:
`uv build --wheel` produces a wheel that contains every file
reported by `git ls-files corpus registry`, mapped to the
`aeat/_data/` prefix.

No occurrence of `PROJECT_ROOT / "corpus"` or
`PROJECT_ROOT / "registry"` remains anywhere under `src/aeat/`,
verified by repository-wide search.

The Settings env-override seam still wins over the resource-locator
default for `aeat_manuals_root`, `aeat_normatives_root`, and
`aeat_vat_catalogue_root`, verified by the existing override-based
tests under `src/aeat/domain/manuals/`,
`src/aeat/domain/normatives/`, and
`src/aeat/application/registry/`.

The project quality gate completes clean: ruff, ty, pytest with the
unit marker, and the structural audits declared in the justfile all
pass.

The release documentation surface acknowledges the PyPI 100 MB
per-file cap and the three release-time options without committing
the project to any one of them.
