---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0b8e6ff3d29d320cf76d7042b108feede9107b45fad4b01f780bf6ff5e16a1a7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` reference: `S127 Workspace field-manifest derivation`

S127 research grounded the accepted Workspace V1 D8 contract, the accepted Workspace interface decision, the W03.P20 plan, S125/S126 implementation, and the live validated registry schema through Vaultspec RAG on port 8766 followed by exact source inspection. RAG returned the governing public Workspace and registry-schema sources without an index-lag warning. There is no S127 Step Record yet; this reference is the implementation-ready contract for its eventual narrow implementation.

## Summary

### Canonical source and boundary

The only runtime source is a `RegistrySnapshot` returned by the public `cadrumo.domain.calculations.registry` facade through `ValidatedRegistryAuthority.snapshot`. It is already validated and carries the selected `ModeloDefinition`, `ModeloRevision`, legal/source maps, and all snapshot-scoped auxiliary schema maps. S127 must accept that public typed snapshot or a purpose-built public application port that returns it; it must never reopen TOML, call a loader, enumerate registry directories, or inspect a raw mapping. The generated manifest is conformance evidence only. It emits `ModeloWorkspaceSchemaRecordV1`-compatible safe rows and a deterministic digest, never a registry compiler node, selector payload, raw source identity, financial value, or persistence identity.

`ModeloWorkspaceContributorIdentityV1` from S125 is the only contributor identity. S127 declares one `FIELD_MANIFEST` producer contract through the S126 family; do not define another identity, epoch, digest, port, inventory, schema fingerprint, manifest version, or registry facade. The later owner-seam amendment assigns native manifest capture and generation plus correction of the application owner identity to S166, atomic relocation of the sole S126 declaration into the exact registration inventory to S167, and invocation plus two-pass assembly/retry to S128.

### Complete roots and traversal

Start the recursive type walk from the concrete public `RegistrySnapshot` class, not a directory listing or a hand-maintained family list. Traverse its `modelo`, `revision`, and every typed mapping value; that reaches `ModeloDefinition`, `ModeloRevision`, `RegistryCatalogues`-equivalent legal/source structures represented in the snapshot, revision families, and snapshot-only auxiliary declarations such as extraction, cross-reference, verification, application-link, deadline, schedule, construct, and dependency-classification records.

Use `model_fields` and resolved annotations. Unwrap `Annotated`; visit `BaseModel` subclasses; visit all arms of `Union` and `Optional`; record each discriminated-union arm by its discriminator literal; descend tuple/list/set/frozenset/sequence element types and mapping value types; treat `Literal`, scalar aliases, enums, date/decimal/str/bool, and opaque typed IDs as leaves. A path must encode model-field segments plus stable union-arm discriminator coordinates, not Python private module names, display labels, collection indexes, or data values. Sort paths lexicographically before digesting and keep a visited `(model class, canonical path)` guard so reused models are represented at each reachable public path while recursive structures terminate.

`DataBindingDefinition.selector` is the non-negotiable annotation hole: it is declared as `BaseModel`. Add the public registry-facade `selector_model_for_source` accessor, iterated over the canonical `BindingSourceKind` taxonomy, as a second derived root and walk every registered concrete selector model. The existing loader-fingerprint test proves that annotations alone miss selector-only types, including IVA category vocabulary. The S127 fixed-point test must carry the same anti-vacuity property: removing the selector-table roots yields a strictly smaller universe, and no concrete registered selector branch is absent from the manifest. Do not create a Workspace-owned selector table or duplicate registry dispatch grammar.

Do not treat Pydantic JSON Schema output as the denominator: `$ref` naming and schema generation ordering are implementation details and JSON Schema cannot close the selector hole. The denominator is the ordered typed traversal; a digest may use canonical primitive records containing only stable public type labels, canonical field paths, discriminator coordinates, and classification metadata.

### Classification map

Every leaf and every discriminated branch receives exactly one closed `ModeloWorkspaceSchemaClassification` value.

| Classification | Rule | Required metadata |
|---|---|---|
| `projected` | The workspace has a named safe DTO/reference arm for the public semantic field or branch. | Workspace destination/reference arm, canonical typed IDs, safe legal/source references, and family disposition. |
| `derived` | The field is represented only through an existing canonical application/domain producer. | Canonical producer identity and named derivation; no copied algorithm or reconstructed rule. |
| `backend_only` | The field is grammar, parser/compiler, transport-layout, raw source, secret/sensitive, persistence, execution, or otherwise lacks a safe Workspace representation. | Owning public authority and a bounded stable reason; never the value itself. |

The initial projected set is constrained by S125 `ModeloWorkspaceSchemaReferenceV1`: casilla, binding, formula, relation, parameter, export-field, continuity, formula-operand arms, relation endpoint arms, applicability, constraint, and export exposure. `ModeloWorkspaceSchemaRecordV1` is the only explanatory row; preserve its `family_disposition`, canonical identities, safe evidence references, and bounded section path. The record does not authorize a generic reflection dump.

Canonical derivations include the accepted `ModeloWorkReview` bounded-review producer, calculation-source graph provenance, canonical readiness projection, canonical closure report, locale resolver, and generated export-layout materialization where the registry explicitly says authored layouts are not the shipping layout. Specifically, derived export fields must delegate to the existing `derive_export_layouts_from_bindings` owner; reading authored `ModeloRevision.export_layouts` as current shipping field truth is forbidden.

Backend-only covers raw selector configuration, formula expression/compiler nodes, loader/fragment placement details, raw legal/source payload bodies, extraction parser configuration, fixed-width layout mechanics, validation internals, snapshot caches, repository/location data, and any unsafe or financial material. A backend-only record may say why it is excluded, but must not leak its raw value or source identity. Unknown additions, duplicate paths, stale manifest digest, missing registered selector branch, or an unclassifiable branch are fail-closed errors, never a default to backend-only and never an allowlist.

### Determinism and fixed-point proof

Define one frozen manifest record whose entries are sorted by canonical path and whose digest is `content_hash_hex` over a JSON-mode canonical serialization of its version, traversal-root identities, and entries. The generator must rebuild from the same selected validated snapshot and public selector registry; validation recomputes both entry order and digest. Test three independent directions: a genuine current snapshot round trip; structural mutation that removes one entry or repeats one path; and a changed reachable field/union selector root that causes regenerated output to differ. Do not pin an exact count: S127 is meant to fail when the schema grows.

Fixtures must use the real bundled validated authority and at least one revision whose bindings exercise selector-only concrete models, a discriminated union branch, a collection element, an export layout with generated fields, and a backend-only grammar field. The selector-table anti-vacuity mutation, a duplicate-path mutation, an unclassified-path mutation, and a stale-digest mutation must each fail the live validator. Reuse existing registry loader/fingerprint and export-materialization fixtures where possible; no mocked authority, hand-built raw registry mapping, or static list may prove completeness.

### Ownership and topology hazards

`cadrumo.domain.calculations.registry` is the public owner of registry schema classes, selector dispatch, validated authority, snapshots, and export materialization. `cadrumo.application.modelo._workspace_manifest` may consume only that facade and public application/core contracts. It must not import private `_schema*`, `_loader`, registry authoring fragments, adapters, persistence, entrypoints, CLI/MCP, Textual, operations journals, or raw registry maps. A cross-package import resolves through the owner package facade; no private import is excused because the data is read-only.

No compatibility alias, re-export bridge, fallback traversal, duplicate enum, parallel manifest generator, hard-coded count, permanent exemption list, or second registry grammar is permitted. New public registry fields naturally alter the generated denominator and must be classified in the same atomic change. S129 remains the only facade-export step; S127 must not widen `cadrumo.application.modelo.__all__`.

### Current blockers and next actions

There is no design blocker to implement S127. The operational prerequisite is only that the implementer first scaffold the missing S127 Step Record, then use the public registry facade, `RegistrySnapshot`, and its exported `selector_model_for_source` accessor iterated over `BindingSourceKind`. S127 must retain that production boundary even if a test helper can see private schema modules.
