---
tags:
  - '#audit'
  - '#bindings-architecture-unification'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - '[[2026-06-14-bindings-interface-hardening-adr]]'
  - '[[2026-06-15-bindings-interface-hardening-audit]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-06-02-registry-bindings-boundary-audit]]'
---



# `bindings-architecture-unification` audit: `bindings architecture breadth audit: cross-source data-sourcing taxonomy and contract fragmentation`

## Scope

Phase-1 breadth audit opening a multi-day, multi-turn "bindings sweep" whose goal
is to standardise the data-sourcing surface into one cohesive, centralised,
ADR-backed architecture uniformly adapted to the backend schema. The operator
defines "bindings" BROADLY — not the `--binding` CLI flag, but **any and every
interface where a calculation sources data cross-modelo or from another storage
vault / source**. This audit discovers the breadth of the disjointedness; it
prescribes no code change and lands no fix.

Method: a six-axis RAG-first discovery swarm (registry-binding core; source
resolver mesh; relations subsystem; cross-period carry / previous_filing / IVA
wallet; non-registry / storage-vault sourcing + application aggregation layer;
CLI + terminology census), each agent grounding every claim to a `file:line` and
flagging confidence. The highest-value, most-surprising claims were then
re-confirmed by the coordinator against HEAD (branch `chore/eliminate-shims`,
HEAD `cbf749f5a`) before being recorded here as fact. Every remaining `file:line`
below is swarm-sourced inventory to re-verify at the point of any future action,
per `aeat-swarm-audit-cadence` (agent-as-discovery, coordinator-as-confirmation).

What is NOT re-litigated. Two altitudes are already decided and rule-backed, and
this audit does not reopen them as such; it audits only their **seams** with the
rest of the surface:

- The **registry-data-input binding definition** altitude (validation contract,
  typed `BindingAggregation`/op, `BindingSourceKind` taxonomy, provenance parity,
  per-family module extraction, homonym renames) was hardened by the
  `2026-06-14-bindings-interface-hardening-adr` campaign and is internally sound
  at HEAD.
- The **source-resolver mesh** internals (one `ModeloSourceResolver` port, one
  `merge_source_resolutions` collision adjudicator, novel-source gate, deferred
  advisories, pull==calculate parity) were settled by
  `2026-06-10-calculation-aggregation-taxonomy-adr` and the source-connectivity
  ADR; the mesh is cohesive *within itself*.

The thesis of this audit: each altitude is cohesive **internally**, but the
project has never reviewed the **union** — and the disjointedness lives almost
entirely in the seams *between* altitudes and in the parallel sourcing pipelines
that grew up *outside* both. The two prior ADRs each explicitly fenced the other's
territory out of scope, so no document owns the whole.

## Findings

Severity reflects architectural blast radius (how many call sites and how much
operator-facing vocabulary a fix touches), NOT runtime correctness — the surface
largely *works*; it is *fragmented*. No live under-declaration defect is claimed
here (those are tracked under their own campaigns).

### CRITICAL

#### F1 — The source-kind closed set is fractured across four+ typed enums plus a parallel bare-string vocabulary; the registry is typed, the mesh is stringly-typed, and neither set contains the other

`src/aeat/core/aggregation.py` declares **three** source-kind enums describing one
problem at different altitudes: `AggregationSourceKind` (4 members, lines 85-102),
`RowSetGroupingKind` (5 members, lines 151-179), and the declared-canonical
`BindingSourceKind` (19 members, lines 182-250) which *partially reuses* the other
two's values (lines 239-247) and independently declares the rest — plus a
`CounterpartSourceKind` `Literal` subset (line 105) and a fourth duplicate,
`operator_surface.SourceKind` (`operator_surface/_models.py:43`), byte-identical to
the four `AggregationSourceKind` members. Two bridge maps
(`ROW_SET_GROUPING_FOR_BINDING_SOURCE`, the counterpart subset) exist solely to
reconcile them.

The deeper split: `BindingSourceKind` is enforced as a typed enum ONLY at the
registry-load boundary (`DataBindingDefinition.source`, parity-gated by
`test_binding_source_kind_taxonomy.py`). The **entire application mesh runs on bare
strings** — `owned_sources: tuple[str, ...]` (`_source_mesh.py:127`),
`source_kind: str` on both `CalculationSourceDiagnostic` and
`CalculationSourceProvenance` (`_source_mesh.py:103,116`), `DEFERRED_SOURCE_KINDS:
frozenset[str]` (`_source_mesh.py:66`), `_BUCKET_AGGREGATION_OWNED_SOURCES`
(hand-listed strings, `_calculation_actions.py:146-163`). Every resolver hard-codes
its owned source as a string literal. The typed token therefore travels
`BindingSourceKind` → bare `str` → `str` → `str` along the calculate → diagnostic →
CLI path, kept in sync only by hand-maintained string equality. **The mesh accepted
set and the registry typed set overlap but neither contains the other**: `borrador`
and `iva_wallet_decision` are mesh-owned strings with NO `BindingSourceKind` member;
`purchase_invoice_evidence` and `ledger_transaction` are enum members in NEITHER the
owned nor deferred mesh set (a binding declaring them would trip the novel-source
gate). Confidence: HIGH (re-confirmed against HEAD by the coordinator).

#### F2 — At least three unreconciled sourcing-contract shapes, surfacing four-to-six overlapping result envelopes for "a resolved source value"

A non-registry source value is produced through one of three structurally distinct
contracts that are NOT unified:

- **(A) Source mesh** — `ModeloSourceResolver` Protocol (`_source_mesh.py:222`) →
  `CalculationSourceResolution` (10 typed channels, `_source_mesh.py:121`). The live
  calculate path. ~12 concrete resolvers across four packages.
- **(B) Pre-mesh binding-source resolution** — `BindingSourceResolution` Protocol
  (`modelo/_binding_resolution.py:39`) → `ProfileSourcedBindingResult` /
  `Modelo100BorradorBindingResult`. Profile and borrador run OUTSIDE the mesh, with
  their own precedence ladder. A profile value is shape-converted B→A→B on every
  calculation (`_source_profile.py:74` wraps into a `CalculationSourceResolution`;
  `_binding_resolution.py:221` immediately unwraps it back) — pure friction.
- **(C) Per-modelo aggregation service** — `aggregate_per_modelo(command)`
  (`aggregation/_service.py:334`) → `PerModeloAggregationResult` wrapping
  `Retenciones/Counterpart/ForeignAssets Aggregation`, keyed off the *separate*
  `AggregationSourceKind` enum. The CLI `aggregate` verb path. **Counterpart
  (347/349) and foreign-assets (720) are reachable ONLY here — they have no mesh
  resolver and never enter the live calculate path.** Retenciones is reachable
  through BOTH A and C with two different result types.

`BindingSourceResolution` is an *aspirational* unification that already documents
its own exception (the IVA wallet "is intentionally not a member"), so it does not
actually cover the surface. Beyond the three live shapes, the swarm found vestigial
or near-dead envelopes for the same role: `CalculationBindingResolution` (a fourth
"Resolution" aggregating the others), `CasillaAggregation`/`CasillaProvenance`
(advertised canonical in the package `__init__` docstring but bypassed by both live
paths), `PerModeloRegistryBindingResolution` (M349-only bridge,
`_registry_provider.py:51`), and `ModeloLedgerBindingAggregation` (no live consumer,
`_modelo_bindings.py:79`). Confidence: HIGH on the three live shapes; MEDIUM on the
"vestigial" classification of the latter three (single-grep, not exhaustively traced).

#### F3 — At least six parallel mechanisms answer one question ("source a value from a prior period / year / other filing"); relations and previous_filing bindings are two full implementations of the same fold-in

The time-axis / cross-filing sourcing surface is the most fragmented region. The
swarm enumerated six distinct mechanisms: (A) direct `previous_filing` binding
(`_bindings_previous_filing.py`, selector-driven, with the only member-fan-in axis
`per_grupo_member`); (B) `relation` cross-modelo/prior-period fold-in
(`_relations.py` + `_relation_prefill.py`); (C) the `relation_prefill`
materialisation-slot binding fed by a relation; (D) the cross-period clean-state
evidence gate (`_cross_period_clean_state.py`, 1522 lines, re-deriving requirements
from BOTH A and B origins via `CrossPeriodDependencyOrigin`); (E) the IVA wallet
compensación decision — a wholly bespoke parallel path spanning a domain package
(`domain/iva_compensation/`) and five application modules, with its own source kind
`iva_wallet_decision`, a pre-mesh (not in-mesh) resolver, AND a back-door value
injection through the previous_filing observation-merge (`_binding_prefill.py:314`);
(F) `MultiYearResolver` (`_multi_year.py:400`) — a CONFIRMED ORPHAN (its own
docstring at line 410: "This class has no live production caller in the current
calculate path"), with a richer year-set API than the live path exposes, intended
for M200 BIN carry and M303 prorrata but never wired.

Relations and previous_filing bindings are **two parallel implementations of "fold
one modelo's filed value into another"**: separate requirement records
(`RegistryRelationSourceRequirement` vs `RegistryModeloObservationRequirement`,
near-identical fields), THREE near-identical copies of the observation-folding loop
(`_relations.py:299`, `_relation_prefill.py:450`, `_bindings_previous_filing.py:146`),
duplicated period-offset math, the `target_binding` field by which a *relation*
points into the *binding* namespace, and two carve-out frozensets bridging the M303
compensación overlap. The good news, verified: all six mechanisms read ONE
observation store and route through ONE unified `revision_carry_outcome` R2 gate
(`_revision_carry_gate.py` — the three-copy merge is genuinely complete). The
fragmentation is in the value layer, not the carry-confirmation layer. Confidence:
HIGH (orphan + carry-gate unification re-confirmed against HEAD).

### HIGH

#### F4 — Relation aggregation never received the typed-op treatment that bindings did — an enforced rule on one half of the surface, an open smell on the other

`RelationDefinition.aggregation` is a free-form `Mapping[str, str | int |
DecimalValue | bool] | None` (`_schema_surfaces.py:489`), and its op is re-parsed
inline as `str((relation.aggregation or {}).get("op", ...))` at three sites
(`_relations.py:103,167`; `_relation_prefill.py:605`) with a hand-rolled
`{copy, sum}` check (`_validate_relation_sources.py:85`). This is **exactly** the
untyped-mapping op-reparse smell that the `binding-aggregation-is-typed` rule
forbids for bindings (which now use the typed `BindingAggregation` +
`BindingAggregationOp` enum). The discipline was applied to the binding half and
never to the relation half, even though both answer the identical "how do I fold
these values" question. Confidence: HIGH (re-confirmed against HEAD).

#### F5 — A source's enrollment state is tracked in four disconnected places, with no single registry of "where does source X resolve," and live capacity is silently orphaned

A source can be enrolled-in-mesh, pre-mesh-handled, deferred, or service-only — four
states recorded in four structures: the `merge_source_resolutions` tuple
(`_calculation_actions.py:561-617`), `_pre_mesh_handled` (`:624`),
`DEFERRED_SOURCE_KINDS` (`_source_mesh.py:66`), and the `PerModeloAggregationProvider`
enum (`_service.py`). No test asserts `_BUCKET_AGGREGATION_OWNED_SOURCES` equals the
union of enrolled resolver `owned_sources` (the parity gate covers only enum↔registry,
not frozenset↔enrollment), so the hand-maintained owned set can silently drift.
Consequences observed: counterpart/foreign-assets orphaned from the live mesh (F2);
`MultiYearResolver` orphaned (F3); and several `BindingSourceKind` members
(`ledger_oss_aggregation`, `retenciones_aggregation`, `payable_invoice`,
`purchase_invoice_evidence`, `ledger_transaction`) have ZERO declared registry TOML
bindings at HEAD (dormant-capacity surface to reconcile against
`no-dormant-source-resolvers`). Confidence: HIGH on enrollment-state count; MEDIUM on
the "no frozenset↔enrollment parity gate" (the swarm did not exhaustively grep tests).

#### F6 — Pervasive naming homonyms and synonyms make the surface grep-hostile and the vocabulary non-load-bearing

One-name-many-concepts: `resolve`/`resolve_*` spans six unrelated meanings
(mesh value resolution, snapshot lookup, id-prefix resolution, workflow-target
resolution, profile/capability, revision selection); `SourceKind` names four
unrelated closed sets; the `source` field is typed `BindingSourceKind` in one carrier
and bare `str` in the diagnostic/provenance carriers; **`Observation` names 30+ types**
across calc-runtime, ledger-aggregation, live-capture and AEAT-oracle domains with no
discriminating prefix; **`BindingRow` names four unrelated row types** (`BindingRowPayload`,
`BindingPreviewRowPayload`, `ModeloBindingRow`, `_BindingRow`); `prefill` spans three
concepts (`relation_prefill`, `_binding_prefill`, `aeat_prefilled`); "provider" and
"resolver" are used interchangeably for the same role. Two false-friend filenames sit
inside the registry binding package without being part of it:
`_m232_row_bindings.py` (a CLI-row materialiser, not a `DataBindingDefinition` family,
not in the validator dispatch table) and `_sources.py` (a BOE/HTML corpus integrity
verifier, unrelated to binding *source kinds*). One-concept-many-names: the resolver
output role is spelled `CalculationSourceResolution` / `BindingSourceResolution` /
`ProfileSourcedBindingResult` / `CalculationBindingResolution`. Confidence: HIGH.

#### F7 — Operator-facing CLI vocabulary forked the one aggregation path into three unrelated verbs under unrelated command groups

The `one-aggregation-path-pull-equals-calculate` rule unifies the *implementation*
(both transports share `resolve_relations_from_local_store`), but the *operator
vocabulary* stayed forked: "produce the bound casilla values from sources" is spelled
`app modelo bindings preview`, `config google sync calc pull --compute`, and
`app modelo work calculate` — three verbs under two unrelated groups. `bindings list`
(definitions) vs `bindings preview` (definitions + values) names the value-bearing
verb after a UI gesture, not what it sources. The `pull` verb multiplexes four
source-family channels (`operator_edits` / `binding_edits` / `relation_edits` /
`row_set_edits`, `_google_sync_calc.py:411`) with no naming parity to the resolver
families. Confidence: HIGH.

### MEDIUM

#### F8 — The canonical binding model's most-used field is untyped; type-safety is bolted on at validate-time, never at the schema

`DataBindingDefinition.selector` is a free-form `Mapping[str, BindingSelectorValue]`
(`_schema_scalars.py:399`); the per-family strict selector models are applied only
during the validate pass and never replace the stored field type. `typed_enum: str |
None` is a stringly-typed pointer to an enum *class*. These are the residual
type-erasure inside the otherwise-hardened registry core. Confidence: HIGH
(swarm-sourced; consistent with the hardening ADR's own "out of scope" notes).

#### F9 — Some source-kind collections are still hand-listed, not derived from the canonical enum

`_ROWS_DEFAULT_SOURCE_KINDS` (`_binding_aggregation.py:20`) hand-lists the four
ROWS-default detail families and must stay in lock-step with the five-member
`ROW_SET_GROUPING_FOR_BINDING_SOURCE` by hand — the exact "derive from the enum"
discipline the `binding-source-kind-single-taxonomy` rule mandates for the other
frozensets. The withholding validator compares against `RowSetGroupingKind.WITHHOLDING`
rather than `BindingSourceKind.WITHHOLDING` (works only by cross-enum value-equality)
and is named `..._selector_shape` while actually lifting fact/op invariants to build
time (misleading name). Confidence: HIGH.

#### F10 — Three concepts share one module file; locality of resolver vs selector vs gate is inconsistent

`_multi_year.py` holds the live `PreviousFilingSourceResolver`, the orphaned
`MultiYearResolver`, AND the unrelated heavily-live `EnrollmentRecorder` multi-year
authorization verifier — three concepts in one file. `PreviousFilingSourceResolver`
lives in `_multi_year.py` while its selector and invariants live in
`_bindings_previous_filing.py` (a locality split). Resolvers implementing the one
mesh port are spread across four packages (`application/aggregation`,
`application/calculations`, `application/invoices`, `application/modelo`).
Confidence: HIGH.

## Recommendations

This is the opening audit of a multi-day campaign; the recommendation is a sequenced
programme, not a single fix. The deliverable that closes the disjointedness is a
**unifying architecture ADR** (or a small ADR set) that the prior two ADRs each
deliberately declined to own — one document that defines "the bindings interface" as
*all* cross-source data sourcing and adapts it uniformly to the backend schema.

Proposed phase sequence (each phase its own ADR → plan → execute → review arc):

1. **Taxonomy unification (addresses F1, F9).** Make `BindingSourceKind` the single
   typed source-kind authority end-to-end: replace the mesh's bare-string
   `owned_sources` / `source_kind` / `DEFERRED_SOURCE_KINDS` /
   `_BUCKET_AGGREGATION_OWNED_SOURCES` with the enum; reconcile the mesh-only
   (`borrador`, `iva_wallet_decision`) and enum-only (`purchase_invoice_evidence`,
   `ledger_transaction`) members into one coherent set; retire the duplicate
   `operator_surface.SourceKind`; derive every remaining hand-listed collection.
   Highest blast radius — sequence first because everything else references it.

2. **One resolver contract (addresses F2, F5, F10).** Collapse the three sourcing-
   contract shapes onto one port + one result envelope; bring profile/borrador into
   the mesh (or formally document why pre-mesh, ending the B→A→B wrap); adjudicate
   the shape-C service (fold counterpart/foreign-assets into the mesh or formally
   declare them a separate, documented surface); resolve the `MultiYearResolver`
   orphan (enroll or delete per `no-dormant-source-resolvers` / `no-legacy`); add a
   single "where does source X resolve" registry + a frozenset↔enrollment parity gate.

3. **Cross-filing fold-in unification (addresses F3, F4).** Decide the canonical
   mechanism for "fold a prior/other filing forward" — relation vs previous_filing —
   per the existing `calculation-source-canonical-mechanism` rule, and either merge
   the two implementations or formalise the boundary; deduplicate the three
   observation-folding copies and the parallel period-offset math; lift relation
   aggregation onto the typed `BindingAggregation`/op model at parity with bindings.

4. **Vocabulary + CLI cohesion (addresses F6, F7, F8).** A naming-discipline pass
   (resolve the `Observation`/`BindingRow`/`resolve`/`provider` homonyms, the
   false-friend filenames) and a CLI-verb reconciliation (pull/preview/calculate)
   under the existing CLI-standard rules; finish typing the registry `selector` field.

Each phase MUST: re-read HEAD before acting on any `file:line` here (this is a fast-
landing shared worktree); respect the two settled ADRs as foundations, not targets;
and land relocations as atomic explicit-path commits with docs-scaffold regen.
Treat every `file:line` in this audit as inventory to re-confirm, not gospel.

## Codification candidates

None yet — and deliberately so. This is a phase-1 breadth-discovery audit; the
`vaultspec-codify` discipline forbids codifying on first encounter ("a lesson
qualifies only after it has held across at least one full execution cycle"). The
findings above are not yet constraints that held through a fix — they are the
problem statement for a unifying architecture ADR. Codification is the natural
follow-on to each remediation phase's review, not to this discovery pass.

Anticipated rule directions to author *after* the phases land (recorded so the
intent is not lost, NOT promoted now):

- After phase 1: a single-source-kind-authority rule extending
  `binding-source-kind-single-taxonomy` end-to-end through the application mesh
  (the typed enum is the only representation; no bare-string source vocabulary).
- After phase 2: a one-resolver-contract rule (one port, one result envelope; a
  new source enrolls in the single mesh or is formally, test-gated documented as a
  separate surface — no fourth shape).
- After phase 3: extend `binding-aggregation-is-typed` to relations (relation
  aggregation is the typed model, no inline op re-parse), and a
  one-fold-in-mechanism rule sharpening `calculation-source-canonical-mechanism`.

Each remains a candidate, not a rule, until its phase has shipped and held.
