# Revision selection, withholding aggregation, and row provenance

[Technical overview](../README.md) · [Article index](README.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-137` · **Topic:** [Tax calculation domain](../topics/tax-calculation-domain.md)

<!-- preserved:article -->
## Scope and method

This chunk covers 11 modules, 3,200 physical lines, 136,835 bytes, and 30,571 measured `o200k_base` proxy tokens. All six bounded pages were read. It contains canonical revision selection, cross-domain validation, registry-backed withholding and mediation vocabularies, Modelo 190/193/296 aggregation, and row provenance primitives. No application code or tests were run and no source was changed.

## Temporal revision selection

`ModeloRevisionDirectory` is a point-selection index: it retains small immutable revision windows, period selectors, filing schedules, pending-order facts, and endpoint source enrollment without copying all revision payloads. It materializes a one-revision modelo view while validation context preserves the directory's complete revision-ID set, so predecessor and historical endpoint references can still be checked. The directory requires a one-to-one enrollment for every revision. Directory and point materialization (`src/cadrumo/domain/calculations/registry/temporal.py`) Directory construction (`src/cadrumo/domain/calculations/registry/temporal.py`)

Selection first applies the hard support envelope and declared inception. It then matches explicit years/period overrides or chooses the nearest compatible authored year, preferring the earlier year on equal distance. A pinned revision ID narrows the already-selected legal candidate rather than authorizing a farther revision to bypass the nearest-anchor rule. Projected reference dates preserve their within-year offset, clamping the day for shorter months. If an `on` date lies within a revision's governed tax-period window, that tier wins; only when no candidate governs the date are the declared filing windows consulted. This permits a prior-period return to be filed after the tax period closes without widening substantive validity dates. Year-only requests refuse when a mid-year design boundary leaves more than one candidate. Support and inception gates (`src/cadrumo/domain/calculations/registry/temporal.py`) Nearest authored anchors (`src/cadrumo/domain/calculations/registry/temporal.py`) Date-offset projection (`src/cadrumo/domain/calculations/registry/temporal.py`) Governed-period versus filing-window tiers (`src/cadrumo/domain/calculations/registry/temporal.py`) Year and period selectors (`src/cadrumo/domain/calculations/registry/temporal.py`) `select_authored_revision_metadata` separately bypasses the product support gate for historical-law lookup while still refusing dates before the modelo's declared inception. Authored historical selection (`src/cadrumo/domain/calculations/registry/temporal.py`)

When no edition is authored for a requested year, the selector also preserves whether the gap is an explicitly declared pending approving order or an ordinary missing revision. A pending order produces a specialized refusal with its cited basis and expected publication year. Period selectors and annual schedules remain part of the selection metadata, so consumers can decide whether an actual filing period is supported without hydrating the full revision tree. Specific absence and pending-order refusal (`src/cadrumo/domain/calculations/registry/temporal.py`) The directory projection is therefore a bounded read model for selection, not a second store of the full calculation authority.

## Cross-domain and identity integrity

Peer domains register snapshot checks through a protocol, preserving dependency inversion. The registry names the exact required module for the modelos that have such a check; validation fails when that identity is absent even if some unrelated check has registered. Checks receive the selected filing year, revision binding IDs, and declared renta first-slice targets, preventing a check from using current-date facts or asserting requirements on revisions without the binding that creates them. Required check identities and registration (`src/cadrumo/domain/calculations/registry/validate_cross_domain_snapshot.py`) Named-gate enforcement (`src/cadrumo/domain/calculations/registry/validate_cross_domain_snapshot.py`) Revision identity validation catches duplicate IDs within and across record kinds, duplicate export ownership, metadata collisions, ambiguous bare casilla numbers reused across record segments, and empty placeholder revisions. Revision identity checks (`src/cadrumo/domain/calculations/registry/validate_revision_identity.py`)

## Withholding bindings and sensitive row data

The shared withholding resolver maps a filing-date clave vocabulary to the core enum and model applicability; it refuses undeclared tokens, malformed catalogues, and clave/model mismatches. `WithholdingObservation` holds perceptor identity and declaration detail for Modelos 190/193. It normalizes IDs before grouping and storage, preserves unknown country/province data as absent rather than inventing defaults, and rejects negative withholding amounts. Scalar facts share arithmetic helpers for distinct perceptors, distinct `(perceptor, clave, subclave)` perceptions, perceived income, and total retention. Catalogue-backed clave resolution (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`) Withholding observation fields (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`) Amount validation (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`) Shared scalar folds (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`)

Row selectors declare one of several explicit record identities: per recipient, per recipient/clave/subclave, or that key plus pending status and accrual year. Monetary fields sum across active observations; non-additive identity/detail fields must agree or materialization refuses instead of selecting an arbitrary first/last value. Grouped row count and grouped monetary sum reuse the same emitted-row grouping, keeping summary totals aligned with the records that export. Annual row identity (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`) Additive and non-additive row folds (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`) Row binding materialization (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`) The separate Modelo 296 observation/provider supports non-resident detail and a restricted perceptor-count or row-field selector contract. Modelo 296 provider and shape gate (`src/cadrumo/domain/calculations/registry/withholding296_bindings.py`)

The withholding and Modelo 296 records include NIFs, names, residence, addresses, family/disability attributes, and payment amounts. These are sensitive filing facts. The modules normalize identifiers and use frozen data objects but do not themselves provide redaction, authorization, or persistence encryption; those protections must come from the surrounding storage and export boundaries. Row provenance uses a hidden-from-repr opaque identity plus content fingerprint. Repeating-row list readers share an indexer that refuses duplicate coordinates rather than silently keeping the last mapping entry. Row provenance identity (`src/cadrumo/domain/calculations/row_source_identity.py`) Duplicate row-coordinate refusal (`src/cadrumo/domain/calculations/row_coordinate.py`) Direct row materialization provenance (`src/cadrumo/domain/calculations/row_casilla.py`)

## Smaller registry projections

Third-party declaration roles and travel-agency mediation types are projected from dated mapping facts into immutable typed catalogues with order, descriptions, and legal references. They reject undeclared tokens and expose declared selection sets; mediation's air-transport subset is itself a fact entry. Third-party role catalogue (`src/cadrumo/domain/calculations/registry/third_party_declaration_roles.py`) Clave-specific role selection (`src/cadrumo/domain/calculations/registry/third_party_declaration_roles.py`) Travel-agency mediation catalogue (`src/cadrumo/domain/calculations/registry/travel_agency_mediation.py`)

`verification_tolerance_or_exact` returns the snapshot's declared tolerance and falls back to exact equality if there are no verification expectations, avoiding an invented tolerance. Exact fallback (`src/cadrumo/domain/calculations/registry/verification_tolerance.py`)

## Quality, security, and limits

The temporal selector is explicit about the difference between a product's filing support, a model's inception, period validity, and its filing deadline. Its diagnostic errors retain distinctions such as unsupported year, absent revision, pending approving order, and ambiguous boundary. The withholding resolver likewise refuses contradictory annual detail, and the cross-domain checker fails on a missing required gate instead of passing because another check exists.

Some duplication remains in the surface: the standard withholding and Modelo 296 families have separate observation and selector models because their statutory record vocabularies differ. The modules do not show end-to-end extraction correctness, custody of source observations, user-visible handling of sensitive values, or the renderer consuming row values. Static review did not execute the temporal edge cases or aggregations; no test result is implied.

## Coverage appendix

All 11 assigned files were read fully across six bounded pages; no unread ranges remain.

- registry/temporal.py (`src/cadrumo/domain/calculations/registry/temporal.py`) — 1–919
- registry/third_party_declaration_roles.py (`src/cadrumo/domain/calculations/registry/third_party_declaration_roles.py`) — 1–176
- registry/travel_agency_mediation.py (`src/cadrumo/domain/calculations/registry/travel_agency_mediation.py`) — 1–159
- registry/validate_cross_domain_snapshot.py (`src/cadrumo/domain/calculations/registry/validate_cross_domain_snapshot.py`) — 1–205
- registry/validate_revision_identity.py (`src/cadrumo/domain/calculations/registry/validate_revision_identity.py`) — 1–237
- registry/verification_tolerance.py (`src/cadrumo/domain/calculations/registry/verification_tolerance.py`) — 1–27
- registry/withholding296_bindings.py (`src/cadrumo/domain/calculations/registry/withholding296_bindings.py`) — 1–172
- registry/withholding_bindings.py (`src/cadrumo/domain/calculations/registry/withholding_bindings.py`) — 1–1,165
- row_casilla.py (`src/cadrumo/domain/calculations/row_casilla.py`) — 1–35
- row_coordinate.py (`src/cadrumo/domain/calculations/row_coordinate.py`) — 1–41
- row_source_identity.py (`src/cadrumo/domain/calculations/row_source_identity.py`) — 1–64
<!-- /preserved:article -->
