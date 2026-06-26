---
tags:
  - '#adr'
  - '#bindings-interface-hardening'
date: '2026-06-14'
modified: '2026-06-15'
related:
  - "[[2026-06-14-bindings-interface-hardening-research]]"
  - "[[2026-05-20-calculation-source-connectivity-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
---



# `bindings-interface-hardening` adr: `bindings interface hardening: one validation contract, provenance parity, semantic disambiguation` | (**status:** `accepted`)

## Problem Statement

The "bindings interface" — how a registry-declared calculation input is defined,
validated, resolved, carried onto a filing draft, exported, and shown to an
operator — emerged organically across many campaigns and was never given a single
centralised review. The swarm code-discovery research found that the interface has
two altitudes in very different states. The **resolver-mesh altitude** (the
`ModeloSourceResolver` port, `CalculationSourceMesh`, enrollment and novel-source
gates, pull==calculate parity) is already decided across the calculation-source
connectivity ADR and the aggregation-taxonomy ADR, wired live, and rule-backed.
That altitude is settled and this ADR does not reopen it.

The **definition / validation / boundary / naming altitude** is the genuine,
uncodified drift this ADR addresses. The research anchored six finding clusters,
each to a confirmed `file:line`:

- **A — validation is non-uniform within one layer.** Three incompatible validator
  conventions coexist (public `validate_* -> None` that raises; a withholding
  `-> list[str]` that accumulates; and counterpart + the four detail-record
  families with no public validator at all), and op/fact invariants run at
  registry-**build** for counterpart/withholding but only at **resolve** time for
  the detail-record families and `previous_filing`. A malformed binding for those
  families ships clean through snapshot build and fails only on a taxpayer's
  calculation.
- **B — the `aggregation`/`op` axis and the source-kind taxonomy are untyped and
  half-adopted.** `aggregation` is a free-form mapping; `op` is re-parsed at ~10
  sites with divergent silent defaults (`"sum"` vs `"rows"`). `RowSetGroupingKind`
  is enum-keyed for two sources and free-string for three (the strings do not even
  match the enum values); `LEDGER_BINDING_SOURCE_KINDS` lists two of four ledger
  kinds; the `typed_enum` schema field is dead.
- **C — silent-zero is structurally possible everywhere except IVA.** Only IVA has
  a fail-closed unsupported-observation screen; OSS, renta, withholding,
  counterpart, and the detail-record families can resolve to a silent
  `Decimal("0")`.
- **D — provenance is dropped at the operator boundary.** Binding values are
  flattened to a hardcoded `source="registry binding input"` with no
  `legal_refs`/`source_refs` on the `ModeloBindingValue` carrier or the CLI
  list/preview payloads, while casillas carry full provenance — a silent breach of
  the calculation-grounding rule the casilla half upholds. The `bindings list`
  payload is an untyped `dict` bag; `--modelo` lacks a `Choice` refusal; the
  `--binding` numeric-vs-enum split is a `try Decimal/except` heuristic.
- **E — "binding" is one strong core surrounded by homonyms.** Two unrelated
  `_profile_binding.py` files, a `decimal_from_string` parser misfiled under a
  "binding value" name, and a `legal_basis_binding` rate→BOE verification concept
  all overload the word.
- **F — structural debt is un-codified.** The registry binding module is a
  ~3,040-line, ~15-family monolith; two prior boundary audits' codify candidates
  were never promoted to rules.

## Considerations

The operator directive frames this as a security and code-correctness campaign:
codify, verify, audit, harden, improve, and centralise. The user selected the
comprehensive scope (all of clusters A–F in one ADR), inclusion of the encrypted
`ModeloBindingValue` provenance change now (coordinated with the in-flight
storage-backend-security-review campaign), and performing the homonym renames in
addition to codifying a naming rule.

Project rules that bind this decision: `aeat-calculation-grounding` (provenance
through every boundary), `no-silent-under-declaration` (an unrouted/zero value must
surface), `aeat-architecture-boundaries` (typed closed-value enums in `core/`; CLI
`Choice` hints; atomic explicit-path relocation commits; no shims),
`no-dormant-source-resolvers` and `calculation-source-canonical-mechanism` (the
settled mesh side this ADR must not contradict), `cli-notices-are-the-only-
diagnostic-channel`, `aeat-roundtrip-discipline` (any persistence-boundary change
needs strict roundtrip + anti-tautology tests), `no-legacy-compatibility` (delete
old shapes, never bridge), and `aeat-schema-central-config` (regulatory closed sets
live in `core`/registry).

## Constraints

No frontier-technology risk; this is a refactor and hardening of existing strict
pydantic surfaces, well inside the model's competence. Real constraints:

- The `ModeloBindingValue` change (D below) touches the **encrypted** filing-draft
  persistence boundary; the storage-backend-security-review campaign is active in
  the same worktree (~73% complete). Every edit to a shared persistence file MUST
  re-read HEAD and `git diff -- <file>` immediately before editing, and abort on
  non-authored WIP, per the swarm-orchestration discipline.
- The source-kind taxonomy unification (B) touches a closed set consumed by the
  registry loader, the mesh, and the retired-`AggregationSourceKind.INVOICE`
  reconciliation surface; `retired-enum-members-need-consumer-reconciliation`
  applies — every consumer reconciled in one accept-or-reject state before any
  member move, with the owning collection gate proven green.
- The build-time validator move (A) must not weaken any resolve-time check; the
  resolve-time helpers remain as defence-in-depth, with the build gate made
  authoritative. The registry is the authority (`aeat-registry-authority-flow`);
  validation stays in the domain layer, not the loader.
- The campaign runs on the shared `chore/eliminate-shims` factory branch under the
  full-tree-gate-owner-distinction rule: feature gates are path-scoped; a red full
  tree is triaged for owner before any step is marked complete.

## Implementation

The work is organised as one tiered plan, sequenced by risk. High-level layering:

**1 — One binding validation contract (cluster A).** Collapse the three validator
conventions onto a single per-source `validate(binding) -> list[str]` accumulating
signature, registered in one dispatch table alongside the selector model, and run
by the registry-build section validator for **every** family. The four
detail-record families and `previous_filing` get their op/fact invariants lifted to
build time (matching the counterpart/withholding precedent), routed through
`selector_as_dict` for normalisation consistency, and preserving the underlying
pydantic field error in the diagnostic. Resolve-time helpers remain as
defence-in-depth re-checks. Near-verbatim invoice/counterpart duplication is
collapsed to one shared implementation parameterised by source kind.

**2 — Typed aggregation and one source-kind taxonomy (cluster B).** Introduce a
typed `BindingAggregation` model with a closed `op` enum declared in `core`,
replacing the free-form mapping and the ~10 ad-hoc re-parses with one accessor and
one declared per-family default. Consolidate the binding `source` kinds onto a
single canonical closed enum in `core`, with the per-family frozensets **derived**
from it rather than hand-maintained; realign the `related_party` / `atribucion` /
`refund` enum-vs-string mismatch; complete `LEDGER_BINDING_SOURCE_KINDS`; and either
wire or delete the dead `typed_enum` field (delete unless a consumer is found).

**3 — Fail-closed parity (cluster C).** Generalise the IVA unsupported-observation
screen into a per-family "unrouted/unsupported observation" diagnostic so every
aggregation resolver surfaces an advisory instead of a silent `Decimal("0")`, per
`no-silent-under-declaration`. Unify the three copies of the ADR-R2 revision-carry
gate onto one path, and emit a diagnostic for an unresolved non-formula relation.

**4 — Operator-boundary provenance parity (cluster D).** Carry `legal_refs` /
`source_refs` and a real typed source kind on `ModeloBindingValue`, populated by the
filing builder from the binding definition (dropping the hardcoded free-text
string), with strict save→load→equality roundtrip and anti-tautology proof tests
on the encrypted boundary. Expose the grounding on the CLI `BindingRowPayload` /
`BindingPreviewRowPayload`, convert `bindings list` from the `dict[str, object]`
bag to the typed payload, make `bindings list --modelo` a registry-derived `Choice`
with an accepted-codes refusal, and replace the `--binding` `try Decimal/except`
classification with a registry-data-type-driven coercion.

**5 — Semantic disambiguation (cluster E).** Reserve "binding" for the
registry-data-input concept. Rename the Google OAuth `_profile_binding.py` to an
active-profile resolver name, reclassify `decimal_from_string` out of the
"binding value" filename, and rename the `legal_basis_binding` test concept — each
as an atomic explicit-path relocation commit with the docs-scaffold regen. Give the
three source-resolver result types one role-named contract or document the role.

**6 — Codification (cluster F).** Promote the two never-promoted structural
candidates and author the new bindings-interface rules capturing the contracts
above, so the disciplines bind future agents.

A separate `{reference}` document captures the concrete current-state code anchors
(the validator dispatch table, the selector models, the carrier schema, the CLI
payloads) that the plan's steps edit.

## Rationale

The research established that re-deciding the resolver mesh would duplicate
settled, gate-backed decisions, so the ADR is deliberately fenced to the
definition/boundary/naming altitude where no prior decision exists. Each decision
is the project's own existing rule applied to the binding half of a surface whose
casilla half already complies: provenance parity is `aeat-calculation-grounding`;
fail-closed parity is `no-silent-under-declaration`; the typed enums and `Choice`
hints are `aeat-architecture-boundaries`; the single validator contract removes the
build-vs-resolve asymmetry the counterpart/withholding families were already
hardened against ("selector-drift F3"); and the homonym renames remove a concrete
grep/refactor trap. The comprehensive scope was chosen because the clusters are
interdependent — the typed `op` enum (2) underpins the unified validator (1), and
the source-kind taxonomy (2) underpins fail-closed parity (3) — so splitting them
would create cross-ADR coupling.

## Consequences

Gains: one place to learn how a binding is defined and validated; build-time
rejection of malformed bindings for every family, not just two; no silent-zero
under-declaration off the IVA path; operator-visible legal grounding for bound
values at parity with casillas; a typed, completable CLI surface; and a naming
discipline that stops the homonym drift. The structural-extraction rules turn two
stale audit candidates into enforced discipline.

Difficulties and pitfalls, framed honestly: the `ModeloBindingValue` change races a
concurrent encrypted-storage campaign and demands disciplined HEAD-re-reads and
roundtrip tests; the source-kind enum unification has a wide consumer blast radius
and must reconcile every consumer before any member move; the build-time validator
move risks surfacing latent malformed registry bindings that previously only failed
at calculate time, which is the intended behaviour but will need registry-TOML
fixes in the same campaign; and the renames touch import sites across layers and
must land as atomic explicit-path commits with docs-scaffold regen to avoid orphan
stubs. None of these reopen the settled mesh altitude.

Explicitly out of scope (fenced, not abandoned): the resolver-mesh interface; the
six advisory-deferred resolver-less source kinds; the `MultiYearResolver` orphan
adjudication; the `PurchaseInvoiceEvidenceSourceResolver` data-shape blocker; and
`payable_invoice` declared by no registry binding. Each remains tracked in its
originating audit/plan.

## Codification candidates

- **Rule slug:** `binding-validation-single-contract`.
  **Rule:** Every registry binding `source` family MUST expose one
  `validate(binding) -> list[str]` validator registered in the single binding
  dispatch table and run at registry-build for all families; op/fact invariants are
  enforced at build time, never resolve-time-only.
- **Rule slug:** `binding-aggregation-is-typed`.
  **Rule:** A binding's aggregation MUST be a typed model with a closed `op` enum
  declared in `core`; no call site may re-parse `aggregation.get("op")` from a
  free-form mapping or pick a local default.
- **Rule slug:** `binding-source-kind-single-taxonomy`.
  **Rule:** The binding `source` closed set MUST be one canonical `core` enum, with
  every per-family source-kind collection derived from it, never hand-maintained or
  string-literal-duplicated.
- **Rule slug:** `binding-values-carry-provenance`.
  **Rule:** Every persisted and operator-facing binding value MUST carry its
  `legal_refs`/`source_refs` and a typed source kind at parity with casilla
  provenance; a hardcoded free-text source string is forbidden.
- **Rule slug:** `binding-names-reserved-for-registry-input`.
  **Rule:** The term "binding" in module names, types, and CLI surfaces is reserved
  for the registry-data-input concept; account-scoping, parsing helpers, and
  verification gates MUST NOT be named "binding".
- **Rule slug:** `registry-resolver-family-extraction` (promotion of the
  never-promoted `2026-06-02-registry-bindings-boundary-audit` candidate).
  **Rule:** Registry binding/resolver families are extracted into per-family
  modules behind the package `__all__` facade; new families follow the established
  module shape rather than growing the monolith.

## Status

Accepted and FOUNDATIONAL — not reopened. This ADR hardened the REGISTRY-binding
definition altitude (validation contract, typed `BindingAggregation`/op,
`BindingSourceKind`, provenance parity). The bindings-architecture-unification sweep
extends it in two respects, recorded in the canonical PHASE ADRs (not a central apex
doc): the phase-2.1 `binding-source-kind-taxonomy-unification` ADR widens this ADR's
`BindingSourceKind` from registry-only to the registry+mesh union; the future
phase-2.3 (fold-in/relation) ADR applies this ADR's typed-aggregation discipline to
relations (which it did not cover). Those phase ADRs are the canonical direction; this
ADR's decisions remain in force.
