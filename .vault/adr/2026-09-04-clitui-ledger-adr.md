---
tags:
  - '#adr'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:91b816f181fd221b2facf26b7c4a12869e973bf479c81b5e582e146cce8b807c'
related:
  - "[[2026-09-04-clitui-ledger-research]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-28-semantic-consolidation-cli-payload-projection-adr]]"
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
  - '[[2026-06-30-ledger-add-idempotency-adr]]'
  - '[[2026-06-10-llm-evidence-classification-adr]]'
  - '[[2026-07-14-google-optional-adapter-boundary-adr]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-07-24-evidence-revision-identity-adr]]'
---

# `clitui-ledger` adr: `backend authority and interface parity gates` | (**status:** `proposed`)

## Problem Statement

Ledger capability is distributed unevenly among backend services, CLI handlers, registries, calculation and filing paths, and an unimplemented TUI surface. The campaign needs one enforceable ordering: recover business authority from the CLI into typed backend use cases, prove the backend as a production tool, make the CLI a complete adapter over it, and only then admit Ledger TUI implementation. Without explicit gates, surface parity can conceal duplicated policy, disconnected registry routes, incomplete provenance, or exports that exist syntactically but cannot round-trip.

The evidence and current denominator are owned by `2026-09-04-clitui-ledger-research` and `2026-09-04-clitui-ledger-reference`. This ADR decides the target architecture and gate policy; it does not restate their mutable findings.

## Considerations

- The backend must be the single semantic authority; the CLI contract permits parsing, confirmation, localization, projection, redaction, and exit mapping, but not Ledger policy.
- Capability names alone are insufficient: direct backend proof, surface reachability, registry completeness, provenance, and readable artifacts are separate concerns.
- Review, classification, evidence, currency normalization, filing, and model-assisted operations affect financial correctness and require auditable before/after and source lineage.
- The active TUI architecture remains binding, but component existence is not installed capability.
- The repository requires current-only contracts: gaps are completed directly, without compatibility façades, aliases, fallback paths, or parallel authorities.

## Considered options

1. **Build TUI parity directly over existing CLI commands.** Rejected: fast presentation progress would preserve CLI-owned business rules and make the CLI an implicit backend.
2. **Move only duplicated CLI logic, then develop all surfaces in parallel.** Rejected: partial extraction does not prove backend product completeness and permits later surfaces to depend on unresolved composition and artifact gaps.
3. **Treat command registration as the parity denominator.** Rejected: it omits backend-only, registry, calculation, filing, provenance, artifact, and operational capabilities.
4. **Use a gated capability ledger and backend-first authority recovery.** Chosen: it makes ownership, proof, sequencing, and exit criteria explicit and independently reviewable.

## Constraints

- Existing accepted ADRs for Ledger interface contracts, TUI architecture, and semantic consolidation remain parents; this decision narrows campaign order and proof without displacing them.
- The capability denominator is the union of CLI endpoints and sub-operations, backend-only capabilities, known missing product capabilities, registry/calculation/filing routes, artifact products, and supported surfaces.
- No gate may be declared complete through mocks alone, handler existence, schema presence, or help output.
- Sensitive financial data, evidence, archives, model prompts, and model outputs remain subject to secure-storage and redaction rules.
- Google-oriented review exchange and offline review files must share a semantic schema; provider-specific mechanics may differ.
- Planning and implementation must keep a continuously updated matrix and preserve the research/reference documents as the evidence home.

## Implementation

### Capability ledger

The generated campaign matrix in the feature reference is the authoritative ledger. Every denominator row has a stable capability and sub-operation identity, semantic owner, typed command/result contract, applicable surfaces, composition obligations, artifact/provenance/registry obligations, gap classes, proof state, and links to real-behavior tests or independently opened artifacts. Applicability is explicit on every axis. Backend, CLI, and TUI each use `NOT_APPLICABLE`, `ABSENT`, `PARTIAL`, or `PROVEN`, with annotations `CLI_OWNED`, `DELEGATING`, `COMPONENT_ONLY`, and `INSTALLED` where they describe the current ownership or reachability state; remaining axes use `NOT_APPLICABLE`, `UNPROVEN`, `PARTIAL`, or `PROVEN`. Evidence links point to the reference rather than duplicating findings.

Gaps are classified as `AUTHORITY`, `PRODUCT`, `COMPOSITION`, `PROOF`, `REACHABILITY`, `ARTIFACT`, `PROVENANCE`, or `REGISTRY`. A row may carry several classes. Closing one class never implies the others.

### Ordered gates

1. **G0 — denominator and ownership freeze.** Enumerate the union denominator, assign semantic homes, applicability, typed contracts and obligations, record current proof, identify CLI-owned policy, reconcile overlapping plans, and impose the Ledger TUI implementation hold. It closes when every row has all mandatory matrix fields, a reviewed applicability decision and baseline evidence or explicit `UNPROVEN`, every finding has a gap class, plan ownership is singular, and the hold is recorded.
2. **G1 — semantic authority recovery.** Move each CLI-owned rule to its canonical domain owner when it is an intrinsic invariant or to its canonical typed application use case when it is orchestration/cross-aggregate policy; refactor affected handlers to delegate. It closes when no `AUTHORITY` gap or `CLI_OWNED` annotation remains, each moved rule has direct domain/application proof and an adapter detector test, and applicable backend ownership is at least `PARTIAL`.
3. **G2 — backend product completeness.** Complete missing backend operations, compositions, provider boundaries, artifacts, registry routes, and direct behavioral proof. It closes when every applicable backend, composition, artifact, provenance, registry, and proof axis is `PROVEN`, and no `PRODUCT`, `COMPOSITION`, `PROOF`, `ARTIFACT`, `PROVENANCE`, or `REGISTRY` gap remains. CLI and TUI axes do not participate in G2 closure.
4. **G3 — CLI clean break and completeness.** Remove residual Ledger policy from the CLI and prove every applicable backend capability through stable CLI contracts and valid outputs. It closes when each CLI-applicable row has CLI `PROVEN`, delegates to the canonical domain/application path, has interface-level success/refusal/artifact proof, and has no CLI `AUTHORITY`, `PRODUCT`, `REACHABILITY`, or `ARTIFACT` gap. TUI does not participate in G3 closure.
5. **G4 — TUI admission and parity.** Re-census reusable components, lift the hold, install complete Ledger workflows over the same backend use cases, and prove interactive reachability. It closes when each TUI-applicable row is `PROVEN` and `INSTALLED`, all cross-surface parity and reachability tests pass, no blocking gap remains on any applicable axis, and the campaign matrix is regenerated from final evidence.

A later gate does not begin for a convenient subset while an earlier gate remains open. Documentation and tests needed to close the active gate are part of that gate. Newly discovered capability reopens G0, receives a row and applicability decision, and reopens every later gate whose closure predicate it affects.

### Backend and adapter boundary

Domain aggregates and value objects own intrinsic invariants. Canonical typed application use cases own orchestration, authorization, cross-aggregate policy, defaults, normalization, classification and review transitions, split and merge semantics, batch behavior, attachment lifecycle, manual overrides, calculation inputs, registry routing, and export/import plans. Eligible frontend-triggered mutations enter through the canonical operation registry and supervisor; CLI and TUI cannot invoke around it. Adapters may own transport grammar, confirmation, locale-aware presentation, redaction, and error-to-interface mapping only.

Backend proof exercises real repositories and observable effects. Applicable operations cover success, refusal, idempotency, concurrency, batch and provider faults. Detector tests must fail when policy is moved back into adapters. Composition tests cover nonzero calculate-to-verify-to-evidence-to-export journeys.

### Ledger semantics and provenance

Evidence supports attach, metadata/view, download, detach, and atomic replace with immutable revision lineage. Replacement is refused for finalized filing evidence unless the filing is reopened through its governing workflow; the old revision remains encrypted and addressable by authorized history, references move only at commit, and failed persistence leaves the old revision authoritative while cleaning uncommitted encrypted bytes. Notes are append-only events: a committed note is never deleted or compensated, although a failed atomic transaction emits none.

Typed field edits bind to an aggregate version, stable actor/source identity, and exact changed-field set. Sensitive before/after values exist only in encrypted custody; ordinary projections are redacted. Stale baselines and same-idempotency-key/different-payload calls are refused. Manual overrides retain basis, actor, time, prior value, review state, and version. Imports record source-column mapping and normalization outcomes. Currency normalization records original amount and currency, normalized amount and currency, rate, rate source, effective date, and operation identity.

Single-record mutations, split/merge, evidence replacement, and a submitted multi-row edit change set are `ATOMIC`. Batch note append is atomic and emits all immutable note events or none. Bulk import and classification/evidence-reading proposal generation are `BEST_EFFORT`: they process stable input order, stage no failed item, and return a stable per-item identity and outcome; applying selected review proposals is one atomic change set. Mutating requests carry an idempotency key and aggregate or collection baseline version, except the accepted keyless manual-add path, which remains explicitly `non_idempotent_append`; creation uses an explicit absent-aggregate baseline and bulk requests bind the collection/version snapshot they were planned against. Replay lookup precedes baseline validation: same key and same payload returns the recorded result even after versions advance; same key with a different payload, duplicate item identity, or otherwise stale baseline fails closed. Atomic failure rolls back records, events, references, and staged bytes; best-effort failure cannot partially mutate an individual item.

Classification, evidence reading, and model-assisted suggestions are reviewable proposals rather than silent mutation and conform to the accepted evidence-classification posture. Processing is local-first; decrypted evidence is memory-only; off-host processing requires an eligible deployment plus explicit consent; paths and subprocess details never enter prompts or provider payloads; refusal and cleanup are fail-closed. Models may propose categories, splits, and extracted evidence, but never author regulated rates, bases, tax amounts, formulas, legal authority, or filing truth. The canonical model registry selects by stable capability/schema identity and records provider/model revision, prompt/template revision, output schema, evidence revision inputs, suggestion, reviewer disposition, and applied change set. An unavailable, unsupported, or schema-incompatible model produces a typed refusal, never fallback mutation.

The route unit is one declared source semantic, binding-family member, applicability predicate, period/revision, calculation consumer, and filing/export consumer. Every unit across the seven Ledger binding families is classified as proven, incomplete, or not applicable against the validated registry authority. Closure requires positive nonzero production calculation, exclusions, explicit missing/deferred-versus-zero behavior, pull/calculation parity, and verify/export/file refusal for every unrouted observation in OSS and non-OSS paths. Filing evidence contains declaration and legal authority, registry revision, formula provenance, source observations, and complete foreign-exchange source/effective-date lineage.

### Import, export, and recovery products

Three products are distinct contracts:

- **Flat interchange:** deterministic CSV, JSONL, and XLSX data exports that reopen in independent readers. JSONL round-trips the complete typed interchange record. CSV and XLSX round-trip the documented scalar projection; evidence bytes, immutable history, and nested provenance are intentionally excluded and represented by stable identifiers. Import/export tests compare canonical values, ordering keys, null semantics, decimal/date/currency precision, and declared-loss manifests.
- **Review exchange:** an offline workbook and checksummed machine-readable sidecar share an exchange identity, schema revision, baseline versions, stable row identities, editable-column declaration, and artifact digest. Spreadsheet edits outside declared cells or without the matching sidecar are refused. Review return reports accepted, rejected, unchanged, conflicted, and invalid rows; selected accepted changes apply as one atomic change set, with stale baselines refusing the set. A Google-oriented adapter is optional and non-authoritative: it uses canonical writers/readers and the same review plan rather than owning Ledger semantics.
- **Secure recovery archive:** a versioned, authenticated, encrypted backup contains Ledger aggregates, evidence revisions, notes, change sets, provenance, registry-linked snapshots, and a manifest. Unsupported schema versions, failed authentication/integrity, or incomplete contents fail before mutation. Restore targets a fresh empty store by default; a nonempty-store collision is refused rather than merged. Successful restore proves canonical equality of all included identities, bytes, versions, links, and provenance.

Directory import, provider ingestion, and review-return import use backend plans with dry-run summaries, the batch rules above, and auditable results. Decrypted sensitive intermediate material exists transiently in memory only and is never written to temporary files or plaintext side stores. An operator-authorized final plaintext export destination is a separate explicit egress contract; success, refusal, cancellation, and provider faults leave no intermediate plaintext.

### TUI admission and plan ownership

At G0, active overlapping Ledger TUI plans are reconciled and `clitui-ledger` becomes the sole campaign plan for Ledger parity; an explicit Ledger TUI implementation hold is recorded. No Ledger TUI production code is changed before G3 closes. G4 lifts the hold, re-censuses reusable components, and implements against the accepted TUI architecture. A component counts only when reachable from the installed application and backed by the canonical use case.

### Approval protocol

This ADR remains proposed until two independent architectural reviewers issue `ACCEPT` for the same decision-content revision. A ruling is `ACCEPT`, `ACCEPT_WITH_REQUIRED_CHANGES`, or `REJECT`; any decision-content change invalidates both rulings and requires two fresh reviews. The approval record stores reviewer, date, reviewed decision-content hash, ruling, and blocking conditions. Administrative status and approval-record edits are excluded from the reviewed decision content to avoid a self-referential hash.

## Rationale

The gated capability ledger wins because the campaign's central risk is false parity: three surfaces may expose similar verbs while policy ownership, route completeness, provenance, or artifacts remain different. Backend-first sequencing makes one implementation authoritative; independent axes prevent a passing command test from standing in for production behavior; and hard gate closure prevents TUI work from institutionalizing unresolved CLI/backend seams. The chosen export split also avoids conflating human review, machine interchange, and disaster recovery.

## Consequences

- TUI delivery starts later, but it starts against a complete and directly tested backend contract.
- CLI handlers become thinner and breaking cleanup is expected; no legacy compatibility layer will preserve displaced policy.
- The matrix and gate evidence add sustained bookkeeping, but expose regressions and campaign status without narrative reinterpretation.
- Backend test cost increases because artifact readability, restoration, provider failure, provenance, and full compositions require integration fixtures.
- Review workbooks, Google exchange, flat exports, and recovery archives become separate maintained products with shared semantic plans where appropriate.
- Model-assisted Ledger operations become attributable and reviewable, enabling safe automation without making model output authoritative.
- Registry and currency-provenance gaps become release blockers instead of deferred observations.
