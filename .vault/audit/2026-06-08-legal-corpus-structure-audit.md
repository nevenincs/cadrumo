---
tags:
  - '#audit'
  - '#legal-corpus-structure'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-06-05-codebase-monolith-decomposition-adr]]'
---

# `legal-corpus-structure` audit: `verification of bundled source data, settings resolution, and pdf-html corpus consistency`

## Scope

This audit performs a thorough review of the codebase to analyze and verify:
1. The encapsulation and integrity of the production legal corpus and registry definitions inside the package source.
2. The resolution paths in the settings and loader logic to ensure no runtime lookups point outside the bundled package directories.
3. The structural differences and consistency between the HTML normative corpus (committed in full) and the PDF test fixtures (intentionally thin).
4. The recent topology changes and codebase restructurings (Test Topology Refactor, monolith decomposition, and marker taxonomy hardening).

## Findings

### Finding A1: Production Corpus and Registry Bundling
All production read-only legal references, consolidated legislation catalogues, and registry TOML definitions are fully bundled inside the installed package source under `src/aeat/_data/`. Specifically, `src/aeat/_data/corpus/` holds manuals and consolidated HTML normatives, while `src/aeat/_data/registry/` holds the modelo TOML definitions. These are successfully force-included inside the built wheel via the hatchling package targets, which has been verified by the built-wheel tripwire tests in `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`.

### Finding A2: Runtime Resource and Settings Path Resolution
At runtime, all read-only resource lookups are strictly routed through the resource boundary functions `packaged_data()` and `bundled_path()` defined in `src/aeat/core/resources/_boundary.py`. 
1. The `Settings` class in `src/aeat/core/config.py` uses `default_factory` wrappers pointing to `bundled_path()` (e.g. `aeat_normatives_root` defaults to `bundled_path("corpus", "normatives")`), guaranteeing that default paths resolve into the installed package directory.
2. Relative paths provided via environment overrides are normalized against `PROJECT_ROOT` in `src/aeat/core/paths.py`. This resolution is restricted to operator-writable outputs (such as `var/logs` or `var/secrets`) and is never used to fetch production legal metadata. No runtime-critical code references files outside `src/aeat/` by default.

### Finding A3: Sizing Consistency Between HTML and PDF Corpus
The apparent difference in size between the HTML normative corpus (209 committed files) and the PDF corpus (directories containing only manifests or consent logs) is intentional and stems from a design strategy to prevent repository binary bloat:
1. **HTML Normative Corpus**: Resides at `src/aeat/_data/corpus/normatives/html/` and contains lightweight, text-based consolidated legislation. Because HTML is text, committing these files does not bloat the git repository history and is necessary to back `legal_refs` in registry TOMLs.
2. **L1 Public Anchors**: Located at `tests/fixtures/pdf_corpus/l1_public_anchors/`. Contains only `_manifest.json` on disk because the heavy official PDFs are hash-pinned and downloaded dynamically during test time under `AEAT_FIXTURE_OFFLINE=1` to prevent binary bloat in the git history.
3. **L2 Scrubbed Private**: Located at `tests/fixtures/pdf_corpus/l2_scrubbed_private/`. Contains only `_consent_log.jsonl` because PII-scrubbed user files are local-only and gitignored.
4. **L3 Synthetic PDFs**: Located at `tests/fixtures/pdf_corpus/synthetic/`. Contains ReportLab generators that draw tax forms dynamically in memory during test execution rather than storing them.

### Finding A4: In-Tree PDF Receipts and Provenance Gate
Static parser validation target PDFs are committed under `src/aeat/tests/fixtures/justificantes/` (with subdirectories for each modelo) because they serve as stable regression targets. To ensure these committed binaries are authenticated:
1. ReportLab PDF canvas generators use `invariant=True` to write a deterministic creation date and stamp the `/Producer` metadata as `"aeat-test-fixture-generator"`.
2. The gate `test_verification_source_fixture_metadata.py` scans all justificantes and validates their sidecar `.json` provenance declarations (`real_corpus` vs `synthetic_generated`) against the extracted `/Producer` metadata from `pdfplumber`, ensuring no unauthenticated or out-of-date binaries slip in.

### Finding A5: Impact of Recent Restructurings
Recent codebase restructurings (June 5/6, 2026) have successfully decoupled test files, markers, and imports from package internals:
1. **Test Topology Refactor**: All test files have been relocated into domain-local `tests/` folders (e.g. `src/aeat/application/modelo/tests/`), removing naked test files from package roots.
2. **Marker Hardening**: Statically validated via `test_marker_integrity.py`, requiring exactly one execution scope and at least one layer marker (e.g. `hex_domain`, `hex_inbound_adapter`).
3. **Monolith Decomposition**: Modules are budgeted below 1250 lines, and all cross-package imports are routed through top-level package re-exports (`__all__` in `__init__.py`) rather than private submodules (e.g. `_catalogue.py`), preserving layer boundaries.
4. **Metadata Scrub**: Stale project-management annotations and step tokens (such as `W01.P01.S01`) were removed from code docstrings and test names.

### Finding A6: CLI Exposure of Legal References and Manuals
The CLI exposes legal references and handbook definitions through several non-destructive overview, discovery, and registry commands:
1. **Filing Applicability explanation**: `aeat app overview explain <modelo> [--year <year>]` decomposes why a model is applicable to the current taxpayer profile, referencing the corresponding legal provisions (e.g., `ley-11-2021:da-10`).
2. **Schema & Casilla Discovery**: `aeat app modelo describe <modelo>` and `aeat app modelo casillas <modelo>` list casilla definitions along with their `legal_refs` (legal catalogue references) and `source_refs` (record designs/layouts).
3. **Formula Rationale**: `aeat app modelo formulas <modelo> --explain` includes the legal and layout authority references backing each calculated expression.
4. **Citation Catalogue Lookup**: `aeat app registry citations view <normative_id> [--articulo <articulo>]` resolves normative citations to their consolidated legislative metadata, BOE permalinks, and local HTML anchors.
5. **Manual practical review**: `aeat app registry manuals view` and `rules` expose metadata and rules from the annual handbooks (Renta and IVA), linking rules directly back to the casillas they govern via the `references_casillas` attribute.

### Finding A7: Packaged Data vs Database Reads
1. **Schema and Legal References**: All registry TOMLs, legal catalogues, normatives, and manuals are read exclusively from package-bundled static data (located under `src/aeat/_data/`) using file-backed loader modules (e.g. `src/aeat/domain/manuals/_loader.py`). The CLI never queries the database for definitions, formulas, or handbook lookups.
2. **Operator Database (aeat.db)**: The SQLite database `aeat.db` is strictly bucket-scoped and reserved for persisting taxpayer profile facts, transaction ledgers, soft-tombstone records, and computed filing observations. It contains no static schema definitions.
3. **Manual Graceful Degradation**: Production manuals on disk (like `src/aeat/_data/corpus/manuals/renta/2025/`) omit extracted chapter structures (which are optional). When the structured `chapters.json` or `sections/` files are missing, the repository loader and CLI commands degrade gracefully by reading only the `manifest.json` metadata and reporting `structure_available=False`.

## Recommendations

1. **Retain PDF/HTML Storage Dichotomy**: Keep the lightweight HTML normatives committed in-tree while continuing to use dynamic fetching for L1 PDF anchors and dynamic generation for L3 PDFs to keep the repository free from binary bloat.
2. **Preserve `/Producer` Signature Verifications**: Enforce the `/Producer` metadata validation in the unit test suite to prevent the check-in of untracked or unscrubbed official PDFs.
3. **Strict Import and Boundary Enforcement**: Enforce the top-level package re-export import rule to prevent private submodule leaks during model additions or restructurings.
4. **Enforce Manual Graceful Degradation**: Continue to support missing handbook structure extractions by verifying that application services and CLI commands degrade gracefully when chapters and sections directories are absent, avoiding hard failures on un-extracted manuals.

## Codification candidates

None. The existing vaultspec rules adequately cover the structural and architectural invariants.
