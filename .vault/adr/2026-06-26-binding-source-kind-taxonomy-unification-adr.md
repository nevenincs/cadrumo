---
tags:
  - '#adr'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-26-bindings-architecture-unification-audit]]'
  - '[[2026-06-14-bindings-interface-hardening-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-02-registry-bindings-boundary-audit]]'
  - '[[2026-06-24-retenciones-perceptor-count-adr]]'
---



# `binding-source-kind-taxonomy-unification` adr: `source-kind taxonomy unification: one canonical core BindingSourceKind owning the registry+mesh union` | (**status:** `proposed`)

## Problem Statement

This is phase 2.1 of the bindings-architecture-unification sweep, grounded in the
breadth audit `2026-06-26-bindings-architecture-unification-audit` (finding F1, the
sole CRITICAL with the highest blast radius). The sweep's goal — set as an operator
directive — is one cohesive, centralised, ADR-backed bindings architecture so that
semantic search over the codebase returns one standardised, well-defined surface
rather than a fragmented one. The source-kind closed set is the foundation every
other phase references, so it is sequenced first.

The defect, verified at HEAD (`cbf749f5a`): the closed set of "what KIND of source
feeds a calculation value" is declared **four-plus times** with no single owner.
`src/aeat/core/aggregation.py` holds three enums for it — `AggregationSourceKind`
(4 members), `RowSetGroupingKind` (5 members), and the *declared-canonical*
`BindingSourceKind` (19 members, partially reusing the other two's values) — plus a
`CounterpartSourceKind` `Literal` subset; and a fourth, byte-identical duplicate
lives at `application/operator_surface/_models.py:43` (`SourceKind`, "from the CLI
workflow redesign ADRs"). Worse, `BindingSourceKind` is enforced as a typed enum
**only at the registry-load boundary** (`DataBindingDefinition.source`). The entire
application resolver mesh runs on a **parallel bare-string vocabulary**:
`owned_sources: tuple[str, ...]`, `source_kind: str` on `CalculationSourceDiagnostic`
/ `CalculationSourceProvenance`, `DEFERRED_SOURCE_KINDS: frozenset[str]`
(`_source_mesh.py`), and `_BUCKET_AGGREGATION_OWNED_SOURCES` (hand-listed strings,
`_calculation_actions.py`). The typed token is demoted to `str` the moment it
crosses from registry into mesh, and the two are kept consistent only by
hand-maintained string equality.

The structural consequence is that **the registry typed set and the mesh accepted
set overlap but neither contains the other**: `borrador` and `iva_wallet_decision`
are mesh-owned source strings with no `BindingSourceKind` member; conversely
`purchase_invoice_evidence` and `ledger_transaction` are enum members in neither the
owned nor the deferred mesh set. A typo in a resolver's `owned_sources` string is
caught by no type. This is the `binding-source-kind-single-taxonomy` rule satisfied
on the registry half and silently breached across the mesh half — exactly the
"settled mesh / hardened registry, but nobody owns the union" seam the breadth audit
named as its thesis.

## Considerations

What this ADR owns, and what it must NOT reopen. The breadth audit established that
two altitudes are already decided: the registry-binding-definition altitude
(`2026-06-14-bindings-interface-hardening-adr`, which made `BindingSourceKind` the
canonical *registry* set and derived the per-family frozensets from it) and the
source-resolver-mesh internals (`2026-06-10-calculation-aggregation-taxonomy-adr`).
Each prior ADR explicitly fenced the other's territory out of scope, so neither owns
the **union**. This ADR's entire mandate is that union: it does not reopen the mesh's
collision adjudicator, novel-source gate, or pull==calculate parity, nor the
registry validator contract; it makes the one *source-kind closed set* span both
altitudes as a single typed authority. It is the direct extension of the
`binding-source-kind-single-taxonomy` rule from "the registry" to "the registry AND
the mesh, end to end."

The genuine homonyms are explicitly OUT of scope. Three symbols share the
`SourceKind` suffix but name unrelated concepts and are NOT taxonomy members:
`ModeloReconciliationSourceKind` (`application/modelo/_reconcile.py:35` — a reconcile
transport: sede / justificante / capture / declaration), `BusinessOperationInvoiceSourceKind`
(`application/ledger/_business_operation_invoice.py:53` — invoice direction
issued/received), and `IvaCompensationAuthoritySourceKind`
(`domain/iva_compensation/_reconciliation.py:48` — which authority decided a wallet
amount). These are naming-collision noise for the phase-4 vocabulary pass, not
source-kind duplication. Folding them in would be a category error.

The `RowSetGroupingKind` question (flagged for review). The breadth audit and the
phase-2.1 brief list `RowSetGroupingKind` among the enums to "absorb," but it is NOT
a source token — it is the **row-assembly grouping axis** (`_row_set_assembly.py`),
a downstream concept the core docstring itself distinguishes from the binding source
token. `BindingSourceKind` already carries the corresponding source members
(`WITHHOLDING`, `FOREIGN_ASSET`, `RELATED_PARTY_OPERATION`, `ATRIBUCION_MEMBER`,
`REFUND_OPERATION`), bridged to the grouping axis by `ROW_SET_GROUPING_FOR_BINDING_SOURCE`.
This ADR therefore proposes to KEEP `RowSetGroupingKind` as a distinct axis but
**bind it as a derived projection** of `BindingSourceKind` (the bridge map must be
total and gated), rather than merge two semantically different axes into one enum.
This is a deliberate, flagged divergence from the brief's "absorb"; it is offered to
the report-before-land review as the technically-correct reconciliation.

Coordination with in-flight point-fixes (#6 RET-1, #28). Those campaigns land
point-fixes on the CURRENT taxonomy: `BindingSourceKind.RETENCIONES_AGGREGATION`
(already a member at HEAD) and the withholding distinct-(perceptor,clave) count
source (`2026-06-24-retenciones-perceptor-count-adr`). This ADR treats them as
landing FIRST on the current taxonomy; the unified set ABSORBS them as existing
members (`RETENCIONES_AGGREGATION`, `WITHHOLDING`) with no conflict and no re-do.

Project rules binding this decision: `binding-source-kind-single-taxonomy` (the rule
this extends), `aeat-architecture-boundaries` (a closed value set is a `StrEnum` in
`core/`; production code emits members not raw strings), `aeat-schema-central-config`
(regulatory closed sets live in `core`), `no-legacy-compatibility` (delete the
duplicate enums, do not bridge), `no-dormant-source-resolvers` (the enum↔mesh parity
gate must keep every member routed-or-deferred), `retired-enum-members-need-consumer-reconciliation`
(reconcile every consumer in one accept-or-reject state before any member move), and
`modelo-identifiers-use-core-enum` (the precedent for the behaviour-preserving lift).

## Constraints

No frontier risk: this is a typed-enum consolidation over strict pydantic and
StrEnum surfaces, well inside the model's competence. The real constraints:

- **Execution touches the active casilla-id sweep surface.** The member additions
  land in `core/aggregation.py`; the re-typing lands in the mesh
  (`application/aggregation/_source_mesh.py`) and the enrollment/owned-set in
  `application/modelo/_calculation_actions.py` — both files carry concurrent sweep
  WIP (task #18). Per the swarm-orchestration discipline, EXECUTION sequences AROUND
  the casilla-id sweep exactly as #6 P03 and #28 do: design (this ADR + its plan) is
  authored now; the touching edits land after the sweep commits, or via the
  apply-cached gated drive if entangled. The ADR is design-only and lands nothing.
- **Behaviour-preserving lift.** A `StrEnum` serialises, compares, hashes, and
  JSON-encodes identically to its string value (the `modelo-identifiers-use-core-enum`
  and the original `BindingSourceKind`-lift precedent), so re-typing the mesh's bare
  strings to `BindingSourceKind` members changes static types WITHOUT changing any
  stored or compared string. Registry TOML source tokens are never renamed; the new
  members `borrador` / `iva_wallet_decision` take the VALUE of the existing mesh
  strings. No persisted data shifts; `no-legacy` forbids any migration shim.
- **Wide consumer blast radius, reconciled before any move.** Every mesh resolver's
  `owned_sources`, the two frozensets, the diagnostic/provenance carriers, and the
  `operator_surface.SourceKind` / `AggregationSourceKind` consumers must be migrated
  to the one enum in one coherent accept-or-reject state per
  `retired-enum-members-need-consumer-reconciliation`, with the owning collection
  gate proven green, before either duplicate enum is deleted.
- **Shared factory branch.** Runs under `full-tree-gate-must-distinguish-owner`:
  feature gates are path-scoped; a red full tree is owner-triaged before any step is
  marked complete.

## Implementation

A high-level layering (the plan, authored next under the report-before-land gate,
sequences the steps and their sweep-coordination):

1. **One canonical set.** `BindingSourceKind` (in `aeat.core.aggregation`) becomes
   THE single source-kind authority for every cross-source data-sourcing interface —
   registry binding definitions AND the application resolver mesh. It absorbs the
   union: the two currently mesh-only tokens become first-class members
   (`BORRADOR = "borrador"`, `IVA_WALLET_DECISION = "iva_wallet_decision"`), and the
   two currently enum-only tokens (`PURCHASE_INVOICE_EVIDENCE`, `LEDGER_TRANSACTION`)
   are explicitly accounted for in the mesh sets (enrolled, deferred, or documented
   as reserved-undeclared). After this step the canonical set IS the exact union;
   "neither contains the other" is eliminated by construction.

2. **Retire the duplicates (delete, not bridge).** `AggregationSourceKind` and
   `operator_surface.SourceKind` are removed; their four members already exist as
   `BindingSourceKind` values, so consumers migrate to the one enum.
   `CounterpartSourceKind` is re-expressed as a derived `Literal` subset of
   `BindingSourceKind`. Per `no-legacy`, no alias or compatibility shim is left.

3. **Re-type the mesh end-to-end.** `ModeloSourceResolver.owned_sources` becomes
   `tuple[BindingSourceKind, ...]`; `CalculationSourceDiagnostic.source_kind` and
   `CalculationSourceProvenance.source_kind` become `BindingSourceKind`;
   `DEFERRED_SOURCE_KINDS` and `_BUCKET_AGGREGATION_OWNED_SOURCES` become
   `frozenset[BindingSourceKind]`. Each resolver declares its owned source as an enum
   member, not a string literal. The novel-source gate and the deferred-advisory path
   operate on the typed set.

4. **Bind `RowSetGroupingKind` as a derived axis** (subject to review per the
   Considerations divergence): keep it a distinct concept, but make
   `ROW_SET_GROUPING_FOR_BINDING_SOURCE` total over the detail-record source members
   and gate it, so the grouping axis is a typed projection of the source set, not an
   independently-maintained taxonomy.

5. **One parity gate, two halves.** Extend the existing
   `test_binding_source_kind_taxonomy.py` (today: enum↔registry parity) with an
   enum↔mesh half: every mesh owned/deferred/resolver-owned source is a
   `BindingSourceKind` member, and every member is accounted for as enrolled,
   pre-mesh-handled, deferred, or explicitly reserved-undeclared. This makes the
   "neither set contains the other" regression structurally impossible to recur — the
   gate is the durable enforcement surface this ADR exists to install.

A separate `{reference}` document will capture the concrete current-state anchors
(every enum definition, every bare-string site, every resolver `owned_sources`) that
the plan's steps edit.

## Rationale

The decision is the project's own `binding-source-kind-single-taxonomy` rule applied
to the half of the surface that silently breached it. The registry half already
proved the pattern works (one core `StrEnum`, derived frozensets, a parity gate); the
only honest move is to extend the same discipline across the mesh rather than tolerate
a parallel bare-string vocabulary that no type checks. Making `BindingSourceKind` own
the union — not a new enum — preserves the hardened registry decision rather than
re-deciding it, and the behaviour-preserving StrEnum lift means the consolidation is a
type-level change with zero data or comparison-semantics shift, the same risk profile
as the modelo-enum hardening that already shipped. Deleting the duplicates rather than
aliasing them is mandated by `no-legacy`. Keeping `RowSetGroupingKind` distinct-but-derived
respects a real semantic boundary (source token vs grouping axis) the core docstring
already documents, while still ending its independent maintenance. The two-half parity
gate is what converts this from a one-time cleanup into a durable invariant, which is
the only thing that makes the RAG-cohesion goal stick: a future drift fails CI instead
of re-fragmenting the surface.

## Consequences

Gains: one typed home for "what kind of source feeds this value," spanning registry
and mesh; a typo in a resolver's owned source becomes a type error; the union gaps
(`borrador`, `iva_wallet_decision`, `purchase_invoice_evidence`, `ledger_transaction`)
close into one accounted set; two duplicate enums and one stringly-typed mesh
vocabulary disappear; and the two-half parity gate makes re-fragmentation a CI
failure. This is the foundation the next three phases (one resolver contract →
fold-in unification → vocabulary/CLI cohesion) build on, and the first concrete step
toward the operator's goal of a RAG-cohesive, centrally-defined bindings architecture.

Difficulties, framed honestly: the consumer blast radius is wide (every mesh resolver,
both frozensets, the diagnostic/provenance carriers, the `operator_surface` and
counterpart consumers) and must be reconciled in one accept-or-reject state before any
deletion, per the retired-enum-reconciliation rule. Execution races the casilla-id
sweep on two shared files and must sequence around it (design now, land after) exactly
like #6/#28 — this ADR deliberately lands no code. The `RowSetGroupingKind`
keep-but-derive choice diverges from the brief's "absorb" and is surfaced for the
report-before-land review rather than decided unilaterally. And surfacing the
currently-unbacked members (`purchase_invoice_evidence`, `ledger_transaction`) may
force an explicit enrolled/deferred/reserved disposition for each — which is the
intended honesty, not new scope.

Explicitly out of scope (fenced, tracked elsewhere): the resolver-contract-shape
unification (phase 2.2), the relations-vs-previous_filing fold-in duplication (phase
2.3), the naming homonyms and CLI verb fork (phase 2.4), and the three genuine
`SourceKind` homonyms named above. None of those are reopened here.

## Codification candidates

- **Rule slug:** `binding-source-kind-single-taxonomy` (EXTEND the existing rule).
  **Rule:** The canonical `BindingSourceKind` core `StrEnum` is the single
  source-kind authority across BOTH the registry binding definitions AND the
  application resolver mesh; the mesh MUST carry `BindingSourceKind` members, never a
  parallel bare-string source vocabulary, and an enum↔mesh parity gate keeps every
  member routed, deferred, or explicitly reserved. (Extension authored at phase-2.1
  review/codify, not now — the lesson must hold through execution first, per
  `vaultspec-codify`.)


