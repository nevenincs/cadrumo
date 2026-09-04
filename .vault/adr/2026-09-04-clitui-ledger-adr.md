---
tags:
  - '#adr'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:841f5fa458e5f6890c379b2bcaff28ab27f688e72f5e3f408c40f2f2ae27cc83'
related:
  - "[[2026-09-04-clitui-ledger-research]]"
  - "[[2026-09-04-clitui-ledger-reference]]"
  - "[[2026-06-10-ledger-interface-contract-adr]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-28-semantic-consolidation-cli-payload-projection-adr]]"
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

Every denominator row records an owner, operation, and independent status axes for backend, CLI, TUI, composition, artifact validity, provenance, registry routing, and proof. Backend uses `ABSENT`, `CLI_OWNED`, `PARTIAL`, or `COMPLETE`; CLI uses `ABSENT`, `CLI_OWNED`, `DELEGATING`, or `COMPLETE`; TUI uses `ABSENT`, `COMPONENT_ONLY`, or `INSTALLED`; remaining axes use `NOT_APPLICABLE`, `UNPROVEN`, `PARTIAL`, or `PROVEN`. Evidence links point to the reference rather than duplicating findings.

Gaps are classified as `AUTHORITY`, `PRODUCT`, `COMPOSITION`, `PROOF`, `REACHABILITY`, `ARTIFACT`, `PROVENANCE`, or `REGISTRY`. A row may carry several classes. Closing one class never implies the others.

### Ordered gates

1. **G0 — denominator and ownership freeze.** Enumerate the union denominator, assign semantic homes, record current proof, and identify CLI-owned policy.
2. **G1 — backend authority recovery.** Move every CLI-only business decision into canonical typed backend use cases and refactor affected CLI handlers to delegate.
3. **G2 — backend product completeness.** Complete missing backend operations, compositions, provider boundaries, artifacts, registry routes, and direct behavioral proof.
4. **G3 — CLI clean break and completeness.** Remove residual Ledger policy from the CLI and prove every applicable backend capability through stable CLI contracts and valid outputs.
5. **G4 — TUI admission and parity.** Re-census reusable components, then install complete Ledger workflows over the same backend use cases and prove interactive reachability.

A later gate does not begin for a convenient subset while an earlier gate remains open. Documentation and tests needed to close the active gate are part of that gate.

### Backend and adapter boundary

Canonical typed backend use cases own validation, defaults, normalization, classification and review state transitions, split and merge semantics, batch behavior, attachment lifecycle, manual overrides, calculation inputs, registry routing, and export/import plans. CLI and TUI adapters may own transport grammar, confirmation, locale-aware presentation, redaction, and error-to-interface mapping only.

Backend proof exercises real repositories and observable effects. Applicable operations cover success, refusal, idempotency, concurrency, batch and provider faults. Detector tests must fail when policy is moved back into adapters. Composition tests cover nonzero calculate-to-verify-to-evidence-to-export journeys.

### Ledger semantics and provenance

Evidence supports attach, metadata/view, download, detach, and atomic replace. Notes are append-only. Typed field edits persist encrypted change sets with redacted projections. Manual overrides retain basis, actor, time, prior value, and review state. Imports record source-column mapping and normalization outcomes. Currency normalization records original amount and currency, normalized amount and currency, rate, rate source, effective date, and operation identity. Batch mutations declare `ATOMIC` or `BEST_EFFORT` semantics and expose per-item outcomes.

Classification, evidence reading, and model-assisted suggestions are reviewable proposals rather than silent mutation. The backend integrates with the model registry and records model, prompt/template revision, output schema, evidence inputs, suggestion, reviewer disposition, and applied change set.

Each applicable route through the seven Ledger registry binding families is classified as proven, incomplete, or not applicable. Unrouted applicable values block verification and export in OSS and non-OSS flows. Filing snapshots retain registry and formula provenance plus complete foreign-exchange source and date lineage.

### Import, export, and recovery products

Three products are distinct contracts:

- **Flat interchange:** deterministic CSV, JSONL, and XLSX data exports that reopen in independent readers and round-trip where the format permits.
- **Review exchange:** an offline workbook plus machine-readable sidecar; a Google-oriented adapter consumes the same review schema and import plan.
- **Secure recovery archive:** versioned, integrity-checked, encrypted backup restored into a fresh store with equality checks for Ledger records, evidence, notes, changes, provenance, and registry-linked state.

Directory import, provider ingestion, and review-return import use backend plans with dry-run summaries, explicit conflict behavior, and auditable results.

### TUI admission and plan ownership

No Ledger TUI production code is changed before G3 closes. At G4 the implementation reuses the accepted TUI architecture, reconciles any active overlapping Ledger TUI plan, and makes `clitui-ledger` the sole campaign plan for Ledger parity. A component counts only when reachable from the installed application and backed by the canonical use case.

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
