---
tags:
  - '#plan'
  - '#binding-source-kind-taxonomy-unification'
date: '2026-06-26'
modified: '2026-06-26'
tier: L2
related:
  - '[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- RETIRED: S16 -->

# `binding-source-kind-taxonomy-unification` plan

### Phase `P01` - Foundations: members and extended parity gate

Add the two mesh-only source tokens as BindingSourceKind members and extend the parity gate to the enum-to-mesh half, as one atomic behaviour-preserving landing.


Phase 2.1 of the central bindings architecture: make one core `BindingSourceKind`
the single typed source-kind authority across registry and mesh.

- [x] `P01.S01` - Add BORRADOR and IVA_WALLET_DECISION members to BindingSourceKind; `src/aeat/core/aggregation.py`.
- [x] `P01.S02` - Extend the source-kind parity gate with an enum-to-mesh half and decide the purchase_invoice_evidence and ledger_transaction disposition; `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`.

### Phase `P02` - Re-type the mesh off bare strings

Replace the bare-string source vocabulary across the mesh carriers, sets, and every resolver owned_sources with the BindingSourceKind enum.

- [x] `P02.S03` - Re-type owned_sources and both source_kind carriers to BindingSourceKind; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `P02.S04` - Re-type DEFERRED_SOURCE_KINDS and _BUCKET_AGGREGATION_OWNED_SOURCES to frozenset of BindingSourceKind; `src/aeat/application/modelo/_calculation_actions.py`.
- [x] `P02.S05` - Re-type the five ledger and retenciones resolver owned_sources to enum members (sequenced after #6 P03 + #28 land on this mesh surface); `src/aeat/application/aggregation/_modelo_bindings.py`.
- [x] `P02.S06` - Re-type the OSS/IOSS ledger resolver owned_sources to an enum member; `src/aeat/application/aggregation/_oss_ioss.py`.
- [x] `P02.S07` - Re-type the profile resolver owned_sources to an enum member; `src/aeat/application/aggregation/_source_profile.py`.
- [x] `P02.S08` - Re-type the relation-prefill resolver owned_sources to an enum member; `src/aeat/application/calculations/_relation_prefill.py`.
- [x] `P02.S09` - Re-type the previous-filing resolver owned_sources to an enum member; `src/aeat/application/calculations/_multi_year.py`.
- [x] `P02.S10` - Re-type the iva-wallet-decision resolver owned_sources to an enum member; `src/aeat/application/calculations/_iva_wallet_reconciliation.py`.
- [x] `P02.S11` - Re-type the borrador resolver owned_sources to an enum member; `src/aeat/application/modelo/_borrador_binding.py`.
- [x] `P02.S12` - Re-type the invoice-catalogue resolver owned_sources to enum members; `src/aeat/application/invoices/_source_resolver.py`.

### Phase `P03` - Delete the duplicate enums and reconcile consumers

Re-express CounterpartSourceKind as a derived subset, migrate every consumer, then delete AggregationSourceKind and operator_surface.SourceKind under the retired-enum-reconciliation discipline.

- [x] `P03.S13` - Re-express CounterpartSourceKind, COUNTERPART_SOURCE_KINDS, and counterpart_source_kind as a derived subset of BindingSourceKind; `src/aeat/core/aggregation.py`.
- [x] `P03.S14` - Migrate the per-modelo aggregation service and registry-provider consumers off AggregationSourceKind and delete it; `src/aeat/application/aggregation/_service.py`.
- [x] `P03.S15` - Migrate operator_surface SourceKind consumers to BindingSourceKind and delete the duplicate; `src/aeat/application/operator_surface/_models.py`.

### Phase `P04` - Prove the unified gate

Prove both parity halves and the full bindings surface green; RowSetGroupingKind is scoped out and left untouched.

- [x] `P04.S17` - Run the full bindings test surface and both parity halves and owner-triage the full tree; `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`.

## Description

Implements Axis 1 of the central bindings architecture ADR via the phase-2.1
source-kind taxonomy-unification ADR, against the current-state anchors in the
phase-2.1 reference. The work makes `BindingSourceKind` (in `core/aggregation.py`)
THE single source-kind closed set across BOTH the registry binding definitions AND
the application resolver mesh: add the two mesh-only tokens as members
(`BORRADOR`, `IVA_WALLET_DECISION`), give the two enum-only tokens
(`PURCHASE_INVOICE_EVIDENCE`, `LEDGER_TRANSACTION`) an explicit
enrolled/deferred/reserved disposition, re-type the mesh off bare strings, delete the
duplicate `AggregationSourceKind` and `operator_surface.SourceKind` (with member +
consumer reconciliation as the explicit PRECONDITION of each deletion, atomic), scope
`RowSetGroupingKind` OUT (it stays its own enum, a different axis, with NO bridge),
and extend the parity gate with an enum-to-mesh half so "neither set contains the
other" cannot recur. The lift is behaviour-preserving: a `StrEnum` serialises and
compares identically to its value, so re-typing changes static types without changing
any stored or compared string; no registry TOML token is renamed.

Deletion-reconciliation precondition (P03, per `retired-enum-members-need-consumer-reconciliation`).
Before either duplicate enum is deleted, ALL its members and EVERY consumer are
reconciled into `BindingSourceKind` in one atomic relocation: confirm no orphan
member is lost, every consumer is migrated, the owning collection / parity gate is
proven green, and only then is the enum removed in the SAME commit. The reconciliation
is the precondition of the deletion, never a separate later step.

Execution discipline. This plan rides the report-before-land gate: the coordinator
reviews this plan before any Step lands, and each landing Step is reported before
commit. SEQUENCING (updated): the casilla-id sweep that earlier touched these files is
now committed (autonomo-130 safeguard; registry builds, suite green), so "sequence
around the sweep" is moot. The live constraint is that phase-2.1 re-types the mesh
source surface (`_source_mesh.py`, the owned/deferred sets in `_calculation_actions.py`,
and the resolver `owned_sources`) that the #6 P03 + #28 retenciones re-stamp is editing
RIGHT NOW. So phase-2.1 EXECUTION sequences AFTER #6 P03 + #28 land, building on top of
the landed re-stamps and absorbing `RETENCIONES_AGGREGATION` + the withholding count
source as existing members. Each Step still re-reads HEAD and `git diff` immediately
before editing and aborts on non-authored WIP, never overwriting peer work. A critical
ordering fact: adding the two members (S01) before extending the parity gate (S02) REDS
the existing enum-to-registry parity gate (which rejects an enum member no registry
binding declares), so S01 and S02 land together as one atomic, behaviour-preserving
change.

## Steps







## Parallelization

The whole phase EXECUTION is gated to start AFTER #6 P03 + #28 land (they re-stamp
the same mesh source surface). Within that: phases are hard-ordered - P01
(foundations) before P02 (re-type the mesh) before P03 (delete the duplicates) before
P04 (final gate). P01's two Steps are one atomic landing (members + gate extension,
per the ordering fact above). Within P02 the per-file re-typing Steps are independent
of each other and may land in any order once P01 is in. P03 must follow P02 (the
consumers must read the unified enum before the duplicates are deleted), and each
deletion Step carries its member + consumer reconciliation as an atomic precondition
per `retired-enum-members-need-consumer-reconciliation`. P04 (final gate) is last.

## Verification

- The extended `test_binding_source_kind_taxonomy.py` is green on BOTH halves:
  enum-to-registry parity AND the new enum-to-mesh parity (every owned / deferred /
  resolver-owned source is a `BindingSourceKind` member; every member is enrolled,
  pre-mesh-handled, deferred, or explicitly reserved-undeclared).
- `AggregationSourceKind` and `operator_surface.SourceKind` no longer exist in the
  tree (`rg` returns zero definitions); `CounterpartSourceKind` is a derived subset
  of `BindingSourceKind`.
- The mesh carriers (`owned_sources`, both `source_kind` fields,
  `DEFERRED_SOURCE_KINDS`, `_BUCKET_AGGREGATION_OWNED_SOURCES`) are typed
  `BindingSourceKind`, not bare `str`.
- `RowSetGroupingKind` is untouched: it remains its own independent enum (a distinct
  row-assembly grouping axis), is NOT a member of the source-kind union, and NO
  speculative source-to-grouping bridge map was added.
- The full bindings test surface (registry + aggregation + calculations + filing +
  modelo test dirs) passes; `uv run --no-sync pytest --collect-only -q src/aeat` is
  clean; the full-tree gate is owner-triaged.
- Behaviour preservation proven: no stored or compared source-token string changed
  (the StrEnum lift), verified by the green calculation/roundtrip suites.

The plan is complete when every Step is closed and the coordinator has signed off the
landed change at the report-before-land gate.
