---
tags:
  - '#adr'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ad8aff4a2527765970eb0c550b599238643c967d75fff524b9703ff5fde1ee68'
related:
  - "[[2026-08-22-source-casilla-integration-research]]"
  - "[[2026-08-22-modelo-work-binding-architecture-reference]]"
  - "[[2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - '[[2026-08-22-source-casilla-integration-composite-provenance-research]]'
---
# `source-casilla-integration` adr: `ratcheted source-domain-to-casilla connectivity` | (**status:** `accepted`)

## Problem Statement

The calculation architecture guarantees that every registry-declared binding source is enrolled, explicitly deferred, or reserved, but it does not guarantee that every existing typed source domain which should feed a filing has been declared and connected. `2026-08-22-source-casilla-integration-research` establishes this upstream blind spot and the need for a durable responsibility that remains measurable as the application grows.

The decision must define how candidates enter that responsibility, how legal identity is adjudicated, what constitutes a complete connection, and how continuing discovery is represented without an implementation plan that can never honestly complete.

## Considerations

- Existing downstream source enrollment and no-silent-blank behavior remain authoritative and must not be duplicated or weakened; `2026-08-22-source-casilla-integration-research`.
- Source and casilla terminology does not establish substitutability; target revision, legal meaning, constraint shape, grain, sign, units, and override policy must agree; `2026-08-22-modelo-work-binding-architecture-inventory-gap-verification-reference`.
- Manual input, formal deferral, not-applicable classification, and deletion are legitimate dispositions; automation is not presumptively correct; `2026-08-22-source-casilla-integration-research`.
- Continuing responsibility needs monotonic state and recurring audit, while every implementation slice needs finite authorization and completion criteria.
- The established resolver, provenance, secure-storage, and registry-binding contracts are extension points, not targets for a parallel integration architecture; `2026-06-10-calculation-aggregation-taxonomy-adr` and `2026-08-22-modelo-work-binding-architecture-reference`.

## Considered options

### Permanently open roll-up plan

Keep one L3 plan open indefinitely and append every discovered connection. This centralizes visibility but has no stable completion condition, conflates discovery with authorization, accumulates stale rows, and lets a campaign narrow its own standing goal.

### Pre-enumerated source mega-plan

Census the current tree once and plan every candidate together. This provides an apparent endpoint but falsely assumes the initial census and legal mappings are complete, and couples unrelated evidence dependencies into one execution stream.

### Inventory-only feature

Connect the known inventory domain and close. This yields immediate value but leaves the upstream discovery blind spot intact and repeats the same failure for fincas, deferred row sources, and future domains.

### Ratcheted census plus finite vertical slices

Establish one canonical connectivity census and recurring audit, bootstrap the mechanism through a finite plan, and authorize each accepted source-to-casilla connection as a bounded vertical slice with its own grounding and lifecycle. This retains continuous responsibility without an immortal implementation plan.

## Constraints

- A candidate cannot become implementation-ready until official evidence settles modelo, revision window, target semantic role, source fact, aggregation, sign, units, rounding, temporal window, entity/activity grain, absence semantics, and override policy.
- Candidate discovery from names or numeric casilla identifiers is advisory only and cannot author a binding.
- The census uses a closed disposition set: `connected`, `connect_candidate`, `grounding_blocked`, `ingress_blocked`, `registry_blocked`, `manual_by_design`, `duplicate_or_stale`, and `not_applicable`.
- Every census row carries re-fetchable grounding, an owner, and a linked bounded follow-up or explicit review condition where unresolved.
- Existing `BindingSourceKind`, source-disposition parity, `ModeloSourceResolver`, `CalculationSourceResolution`, registry validation, and encrypted `CalculationRevision` remain the only production integration path.
- Inventory is the first known candidate, not a pre-decided mapping. Its current signed helper and current M100 inventory boxes require tax adjudication before implementation.
- Documentation approval and implementation-plan approval remain independent user gates.

## Implementation

Create a finite bootstrap feature that derives the registry-side inventory of manual casillas, declared bindings, relations, formulas, and source dispositions from validated snapshots; enumerates typed source domains, secure repositories, supported ingress, row assemblers, readiness declarations, and exported calculation helpers; and joins them only through evidence-backed candidate records.

Persist the resulting census in one canonical machine-checkable form with the closed dispositions above. Add a monotonic gate that refuses unclassified new capability, unexplained disappearance or regression of accepted candidates, expired deferrals without linked action, and a `connected` claim lacking resolver ownership plus encrypted calculation-revision proof. Semantic-name matches remain report-only.

For every `connect_candidate`, require an official-source adjudication followed by one vertical slice through the existing architecture: canonical source taxonomy, typed selector validation, registry binding and casilla linkage, enrolled resolver, precedence and collision policy, diagnostics, source identity and fingerprint provenance, secure revision round trip, operator-path anti-dormancy proof, conflict proof, and replay/review/export proof where supported.

The bootstrap plan establishes the census and ratchet and adjudicates inventory as its first known candidate. It may implement inventory only if that adjudication resolves its target semantics. Later candidates run as bounded child features with their own research, ADR or amendment, plan, execution records, and review. A recurring audit refreshes the census; no plan remains open solely to symbolize continuing ownership.

The documentation lane separately aligns operator and developer material with the actual boundary: bindings are projections rather than attachments, secure business aggregates remain independently owned, foreign-asset rows are already connected, and stock inventory remains unconnected until a verified slice lands.

## Rationale

The ratcheted-census option is the only option that covers both present and future upstream disconnects while retaining falsifiable completion criteria. It composes with the accepted calculation aggregation decision, makes non-automation outcomes explicit, and prevents lexical similarity from becoming tax behavior. The research and two implementation references provide the grounding for the census boundary and vertical-slice contract.

## Consequences

- The project gains one auditable answer to which existing source capabilities are connected, blocked, intentionally manual, stale, or inapplicable.
- Inventory becomes the first adjudicated example without prejudging an unsafe `0155` or signed-value mapping.
- Deferred row families, fincas, assets, and future domains become visible through one classification vocabulary rather than ad hoc backlog prose.
- Every accepted connection carries source ownership, diagnostics, provenance, replay, encrypted persistence, and operator-path proof.
- Some apparently obvious automation candidates will remain manual or be rejected after tax adjudication.
- Continuous discovery produces recurring audit work and bounded child features rather than one perpetual plan, increasing lifecycle-document count while keeping each authorization honest.
- The census and gates require maintenance whenever a new secure domain, ingress surface, assembler, helper, source kind, or registry binding is introduced.

## Amendment (2026-08-23): composite calculation-source provenance

### Problem

The accepted connectivity proof requires the resolver-owned binding source to agree with persisted calculation provenance. That is sufficient for a direct source, but it is not truthful for a composite resolver: the resolver owns the resolved economic object while its inputs retain different upstream source kinds. Foreign-asset aggregation and IVA wallet reconciliation expose this distinction. Treating either axis as the other makes a real resolver appear disconnected or lets an upstream contributor incorrectly satisfy connectivity.

Codebase-wide semantic and regex sentinels confirmed that this distinction is not already implemented elsewhere. The existing `CalculationSourceProvenance`, `CalculationSourceRef`, `CalculationRevision.source_provenance`, revision-identity payload, and live proof authority are therefore amended in place; no parallel provenance or canonical-casilla model is authorized.

### Decision

Calculation-source provenance represents both resolution ownership and contribution lineage. Its canonical vocabulary is:

- `resolved_binding_source: BindingSourceKind`: the source kind owned by the resolver that produced the resolved economic object;
- `contributor_source_kind: str`: the contributor's existing source taxonomy value;
- `contributor_binding_source: BindingSourceKind | None`: the contributor's registry binding kind when one exists;
- `lineage_role: CalculationSourceLineageRole`, with the closed values `PRIMARY` and `CONTRIBUTOR`;
- the existing `source_ref` and `fingerprint`, which remain the durable object identity and content identity for that node; and
- `parent_source_ref: str | None`, which links a contributor to its primary resolved object.

A direct resolver emits a `PRIMARY`; its resolved and contributor axes may be equal. A composite resolver emits exactly one truthful `PRIMARY` for each resolved economic object and zero or more `CONTRIBUTOR` nodes whose `parent_source_ref` identifies that primary. A contributor never satisfies resolver connectivity by itself. Every connected primary has a stable, non-empty `source_ref` and content fingerprint, and every contributor parent resolves to exactly one primary in the same provenance graph. Merge and persistence preserve resolver identity and parent edges. Every axis above participates in calculation-revision identity so that changing ownership, role, lineage, object identity, or content changes the revision identity.

`LiveSourceConnectivityProofAuthority` accepts a persisted connection only when exactly one `PRIMARY` matches the claimed resolver, `resolved_binding_source`, durable reference, and fingerprint. Contributor nodes are supporting evidence only.

For IVA wallet reconciliation, the primary reference is the existing immutable `iva_wallet_decision_event_key(decision)` and the resolved binding source is `IVA_WALLET_DECISION`; the decision's canonical content digest is its primary fingerprint. Authority sources are contributors parented to that event key. The mutable wallet-decision lookup key is not a provenance identity.

Foreign-asset observations do not currently expose an authoritative unique identity for the resolved asset. `source_object_id` identifies an upstream carrier, `asset_external_id` is not uniqueness-enforced, and row position or `(source_kind, asset_class)` would be synthetic identities. The M720 composite therefore remains `grounding_blocked` until a typed persisted asset identity is established or a separately approved, uniqueness-enforced composite key is grounded. No transient aggregation key may be fabricated to make the proof pass.

This is an atomic, no-legacy replacement of the existing provenance shape. Compatibility aliases, defaults, dual readers, and alternate proof paths are not permitted. All constructors, serializers, revision hashing, encrypted persistence, resolver emissions, authority checks, and tests move together.

### Consequences

- Composite calculations can prove both who resolved the filing value and which upstream facts contributed without collapsing the two meanings.
- IVA wallet decisions can connect through an already durable event identity.
- Foreign assets remain visibly blocked instead of receiving a convenient but ungrounded primary identity.
- Existing provenance constructors and encrypted revision fixtures require a coordinated migration, and primary-only authority checks become stricter.

## Amendment (2026-08-23): canonical live connected-proof composition

### Problem

The accepted census may classify a row as `connected` only when production enrollment, operator reachability, source evidence, and encrypted calculation-revision survival agree. Those axes already have canonical authorities, but a connected claim is not trustworthy if it is assembled from census-authored assertions, repository descriptors without content proof, or a synthetic fixture derived from the same claim it is intended to verify.

The decision must define one production composition and one deterministic CI proof lifecycle without introducing a parallel ownership catalogue, workflow catalogue, storage path, or evidence vocabulary.

### Considered options

- Trust census declarations. Rejected because the proof would repeat the claim under test.
- Use ad hoc test-only ownership, workflow, or storage substitutes. Rejected because green tests could describe a route production does not own.
- Require operator financial data or external credentials. Rejected because the gate must be deterministic, safe, and runnable in isolated CI.
- Compose the existing live authority from canonical production catalogues plus independently authored encrypted proof evidence. Accepted.

### Decision

`LiveSourceConnectivityProofAuthority` is the sole authority for promoting a census row to `connected`. It composes, without copying or widening them:

- the canonical production source-ownership catalogue;
- the canonical supported operator-workflow catalogue;
- repository-root evidence descriptors whose declared files are verified by content digest relative to the repository root; and
- a real encrypted `CalculationRevision` read through the production calculation-revision repository.

Connected-proof composition occurs automatically only when the census contains at least one row claiming `connected`. A census with no connected rows does not create an encrypted fixture, temporary repository, credential request, or vacuous connected-proof result.

For each connected row, CI creates an independently authored synthetic source fixture whose expected resolver, owned source, durable source reference, fingerprint, workflow route, and target connection identity are defined outside the census claim. The fixture is calculated and persisted through the real encrypted `CalculationRevision` repository, then reloaded and adjudicated by `LiveSourceConnectivityProofAuthority`. The proof must fail when the census claim changes without a matching change to the independent fixture, when the fixture changes without matching production behavior, when ownership or workflow membership is absent, when a repository evidence digest diverges, or when encrypted provenance does not match the required primary connection.

The synthetic proof fixture uses fabricated, non-personal, non-financial values. It does not read an operator profile, production bucket, environment credential, external service, or persistent developer storage. CI creates an isolated ephemeral secure-object repository and key context, executes the production write/read path, and destroys that lifecycle deterministically after the proof. No generated secret, ciphertext, database, or fixture state survives the run.

Repository evidence is descriptor-safe: descriptors identify repository-relative files plus cryptographic content digests. Paths outside the repository root, unresolved traversal, missing files, non-regular targets, and digest mismatches fail closed. A filename, class name, or census locator alone is not evidence of executable connectivity.

The connected-proof result is conjunctive. Resolver ownership, supported workflow reachability, repository evidence integrity, and encrypted revision survival must all pass for the same connection identity. No axis may infer or repair another, and contributor provenance cannot substitute for the primary resolver-owned proof defined by the composite-provenance amendment.

### Rationale

This composition reuses the accepted production authorities and makes the encrypted proof anti-tautological. It proves an independently authored source fact can traverse the actual production route and survive the actual encrypted repository while remaining deterministic and safe for CI.

### Consequences

- A `connected` row becomes an executable production claim rather than census metadata.
- CI remains credential-free and contains no taxpayer or financial data.
- Repositories with no connected rows incur no synthetic encrypted lifecycle.
- Production ownership, workflow, evidence, or persistence drift breaks the gate independently.
- Test fixtures require deliberate maintenance when a connection's production identity changes; updating only the census cannot restore green.
