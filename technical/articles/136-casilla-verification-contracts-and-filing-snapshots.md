# Casilla verification contracts and filing snapshots

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-136` · **Topic:** [Tax calculation domain](../topics/tax-calculation-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 12 registry modules, 4,866 physical lines, 217,623 bytes, and 46,727 measured `o200k_base` proxy tokens. All nine bounded pages were read in sequence. The code defines casilla and verification contracts, builds filing snapshots, checks legal/source applicability, exposes a reduced static-inspection view, and projects support and identity catalogues. No application code or tests were run and no source was changed.

## Casillas and verification

`CasillaDefinition` unifies casilla identity, labels, input mode, formula/binding sources, export exposure, continuity lineage, semantic role, constraints, and evidence references. Validators require formulas for computed values, bindings for bound values, and prevent formulas/bindings leaking onto incompatible input kinds. Alternate bindings must be unique. Internal-only casillas must be computed and cannot also declare export references or a separate export exemption; a declared export exemption cannot coexist with an addressed output. Continuity declarations are row-locally checked for required IDs and evidence, while cross-revision truth is left to registry-level checks. Casilla declaration and input rules (`src/cadrumo/domain/calculations/registry/schema_surfaces.py`) Export and lineage invariants (`src/cadrumo/domain/calculations/registry/schema_surfaces.py`)

Casilla constraints cover numeric sign/range, text length, regex, and enumerated values, with separate numeric and text violation methods. Calculation-completeness manifests enumerate canonical IDs in calculation closure, retain record-design metadata for drift checking, and require their derivation source in the evidence references. The manifest distinguishes intentional manual extraction of a difficult PDF design from a missing derivation. Constraint projection (`src/cadrumo/domain/calculations/registry/schema_surfaces.py`) Completeness manifest (`src/cadrumo/domain/calculations/registry/schema_surfaces.py`)

Verification expectations separate coverage-gated computed casillas, optional casillas reconciled only when present, and the subset backed by external authority. They reject duplicates, overlap between the first two sets, and external-grounding claims outside the reconciled union. Folds union declared scopes, choose the strictest tolerance and minimum coverage threshold, and refuse conflicting reconciliation-total casillas. The predicate DSL is a closed operator/syntax table with parsers for list, ratio, and profile-field forms; malformed or unknown expressions parse to `None` for validation/runtime refusal rather than being silently accepted. Blocking and advisory predicates intentionally have different semantics, and the comments mark several risk cases as advisory-only pending complete modeling. Verification expectation invariants (`src/cadrumo/domain/calculations/registry/schema_verification.py`) Canonical total fold (`src/cadrumo/domain/calculations/registry/schema_verification.py`) Predicate operator grammar (`src/cadrumo/domain/calculations/registry/schema_verification.py`) Predicate parser and fallback (`src/cadrumo/domain/calculations/registry/schema_verification.py`)

Live cross-reference declarations constrain surface type, evidence tier, allowed hosts and methods, authentication/AEAT authorization, synthetic-data use, and applicability predicates. Read surfaces reject synthetic data and non-read HTTP methods; authenticated reads require both authentication and AEAT authorization; authenticated simulators may declare POST. Workbook parity references require a runner and output cells for formula coverage, and must include the workbook source among their evidence. These are registry declarations and validation checks; the actual remote operation and workbook runner are outside this chunk. Live surface policy checks (`src/cadrumo/domain/calculations/registry/schema_verification.py`) Workbook parity requirements (`src/cadrumo/domain/calculations/registry/schema_verification.py`)

## Snapshot authority and temporal evidence

`build_validated_snapshot` is the filing-context boundary. Its default requested authority is the filing grade, and lower grades must be explicit. It selects a revision against the supported-year envelope, normalizes period selectors, derives export layouts, refuses unresolved materialized repeat families, checks capability/review/authority grade, validates revision references and legal/source applicability, then slices only the selected catalogues into a frozen snapshot. Cross-domain checks install from a fixed module list at the build boundary, avoiding accidental dependence on unrelated import order. Snapshot construction (`src/cadrumo/domain/calculations/registry/snapshot.py`) Filing snapshot pipeline (`src/cadrumo/domain/calculations/registry/snapshot.py`) Authority grade gate (`src/cadrumo/domain/calculations/registry/snapshot.py`) Review and filing capability gates (`src/cadrumo/domain/calculations/registry/snapshot.py`)

The temporal checks distinguish substantive law, which must cover the tax period's devengo date, from procedural material such as form approvals or manuals that may properly appear during the presentation window. Retroactive legal provisions may instead ground historical parameter values when a dated value window is wholly contained in the law's declared governed span and is not keyed to submission date. Source applicability is checked against the revision, with narrowly scoped accommodations for deadline calendars and historical continuity evidence tied to named endpoints. Reference collection explicitly walks nested declarations, including applicability-rule legal references, form fields, predicates, and deadline conditions, so the snapshot contains the provenance its consumers resolve. Devengo and presentation-window rules (`src/cadrumo/domain/calculations/registry/snapshot.py`) Historical parameter spans (`src/cadrumo/domain/calculations/registry/snapshot.py`) Source-window gate (`src/cadrumo/domain/calculations/registry/snapshot.py`) Snapshot reference closure (`src/cadrumo/domain/calculations/registry/snapshot.py`)

`RegistryRevisionInspection` is a deliberately narrower non-filing projection for static generators: it exposes selected revision IDs, labels/sections, source and legal references, bindings, formulas, parameters, and related evidence without a filing year, period, or full revision. Published views carry no source root, and validation requires their source slices to match the computed reference union. Only dictionary and XSD bytes are embedded in a published authority; other catalogued artefacts remain hash/size-pinned citations. Static inspection boundary (`src/cadrumo/domain/calculations/registry/static_inspection.py`) Inspection projection (`src/cadrumo/domain/calculations/registry/static_inspection.py`) Embedded source policy (`src/cadrumo/domain/calculations/registry/source_byte_availability.py`)

## Registry-backed projections

The support matrix derives each modelo's latest revision, calculation closure, export formats, extractor count, continuity changes, and portal references from registry declarations. Its typed rows explicitly report empty/false capabilities rather than inventing support. Separate family-situation catalogues project dated Art. 82 and Modelo 145 tokens, descriptions, legal references, and eligibility flags from governed mapping facts, avoiding conflation of their distinct vocabularies. Setup answer and wizard-page declarations are resolved lazily through governed mapping facts, with no hard-coded fallback when a required entry is missing. Support matrix probe (`src/cadrumo/domain/calculations/registry/support_matrix.py`) Matrix construction (`src/cadrumo/domain/calculations/registry/support_matrix.py`) Family-situation projection (`src/cadrumo/domain/calculations/registry/situacion_familiar_catalogue.py`) Modelo 145 projection (`src/cadrumo/domain/calculations/registry/situacion_familiar_m145_catalogue.py`) Setup mapping seam (`src/cadrumo/domain/calculations/registry/setup_profile_bindings.py`)

Spanish tax-ID format is itself a governed fact. The format adapter requires a complete closed key set, derives a typed kernel configuration without defaults, and requires a temporally invariant bootstrap format for initial catalogue construction. Runtime operations resolve the selected authority before validation; redaction admission returns an unknown result when authority lookup fails, allowing callers to apply a fail-safe instead of raising from a logging path. Tax-ID fact shape (`src/cadrumo/domain/calculations/registry/tax_id_format.py`) Runtime authority lookup (`src/cadrumo/domain/calculations/registry/tax_id_format.py`) Authority-backed operations (`src/cadrumo/domain/calculations/registry/tax_id_runtime.py`) Redaction admission fallback (`src/cadrumo/domain/calculations/registry/tax_identity_admission.py`)

## Security, quality, and limits

The strongest controls are explicit authority grades, review gates, source-content identities, legal time-window checks, bounded snapshot slices, and the separation of filing snapshots from static inspection. There are two scope caveats. First, the verification module's own documentation says the vocabulary of read-only HTTP methods is duplicated in a remote-state guard; two security allowlists can drift unless a shared contract or parity check keeps them aligned. Second, some under-modeled taxpayer/legal risks are intentionally advisory-only, so a successful filing verification must not be read as proof that every advisory has been resolved.

This chunk does not show the corpus path resolver, actual outbound request execution, export renderer, extraction engine, workbook runner, or user interface. The legal and source rows carry provenance claims whose byte-level and semantic proof belongs to separate build verifiers. No tests were run; this is a static description of declared checks and identified integration boundaries, not runtime evidence.

## Coverage appendix

All 12 assigned files were read fully across nine bounded pages; no unread ranges remain.

- registry/schema_surfaces.py (`src/cadrumo/domain/calculations/registry/schema_surfaces.py`) — 1–719
- registry/schema_verification.py (`src/cadrumo/domain/calculations/registry/schema_verification.py`) — 1–1,397
- registry/setup_profile_bindings.py (`src/cadrumo/domain/calculations/registry/setup_profile_bindings.py`) — 1–123
- registry/situacion_familiar_catalogue.py (`src/cadrumo/domain/calculations/registry/situacion_familiar_catalogue.py`) — 1–167
- registry/situacion_familiar_m145_catalogue.py (`src/cadrumo/domain/calculations/registry/situacion_familiar_m145_catalogue.py`) — 1–140
- registry/snapshot.py (`src/cadrumo/domain/calculations/registry/snapshot.py`) — 1–1,179
- registry/source_byte_availability.py (`src/cadrumo/domain/calculations/registry/source_byte_availability.py`) — 1–100
- registry/static_inspection.py (`src/cadrumo/domain/calculations/registry/static_inspection.py`) — 1–405
- registry/support_matrix.py (`src/cadrumo/domain/calculations/registry/support_matrix.py`) — 1–330
- registry/tax_id_format.py (`src/cadrumo/domain/calculations/registry/tax_id_format.py`) — 1–205
- registry/tax_id_runtime.py (`src/cadrumo/domain/calculations/registry/tax_id_runtime.py`) — 1–29
- registry/tax_identity_admission.py (`src/cadrumo/domain/calculations/registry/tax_identity_admission.py`) — 1–72
<!-- /preserved:article -->
