---
tags:
  - '#research'
  - '#bindings-interface-hardening'
date: '2026-06-14'
modified: '2026-06-15'
related:
  - "[[2026-05-20-calculation-source-connectivity-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-06-02-registry-bindings-boundary-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]"
---



# `bindings-interface-hardening` research: `bindings interface: definition, validation, boundary and semantic-spread discovery`

The "bindings interface" — how a registry-declared calculation input is defined,
validated, resolved to a value, carried onto a filing draft, exported, and shown
to an operator — emerged organically across many campaigns and has never received
a single centralised, focused review. This research is the RAG-grounded,
swarm-driven code discovery (five parallel readers, one per layer) that grounds a
hardening/codification campaign. The goal is to separate what is already decided
and gated from the genuine, uncodified drift, so the follow-on ADR hardens the
right altitude instead of re-deciding settled ground.

## The two altitudes of the interface

The word "binding" spans two altitudes that are in very different states.

**Altitude 1 — the resolver mesh (runtime/semantic). Already decided and gated;
out of scope for new decisions.** The `ModeloSourceResolver` port,
`CalculationSourceContext` / `CalculationSourceResolution` payloads, and the
`CalculationSourceMesh` orchestrator were decided in the calculation-source
connectivity ADR and refined by the aggregation-taxonomy ADR. The live gates are
present and rule-backed: `assert_no_novel_source_kinds` and
`collect_unhandled_source_diagnostics` run on the calculate path
(`src/aeat/application/modelo/_calculation_actions.py:691` and `:587`); the
slot-source collision gate lives in
`src/aeat/domain/calculations/registry/_validate_relation_sources.py`; the
pull==calculate parity is regression-backed
(`test_pull_path_calculate_path_casilla_parity.py`). A new ADR MUST NOT re-decide
this surface.

**Altitude 2 — the definition/validation layer, the operator-facing boundary, and
the word "binding" itself. This is the real, uncodified drift** and the proper
target of the campaign.

## Finding cluster A — validation is non-uniform within one layer

The schema is clean: `DataBindingDefinition`
(`src/aeat/domain/calculations/registry/_schema.py:977-1004`) is one strict,
frozen envelope (`id`, `source`, `selector`, `aggregation`, `legal_refs`,
`source_refs`, …). Enforcement, however, is scattered across **three incompatible
validator conventions**:

- public `validate_*_binding_definition(binding) -> None` that *raises*
  (invoice, the four ledger kinds);
- `validate_withholding_binding_selector_shape(binding) -> list[str]` that
  *accumulates*; and
- **no public validator at all** for counterpart and the four detail-record
  families (their invariants are private `_validated_*_selector` helpers).

The load-bearing consequence is a **build-time vs resolve-time split**. The
counterpart and withholding families had their op/fact invariants explicitly
lifted to registry-build (`_bindings.py:605-609`, citing "selector-drift F3"), but
the four detail-record families (`related_party_operation`, `foreign_asset`,
`atribucion_member`, `refund_operation`) and `previous_filing` run the same class
of invariant **only at resolve time** (`_detail_record_bindings.py:85,214,349,456`
are reached only from inside their own `resolve_*` functions;
`_bindings_previous_filing.py` checks aggregation `op` validity only in
`_aggregate_previous_filing_binding`). A malformed binding for those families ships
clean through snapshot build and only fails when a taxpayer's calculation runs.

Related defects in the same cluster:

- **`aggregation` / `op` is untyped.** `aggregation` is a free-form
  `Mapping[str, ...] | None`; `op` is re-derived as
  `str((binding.aggregation or {}).get("op", <default>))` at ~10 sites with
  **divergent silent defaults** — `"sum"` for invoice/counterpart/ledger/
  withholding/previous, `"rows"` for the four detail-record families. There is no
  typed aggregation model and no single accessor.
- **Selector normalisation is inconsistent.** invoice/ledger/withholding/
  counterpart/previous_filing project the selector through
  `selector_as_dict` (strips a stray injected `source` key) before validating;
  the four detail-record `_validated_*` helpers call `model_validate` on the raw
  `binding.selector` — a stricter-at-resolve / looser-at-build mismatch within one
  layer.
- **Diagnostic fidelity diverges.** The shape gate preserves the underlying
  pydantic field error (`_bindings.py:599`); the per-source resolver validators
  wrap it into a generic "malformed selector" string, discarding the field detail.
- **Near-verbatim duplication.** `resolve_counterpart_binding_values` /
  `_row_values` (`_counterpart_bindings.py:186-263`) are near-copies of the invoice
  resolvers (`_invoice_bindings.py:307-391`); the two `intracommunity_clave`
  validators and the two `_validate_rectification` model validators are byte-for-
  byte duplicates.

## Finding cluster B — enum and source-kind taxonomy is half-adopted

The closed set of binding `source` kinds (the 18-member
`DataBindingDefinition.source` Literal) is sourced from three owners that disagree:

- `RowSetGroupingKind` (`src/aeat/core/aggregation.py`) is enum-keyed end-to-end
  for `WITHHOLDING` and `FOREIGN_ASSET`, but its `RELATED_PARTY` / `ATRIBUCION` /
  `REFUND` members exist while the binding source uses divergent free strings
  (`related_party_operation` / `atribucion_member` / `refund_operation`) — the enum
  *value* does not even match the source token, so the enum cannot be used as the
  source without a translation table.
- `LEDGER_BINDING_SOURCE_KINDS` (`_ledger_bindings.py:32`) lists only 2 of the 4
  ledger sources the same module handles — any "is this a ledger binding?" consumer
  misclassifies the other two.
- `INVOICE_BINDING_SOURCE_KINDS` is hardcoded strings, not the
  `AggregationSourceKind` members.
- `AggregationSourceKind.PURCHASE_INVOICE_EVIDENCE` is both an invoice-family and a
  counterpart kind, so the same literal is routed through two validation pipelines
  depending on which collection is consulted.
- The `typed_enum` schema field (`_schema.py:1000`) is **dead** — declared, never
  read by any binding module.

## Finding cluster C — silent-zero is structurally possible everywhere except IVA

Selector `fact` defaults silently widen scope (e.g. `_OssIossLedgerSelector.fact`
/ `_IvaLedgerSelector.fact` default to `"iva_amount_sum"`), and resolvers fall
through to `Decimal("0")` on an empty match. IVA has an explicit fail-closed screen
(`unsupported_ledger_iva_observations`, `_ledger_bindings.py:381-428`) — **no
equivalent screen exists for OSS, renta, withholding, counterpart, or any
detail-record family**, so silent-zero under-declaration is structurally possible
there. Combined with cluster A's missing build-time op check, a mis-authored
binding can resolve to a silent `Decimal("0")` rather than failing. This is the
`no-silent-under-declaration` rule's exact failure mode, present off the IVA path.

At the resolution layer the headline hole is already closed (enrolled resolvers,
live novel-source gate, deferred-source advisories). The residual silent blank is
**missing data, not a missing resolver**: an enrolled `previous_filing` /
`relation_prefill` binding with no prior observation skips silently at calculate
time (`_binding_prefill.py:558-561`), and an unresolved *non-formula* relation
produces neither value nor diagnostic (`_relation_prefill.py:164`, filtered by
`_formula_relation_ids`). Both are caught at file time by the cross-period
clean-state guard (`MISSING_OBSERVATION`), so they cannot silently *file* — but
they can silently *calculate*. Three copies of the ADR-R2 revision-carry gate exist
(`_binding_prefill.py:75-97`, `_cross_period_clean_state.py:706-740`, and the
sister `_relation_prefill` path), a real drift risk.

## Finding cluster D — provenance is dropped at the operator boundary

Casilla values carry full `ModeloCasillaProvenance` (`formula_id`, `legal_refs`,
`source_refs`) onto the draft and into the export. **Binding values do not.**
`_filing_binding_values` (`src/aeat/application/filing/__init__.py:426-454`) builds
every `ModeloBindingValue` with a hardcoded free-text `source="registry binding
input"` and discards the binding definition's `legal_refs` / `source_refs`. The
carrier itself (`src/aeat/domain/filing/_schema.py:71-80`) and both CLI payloads
(`BindingRowPayload`, `BindingPreviewRowPayload`,
`src/aeat/entrypoints/cli/_modelo_payloads.py:825-860`) model no legal grounding —
even though the registry binding definitions hold it and the fichero/BOE export
layer still emits it (`registry/_export.py:191-215`). The bindings half of the
interface silently violates the `aeat-calculation-grounding` rule that the casilla
half upholds: an operator inspecting or filing a bound value cannot see its legal
basis.

CLI-surface defects in the same boundary:

- `bindings list --modelo` is an untyped `str` with no `click.Choice` and no
  accepted-codes refusal, violating the app-modelo-bindings ADR amendment
  (`_modelo_discovery_cli.py:431-434,457-460`).
- `ModeloBindingsListResult.bindings` is `list[dict[str, object]]`
  (`_modelo_payloads.py:850`) — an untyped dict bag — while the typed
  `BindingRowPayload` exists and is used for nothing; `preview` is typed, `list` is
  not.
- `--binding KEY=VALUE` numeric-vs-enum routing is a `try Decimal(value)/except`
  heuristic (`_calculate_input.py:214-220`): a malformed amount (trailing letter)
  is silently reclassified as an enum string rather than rejected as a bad amount.
  Registry validation still rejects truly invalid enums/missing bindings
  downstream, so calculation correctness is preserved — but the classification is a
  bespoke string heuristic, not a registry-data-type-driven coercion.

## Finding cluster E — "binding" is one strong core surrounded by homonyms

A single coherent core exists: the registry `DataBindingDefinition` + its
`BindingId` + the filing `ModeloBindingValue` value carrier, with a clean fan-in of
source resolvers (profile, borrador, IVA-wallet) merged by
`_binding_resolution.py` and surfaced via `_binding_readiness.py`. For that cluster
"binding" means one consistent thing: a registry-declared calculation input,
resolved from some provenance, carried onto a draft.

The drift is at the edges, where the word was reused for unrelated ideas:

- **Two `_profile_binding.py` files that are unrelated homonyms.**
  `src/aeat/application/modelo/_profile_binding.py` projects `source="profile"`
  registry bindings from a taxpayer's profile facts;
  `src/aeat/adapters/outbound/google/_profile_binding.py` resolves which AEAT
  profile UUID an OAuth session is scoped to. Zero shared imports, types, or call
  paths — but the identical filename is the single most likely thing to mislead a
  grep-driven refactor.
- `decimal_from_string` (`_decimal_binding_value.py`) is a str→Decimal parser
  misfiled under a "binding value" name; it is not a binding.
- `legal_basis_binding` (an `iva` test concept) binds a rate to its BOE article — a
  verification gate, not a data binding.
- The three source-resolver bindings (profile, borrador, IVA-wallet) each invent
  their own `*Result` type and `bindings_sourced_from_*` trace tuple; they share
  the resolver protocol but not a result contract, and naming-by-source rather than
  naming-by-role obscures that they are one role.
- `DataBindingDefinition` (the declaration) and `ModeloBindingValue` (its value
  carrier) live in different domain packages, linked only by a bare `BindingId`
  string with no protocol asserting the reference.

## Finding cluster F — structural debt, prior decisions, and the codification gap

`src/aeat/domain/calculations/registry/_bindings.py` is a ~3,040-line, ~15-family
monolith with a private `_PreviousModeloSelector` coupling into `_formula_runtime.py`.
Two prior boundary audits (`2026-06-02-registry-bindings-boundary-audit`,
`2026-06-02-registry-formula-runtime-boundary-audit`) proposed codify candidates
`registry-resolver-family-extraction` and `registry-formula-runtime-facade` —
**neither was ever promoted to a rule** (confirmed: no rule file exists for either).

Prior art that the ADR must build on, not duplicate: the source-mesh interface is
already accepted (connectivity + taxonomy ADRs); slot-source hygiene, no-dormant-
resolver enforcement, pull==calculate parity, the precedence ladder, and
period→revision determinism are all decided and codified as rules. No document is
titled "bindings interface," but its runtime substance is already decided across
two ADRs. The genuinely open codification target is the **definition/validation
contract, the operator-facing provenance boundary, the semantic disambiguation of
the word, and the un-promoted structural-extraction discipline** — not the resolver
mesh.

Open deferred items noted for scope-fencing (not campaign targets unless promoted):
six resolver-less source kinds advisory-deferred by design (`withholding`,
`collectible_invoice`, `related_party_operation`, `foreign_asset`,
`refund_operation`, `atribucion_member`); the `MultiYearResolver` orphan; the
`PurchaseInvoiceEvidenceSourceResolver` data-shape blocker; `payable_invoice`
declared by no registry binding.

## Discovery method

RAG-first per the standing mandate (`vaultspec-rag` over code and vault, port
8766), then `rg`/`Read` confirmation of every cited symbol. Five parallel
read-only Explore agents, one per layer: registry definition, application
resolution/mesh, semantic-spread of the word, filing/export + CLI boundary, and
vault/rules prior art. Every finding above is anchored to a confirmed `file:line`.
The synthesis separates already-gated runtime decisions (altitude 1) from the
uncodified definition/boundary/semantic drift (altitude 2) that this campaign
targets.
