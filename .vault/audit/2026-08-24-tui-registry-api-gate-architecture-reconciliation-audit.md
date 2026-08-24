---
tags:
  - '#audit'
  - '#tui-registry-api-gate'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e53f0e41b1f7b57df2055c74ce6670eb2006b590b6f43d68ce7aa3e6b00afe01'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-research]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-interface-adr]]"
---

# `tui-registry-api-gate` audit: `Independent architecture reconciliation`

## Scope

Three independent architecture reviewers examined the proposed registry API
gate against the accepted ADR corpus, the live application and registry
contracts, and the visual/editor goal. Discovery used `vaultspec-rag` before
whole-document reads and targeted code search. The code index was rebuilt after
doctor reported 154 missing code sections. The audit asks whether the proposed
record has the right authority, whether its contracts can be implemented from
current owners, and whether it is sufficient to authorize complex TUI work.

## Findings

### decision-ownership | critical | The proposed ADR combines three separately owned decisions

The read-only Modelo workspace projection is a legitimate new application
boundary. The public operation projection is already governed by the accepted
TUI architecture decision and its unfinished operation-platform steps. Modelo
editing has no accepted write-side authority. Approving the current combined
record would create a sibling authority for operation observation and silently
authorize an editor whose transaction semantics have never been decided.

### visual-authority | critical | No accepted record owns the complex workspace and editor architecture

The accepted TUI architecture deliberately excludes holistic information
architecture and final component design. The accepted TUI interface record
authorizes only a bounded read-only `modelo.view`; its plan excludes editable
Modelo fields and reserves `modelo.edit` for a later write-side decision. The
proposed API record also disclaims interface architecture. Consequently no
record currently owns routes, workspace hierarchy, edit sessions, dirty-state
navigation, row editing, validation timing, conflict handling, or the mapping
from supervised operation results back into a refreshed workspace.

### addressing-and-authority | high | Workspace identity and authority grade are underspecified

The request's “bucket or work identity” does not preserve the accepted natural
key contract. Normal addressing must use active bucket plus modelo, year, and
period; exact work identity is a discriminated advanced address with ambiguity
refusal and never an alternate revision selector. Static revision inspection is
not a lower authority-grade snapshot. A workspace result must discriminate its
admission path, law-selected coordinate, requested and declared grade, review
status, evidence horizon, and actual capability evidence. The proposed
authority-grade decision is not yet accepted, so Workspace V1 cannot freeze
those semantics.

### projection-denominator | high | “Complete causal graph” has no testable coverage denominator

The registry contains schema families and nested fields for parameters,
dispatch, construction, projection, extraction, verification, applicability,
manifests, governance, and evidence beyond the classes listed in the proposal.
A generated classification manifest must account for every registry field as
projected, derived, or backend-only with an owner and reason. Frontends must
receive explanatory application DTOs rather than copied compiler selectors or
private registry grammar. Row and provenance coordinates must reuse canonical
binding identifiers, row indexes, source roles, references, fingerprints, and
parent edges.

### operation-observation | high | The proposed operation projection is neither complete nor correctly owned

The canonical operation snapshot does not itself contain current progress; that
state resides in the event stream. The proposed fields also omit the independent
terminal condition. A public projector therefore needs an atomic fold tying
snapshot revision, event cursor, replay, progress, notices, interactions,
settlement, and effects together. That contract must amend the accepted TUI
architecture decision rather than be introduced by this registry API record.

### mutation-contract | critical | Operation enrollment is not a write-side Modelo contract

Registration and baseline revalidation do not decide edit commands,
editability, repeated-row identity and ordering, clear versus unset versus zero,
validation phases, persistence and rollback, stale refresh or rebase, or effect
and refusal mappings. A dedicated write-side/editor ADR must define those
semantics and stage each mutation before any visual edit action is enabled.

### capability-ownership | high | Capability composition risks a second readiness truth

`OperatorStateProjection` is already declared the canonical operator-facing
state view and contains Modelo readiness. Registry closure and filing/export
coverage also have existing owners. Workspace capabilities must project or
extend those owners with exact coordinates, precedence, evidence, refusal
translation, and reconsideration rules. A new synthetic readiness graph would
fork authority.

### localization-and-versioning | high | Locale and version contracts are not yet representable

The accepted localization cascade requires language-neutral schema and a
canonical resolver, while the current resolver returns only `str | None` and
cannot expose requested, resolved, and fallback disposition. The Casilla
read-model wording therefore needs reconciliation. Workspace public version,
operation observation version, and durable journal schema version must remain
distinct and an unsupported public version must produce a typed refusal.

### secure-interaction | critical | Detachable secret and recovery interactions have unresolved custody

Persisted pending interaction state retains only a token digest, while response
requires the raw bearer token. Generic secret input therefore cannot promise
detach, restart, or fresh-process completion. The accepted recovery design also
requires one-time display and verification while the interface record says
generated recovery material is never displayed. Initial public interaction
scope must remain limited to supported review apply/reject until the
operation-owned `EphemeralSecretSubmission` contract and recovery reconciliation
are accepted and proven.

### corpus-drift | high | Accepted records and live code contain unresolved drift

The accepted TUI architecture already requires a public operation projection,
but live consumers still expose `OperationPersistedSnapshot`. The Casilla
read-model ADR cites a deleted state-projection ADR. Existing persistence
migration readers conflict with the project rule that pre-release cutovers
delete legacy on-disk compatibility. These are reconciliation tasks, not
precedent for expanding the proposed API authority.

### frontend-scale-and-proof | high | The visual contract lacks scale, consistency, and accessibility gates

The proposal does not decide whether a large causal graph and repeated-row set
is returned atomically or through baseline-consistent facets, nor how refresh,
replay, reconnect, backpressure, and resynchronization behave. It also lacks a
derived lifecycle/action inventory and production-composition proof across the
required viewport, locale, theme, focus, overflow, row-volume, and
non-colour-only accessibility matrix.

## Recommendations

1. Narrow the proposed registry API ADR to a read-only, versioned
   `ModeloWorkspaceProjection` plus capability/refusal facade. It must consume
   canonical readiness and closure owners, preserve accepted addressing, define
   admission-path and authority-grade metadata, and carry a generated registry
   field-classification manifest.
2. Amend the accepted TUI architecture ADR to own the versioned public operation
   observation projector and atomic snapshot/event fold. Keep journal schemas
   private and versioned independently.
3. Author a dedicated Modelo workspace interface and write-side ADR before
   `modelo.edit`. It must decide route and destination inventory, view-model
   ownership, edit-session transactions, repeated rows, validation, stale
   conflict, operation-result refresh, destructive approval, and accessibility.
4. Reconcile the accepted localization, Casilla read-model, recovery, and
   no-legacy decisions before their affected cohorts open. Remove the dangling
   ADR relationship and classify existing migration readers explicitly.
5. Use sequential cohort receipts: C0 operation platform; C1 bounded read-only
   review relocation; C2 complex read workspace after authority-grade and
   Workspace V1 acceptance; C3 staged editing after the write-side and secure
   interaction contracts; C4 individually enrolled verify, file, export, amend,
   and lifecycle actions; C5 fixed-point visual, scale, accessibility, and
   production-composition closure.
6. Do not author a competing implementation plan. Once the revised and new ADRs
   are explicitly approved, amend the canonical TUI architecture and interface
   plans with dependency receipts containing source ancestry, public contract
   versions, schema and action inventory digests, conformance results, secure
   non-retention proof, and the cohort opened.
