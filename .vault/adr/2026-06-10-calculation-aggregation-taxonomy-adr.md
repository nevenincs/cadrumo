---
tags:
  - '#adr'
  - '#calculation-aggregation-taxonomy'
date: '2026-06-10'
related:
  - "[[2026-06-10-calculation-aggregation-taxonomy-research]]"
---



# `calculation-aggregation-taxonomy` adr: `Canonical aggregation mechanism per calculation type` | (**status:** `accepted`)

## Problem Statement

The calculation engine has one terminal seam — `calculate_registry_snapshot`
(`domain/calculations/registry/_formula_runtime.py:173`) with five value channels
(`inputs`, `binding_values`, `enum_binding_values`, `relation_values`,
`date_binding_values`) — but MULTIPLE overlapping mechanisms for populating those
channels, and which mechanism is canonical for which calculation type is implicit.
The trigger overlap: a single cross-modelo fold-in (Modelo 100 casilla `0604` ← sum
of Modelo 130 casilla `19` over 1T–4T) is expressible BOTH as a registry `relation`
(`kind = "cross_model_output"`, resolved by `RelationPrefillSourceResolver`) AND as
a `previous_filing` binding (resolved by `PreviousFilingSourceResolver`) — two schema
entities, two resolvers, DIFFERENT live-fire status. The registry today declares the
M100 fold-in BOTH ways at once: relation
`100/revisions/2025/relations/0005-renta-2025-rel-130-pagos-fraccionados.toml`
(carrying `target_binding`, `source_periods`, `period_alignment`) plus binding
`100/revisions/2025/bindings/0039-renta-2025-modelo-130-pagos-fraccionados.toml`
(`source = "previous_filing"`, selector `{ source_modelo = "130", source_output = "19" }`).

Verified mission risk (every claim re-checked at HEAD during this ADR):

1. **Dormant resolver = latent silent mis-declaration.** The live calculate
   entrypoint `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
   (`application/modelo/_calculation_actions.py:419`) enrolls exactly three resolvers
   in its `merge_source_resolutions` mesh tuple (`_calculation_actions.py:516-534`):
   `LedgerIvaAggregationSourceResolver`, `LedgerRentaExpenseAggregationSourceResolver`,
   and `PreviousFilingSourceResolver` (D3-wrapped). `RelationPrefillSourceResolver`
   (`application/calculations/_relation_prefill.py:250`) is NOT enrolled; its only
   production caller is the Google-Sheets workbook calc-sync
   (`entrypoints/cli/_config/_google_sync_calc.py:113-136`), a different surface, and
   the work-calculate CLI never passes `relation_values`. The M100 fold-in binding's
   selector (`source_output`, no period keys) is deliberately NON-direct —
   `_is_direct_previous_filing_binding`
   (`domain/calculations/registry/_bindings_previous_filing.py:287-293`) returns
   false for it — so the ENROLLED previous-filing resolver skips it by design. The
   only mechanism that can fill it is relation resolution, and that resolver is
   dormant. End-to-end consequence, verified: M100 casilla `0604` is `input_kind =
   "computed"` with formula
   `100/revisions/2025/formulas/0079-renta-2025-pagos-fraccionados-ingresados.toml`
   summing two `{ relation = ... }` operands; on the live operator `calculate` the
   relation channel is empty, the fold-in silently does not happen, and the same
   shape covers the whole relation corpus (39 `cross_model_output`, 28
   `annual_summary`, 6 `previous_period`, 3 `annual`, 1 `quarterly` relation rows at
   HEAD): M100←130/131/111/115/123/180/184/190/193, M200, M202, and the
   M180←115 / M190←111 / M193←123 reconciliations. These fold-ins are green ONLY in
   isolated continuity tests that call `resolve_relations_from_local_store` directly.

2. **No advisory when a binding has no resolver.** `collect_unhandled_source_diagnostics`
   (`application/aggregation/_source_mesh.py:242-268`) — which flags a binding whose
   declared source has no enrolled resolver — has NO caller on the live calculate
   path (grep-verified: only its package re-export and one unit test). A blank
   produced by a dormant or missing resolver surfaces zero findings, violating the
   no-silent-under-declaration discipline.

3. **More dormant capacity.** `LedgerRentaIncomeAggregationSourceResolver`
   (`_modelo_bindings.py:291`) and `OssIossLedgerSourceResolver` (`_oss_ioss.py:232`)
   exist, are exported, and have no production call site, while the registry declares
   `ledger_renta_income_aggregation` (3 bindings) and `ledger_oss_aggregation`
   (5 bindings). Eight further declared source kinds have NO resolver at all
   (counts at HEAD: `collectible_invoice` 17, `withholding` 13,
   `related_party_operation` 6, `foreign_asset` 6, `refund_operation` 5,
   `atribucion_member` 4, plus the two dormant-ledger kinds above).

4. **Implicit precedence, unguarded dual-write.** The D2 ruling (caller `--binding`
   may override an auto-carried `previous_filing` value) and the D3 ruling (the IVA
   wallet decision exclusively owns the M303 compensation binding) live as inline
   comments (`_calculation_actions.py:524-546, 603-630`), not as a declared
   precedence contract. Relation→binding materialisation
   (`materialize_relation_binding_values`, `domain/calculations/registry/_relations.py:199-232`)
   happens POST-mesh in `application/modelo/_binding_resolution.py:107-112` where the
   merge `{**relation_binding_values, **resolved_bindings}` silently lets every other
   source win over a relation-materialised value; there is no guard against a
   relation-targeted binding also being direct-previous_filing-resolvable, because
   the mesh duplicate-owner guard (`_claim_binding`, `_source_mesh.py:302-310`) never
   sees relation-materialised binding values.

This ADR decides the canonical mechanism per calculation type, mandates closing the
silent-blank gap, and codifies precedence and double-write prevention. It is the
decision record only; no plan or implementation rides in it.

## Considerations

**The contested overlap — three options weighed for cross-modelo fold-in:**

- **Option A — relation canonical; enroll `RelationPrefillSourceResolver`.** The
  relation entity is purpose-built for the scenario: it is a typed dependency edge
  carrying `kind`, `dependency_role`, `source_revision_selector`,
  `period_alignment`, `source_periods`/`target_periods`, aggregation op, and its own
  `legal_refs`/`source_refs` — none of which the flat previous-filing selector
  models. The relation corpus is the registry majority for fold-ins (77 relation
  rows across M100/M180/M190/M193/M200/M202 vs 7 cross-modelo previous-filing
  binding rows on M390/M353). Relation values feed the engine's first-class
  `relation_values` channel that computed-casilla formulas reference directly via
  `{ relation = ... }` operands, and the workbook surface consumes the same
  `RelationValues` records for prefill-staleness provenance. ONE mesh enrollment
  closes the headline dormancy for the entire corpus at once.

- **Option B — previous_filing canonical; retire `cross_model_output`.** Already
  enrolled, no mesh change. But it would migrate ~77 relation rows, discard the
  typed dependency metadata (`dependency_role`, `period_alignment`) that grounds the
  reconciliation surfaces, break the workbook prefill provenance contract (the
  Sheets calc-sync resolves relations, not bindings), and force computed formulas
  that consume `{ relation = ... }` operands to be rewritten against bindings. The
  previous-filing selector cannot express period-VARIANT alignment (M202's
  `prior_pagos_cumulative`: 2P folds 1P, 3P folds 1P+2P — expressed today as two
  relations scoped by `target_periods`, inexpressible as one static selector).
  Maximal churn, capability loss, highest regression surface.

- **Option C — strict topology boundary (relation = cross-modelo, previous_filing =
  same-modelo only).** Closest to the truth, but the literal form mandates migrating
  M353←M322 to relations, and the substitutability pre-filter blocks that: the M353
  bindings declare `grouping = "per_grupo_member"` (cross-MEMBER fan-in — every
  grupo member's Modelo 322 for the same month is enumerated and summed,
  `_binding_prefill.py:182-263`), an axis the relation schema does not have. A naive
  migration is a constraint-shape mismatch, exactly the false-positive class the
  audit-cadence rule forbids promoting.

**Decision input — what the corpus actually distinguishes.** Same-modelo
single-filer carry uses DIRECT previous-filing selectors that fire live today (M130
cumulative `source_period_offset_from_target = -1`; M100 BIN
`filing_year_delta = -1, period = "0A"`). Cross-modelo fold-ins split: M390/M353 use
direct bindings (live), everything else uses relations plus a NON-direct slot
binding the relation materialises into (dormant). The non-direct slot misdeclares
`source = "previous_filing"` for a value only relation resolution can produce — the
mislabel is the root of the overlap.

**Sibling consistency.** The parallel period-revision ADR establishes that the
revision for every (modelo, year, period) is law-determined via `select_revision`,
never chosen. Both fold-in mechanisms consume `RegistryModeloObservation` records
keyed by (modelo, filing_year, period); a relation's `source_revision_selector`
pins a YEAR (or a year delta), not a revision id, so nothing in this decision
introduces an externally-chosen revision. The sibling ADR's runtime gate for carried
observations (re-confirm a stored prior observation's revision against
`select_revision`) applies to BOTH mechanisms equally.

## Constraints

- The live mesh contract is stable: `merge_source_resolutions` enforces exclusive
  per-binding/per-relation ownership with hard errors (`_source_mesh.py:302-332`),
  and `CalculationSourceResolution` already carries a `relation_values` channel and
  a `diagnostics` tuple the CLI surfaces. Enrollment is additive, not structural.
- `RelationPrefillSourceResolver` already implements the resolver protocol with
  storage-degradation handling and provenance stamping; it is tested in isolation
  (`test_relation_prefill_source_mesh.py`) and exercised by seven continuity suites.
  The frontier risk of enrolling it is low; the risk of NOT enrolling it is a silent
  fold-in failure on every relation-bearing modelo.
- The relation schema has no `grouping` axis; the M353 per_grupo_member fan-in is
  not expressible as a relation today. Any migration mandate touching M353 is
  blocked on a schema extension that is out of scope here.
- Registry TOML stays free-form per the registry-authority-flow rule; new validation
  (slot-source gate, collision gate) lands in registry validation
  (`_validate.py` family), not in the authoring format.
- D3 (IVA wallet owns the M303 compensation binding) is an accepted prior ruling and
  is reaffirmed, not reopened.
- Caller-override guards (`_reject_caller_overrides_of_source_bindings`) must keep
  refusing overrides of ledger-owned sources; extending the D2 carve-out to
  relation-carried values must not weaken that refusal.

## Implementation

**1. Canonical mechanism table (BINDING — the taxonomy future agents follow):**

| Calculation type | Canonical mechanism | Resolver / engine channel | Live enrollment mandate |
|---|---|---|---|
| Intra-revision derivation | Casilla formula | `calculate_registry_snapshot` (engine core) | already terminal — unchanged |
| Ledger projection (current-period transactions → casillas) | Ledger aggregation binding (`ledger_iva_aggregation`, `ledger_renta_expense_aggregation`, `ledger_renta_income_aggregation`, `ledger_oss_aggregation`) | Ledger source resolvers → `binding_values` | Iva + RentaExpense already enrolled; **enroll RentaIncome + OssIoss** |
| Cross-period SAME-modelo carry, single filer, static alignment | `previous_filing` binding with DIRECT selector (period/source_periods/offset declared) | `PreviousFilingSourceResolver` → `binding_values` | already enrolled — unchanged |
| **Cross-MODELO fold-in (the contested overlap)** | **Relation (`cross_model_output` / `annual_summary` / `annual` / `quarterly`)** | `RelationPrefillSourceResolver` → `relation_values` (+ materialised `target_binding` values) | **ENROLL in the live mesh — the headline fix** |
| Same-modelo carry with period-VARIANT alignment (e.g. M202 `prior_pagos_cumulative`) | Relation (`previous_period`), because `target_periods` scoping expresses what a static selector cannot | `RelationPrefillSourceResolver` | covered by the same enrollment |
| Cross-MEMBER fan-in (grupo de entidades, M353←M322) | `previous_filing` binding with `grouping = "per_grupo_member"` — a distinct axis (aggregates across FILERS in one period, not across one filer's history); documented exception, not a fold-in | `PreviousFilingSourceResolver` | already enrolled — unchanged |
| IVA compensación (M303 casilla 110) | `iva_wallet_decision` (D3 reaffirmed) | `IvaWalletDecisionSourceResolver` via the pre-mesh gate (`_iva_wallet_gate.py`) | already enrolled — unchanged |
| Taxpayer facts | `profile` binding | `ProfileSourceResolver` (pre-mesh) | already enrolled — unchanged |
| M100 borrador prefill | `borrador` binding | `Modelo100BorradorSourceResolver` (pre-mesh) | already enrolled — unchanged |
| Operator-entered values | `manual_input` casillas / caller `--casilla` & `--binding` | caller channels | unchanged; precedence declared below |

**2. Cross-modelo fold-in decision (Option A, refined).** Relation
(`cross_model_output` and its annual/quarterly kinds) is canonical for every
fold-in whose source is another modelo's filed output. `RelationPrefillSourceResolver`
is enrolled in the `merge_source_resolutions` tuple of the live calculate path.
Migration mandates for the loser's sites: the M390←M303 previous-filing fold-in
bindings (`390/.../bindings/0001-bindings.toml`) migrate to relations — the
selectors map one-to-one (`source_modelo`, `source_casillas`→`source_output`,
`source_periods`, op) — landing with a value-parity gate (identical resolved values
before/after; the parity oracle is the existing live-firing path itself, not a
hand-computed expectation). The M353←M322 per_grupo_member bindings are explicitly
EXEMPT (constraint-shape mismatch: relations have no grouping axis); they remain
canonical-as-bindings under the cross-member row of the table, with a named revisit
trigger: if a second cross-member surface appears, extend the relation schema with a
grouping axis and fold M353 in then.

**3. Slot-binding hygiene (kills the dual modelling at the root).** A binding that
exists only as a relation's `target_binding` materialisation slot MUST NOT declare
`source = "previous_filing"`. Introduce the dedicated slot source kind
`relation_prefill` (matching the resolver's `owned_sources`) and re-stamp every
relation-targeted slot binding (the M100/M180/M190/M193/M200/M202 non-direct rows).
Registry validation gains two gates: (a) a binding with `source = "previous_filing"`
MUST satisfy the direct-selector predicate (`_is_direct_previous_filing_binding`) —
the non-direct shape becomes a registry validation error instead of a silent skip;
(b) every `relation.target_binding` must reference a binding whose source is
`relation_prefill`, and no binding may be both relation-targeted and
direct-previous_filing-resolvable. The relation-vs-previous_filing collision the
research flagged becomes structurally impossible at registry-compile time.

**4. Double-write prevention at runtime.** Relation→target-binding materialisation
moves INTO the enrolled resolver: `RelationPrefillSourceResolver` emits the
materialised `target_binding` values in its resolution's `binding_values` (via
`materialize_relation_binding_values`), so the mesh's `_claim_binding` exclusive-
ownership guard adjudicates any collision with another resolver loudly. The silent
post-mesh merge precedence at `_binding_resolution.py:112` (where
`{**relation_binding_values, **resolved_bindings}` lets every other source override
a relation value without a finding) is retired in favour of the mesh guard.

**5. Declared precedence order (codifies D2/D3 out of inline comments).** For the
decimal binding channel, lowest→highest:

1. `profile` resolver (pre-mesh facts);
2. mesh backend resolvers — ledger aggregations, `previous_filing`,
   `relation_prefill` — with EXCLUSIVE intra-mesh ownership (duplicate claim is a
   hard `AggregationValidationError`, never a quiet override);
3. `borrador` (M100 prefill);
4. caller overrides (`--binding` / `--casilla`) — permitted ONLY for
   `previous_filing` and `relation_prefill` carried values (D2 carve-out extended to
   relation carries by the same logic: an operator override of an auto-carried prior
   value is legitimate and the engine's consistency check adjudicates divergence);
   REFUSED with a hard error for ledger-owned sources
   (`_reject_caller_overrides_of_source_bindings`) because the persisted revision
   must reflect the sources it claims to aggregate.

`iva_wallet_decision` sits outside the precedence ladder as an exclusive owner with
refusal-on-conflict semantics: the M303 compensation binding
(`modelo-303-compensacion-pendiente-anteriores`) is stripped from previous-filing
resolutions pre-mesh (D3, `_previous_filing_resolution_excluding_iva_compensation`)
and any conflicting caller/backend value raises
`ModeloIvaWalletReconciliationBlocked` rather than being out-ranked.

**6. Close the under-declaration (non-negotiable).**

- Enroll `RelationPrefillSourceResolver` (headline), plus
  `LedgerRentaIncomeAggregationSourceResolver` and `OssIossLedgerSourceResolver`
  (dormant, tested, own declared registry kinds) in the live mesh tuple.
- Wire `collect_unhandled_source_diagnostics` into the live calculate path: after
  the mesh merge, invoke it with `handled_sources` = the merged resolution's
  `owned_sources` ∪ the pre-mesh-handled kinds (`profile`, `borrador`,
  `iva_wallet_decision`) and the default `manual_sources = {"manual_input"}`;
  append the result to the resolution diagnostics so
  `BucketAggregationCalculationResult.source_diagnostics` — which the operator CLI
  already surfaces — carries a non-blocking ADVISORY for every binding whose
  declared source has no enrolled resolver. A binding or relation with no resolver
  must never silently blank again.
- Resolver-less source kinds, explicit per-kind disposition: `collectible_invoice`
  (17), `withholding` (13), `related_party_operation` (6), `foreign_asset` (6),
  `refund_operation` (5), `atribucion_member` (4) — resolver construction is
  DEFERRED (each is an informativa detail-row / manual-evidence surface today and
  needs its own grounded design); the wired advisory makes every one of them
  operator-visible immediately, which satisfies the no-silent-under-declaration
  minimum safeguard. They MUST NOT be added to the `manual_sources` allowlist —
  that would re-silence them. Each future resolver enrolls under the mesh
  ownership contract of this taxonomy.

## Rationale

Option A wins because it is the only option where the purpose-built entity, the
majority corpus, the engine contract, and the fix's blast radius all point the same
way. The relation IS the cross-modelo dependency model: it is the only entity that
types the dependency (`dependency_role`), aligns periods declaratively
(`period_alignment`, `target_periods`), pins the source year lawfully
(`source_revision_selector` — consistent with the sibling ruling that revisions are
law-determined, never chosen), and stamps workbook-grade provenance. The engine
already treats `relation_values` as a first-class channel and computed casillas
already reference relations in their formulas — Option B would rewrite formulas and
discard metadata to standardise on the LESS expressive entity, and verified corpus
facts kill it twice over (it cannot express M202's period-variant cumulative
alignment, and it abandons the workbook surface's staleness contract). Option C's
literal boundary fails the substitutability pre-filter on M353. The refined
Option A keeps every live-green path live (M390 migrates under a parity gate;
M353 is honestly exempted on constraint shape rather than force-fitted), and closes
the headline dormancy with ONE enrollment instead of ~77 registry migrations.
The slot-source re-stamp addresses the actual root cause: the overlap exists
because relation slots were mislabelled `previous_filing`, making one fold-in look
like two mechanisms. Once slots declare `relation_prefill`, the two mechanisms have
disjoint declared ownership, the registry gate enforces it at compile time, and the
mesh guard enforces it at runtime — defence in depth per the calculation-grounding
and no-parallel-write-path rules.

## Consequences

- **Gain:** the M100/M200/M180/M190/M193/M202 fold-ins fire on the live operator
  calculate path for the first time; the silent mis-declaration class (blank pagos
  fraccionados credits, blank annual reconciliations, blank BIN/dotaciones carries)
  is closed by enrollment, and the diagnostics wiring guarantees the NEXT dormant
  resolver surfaces as an advisory instead of a blank.
- **Gain:** mechanism ownership becomes declared data (binding `source` kind ↔
  resolver `owned_sources`), auditable by the registry gate and greppable by future
  agents; D2/D3 precedence moves from inline comments to a binding contract.
- **Honest difficulty:** enrolling the relation resolver changes live numbers for
  any bucket that has prior filed observations — values that were blank become
  populated. That is the CORRECT direction, but existing operator workflows that
  hand-filled the blanks will now hit the engine consistency check on divergence;
  the D2 carve-out extension (caller may override relation carries) is the relief
  valve, and the rollout must re-baseline the affected enrollment/continuity suites
  against the live path rather than the direct-call path.
- **Honest difficulty:** the slot re-stamp (`previous_filing` → `relation_prefill`)
  touches every relation-bearing revision's bindings TOML plus the registry
  validator, and must land atomically with the validator gate to avoid a window
  where neither gate holds.
- **Deferred surface:** six resolver-less source kinds remain unresolved-by-design
  with advisories; per_grupo_member stays binding-shaped until a second cross-member
  surface justifies a relation grouping axis. Both deferrals are named here so the
  honesty-review gate can track them rather than rediscover them.
- **Opens:** with relation resolution live-enrolled, the workbook calc-sync and the
  operator calculate path consume the SAME resolver, eliminating the two-surface
  drift risk the research flagged; future cross-modelo reconciliation modelos get
  one obvious authoring pattern.

## Codification candidates

- **Rule slug:** `calculation-source-canonical-mechanism`.
  **Rule:** Every calculation value channel has exactly one canonical mechanism per
  calculation type per this ADR's taxonomy table — cross-modelo fold-ins are
  relations, same-modelo static carry is a direct `previous_filing` binding,
  cross-member fan-in is `per_grupo_member`, M303 compensación is the IVA wallet
  decision — and a new aggregation surface MUST enroll under an existing row or
  amend this ADR before shipping.

- **Rule slug:** `no-dormant-source-resolvers`.
  **Rule:** Every `ModeloSourceResolver` merged to main MUST be enrolled in the live
  calculate mesh (or deleted), every registry binding source kind MUST have either
  an enrolled resolver or an explicit manual/deferred registration, and
  `collect_unhandled_source_diagnostics` MUST run on the live calculate path so an
  unrouted source kind surfaces a non-blocking advisory — never a silent blank.

- **Rule slug:** `relation-slot-bindings-declare-relation-source`.
  **Rule:** A binding that exists as a relation's `target_binding` materialisation
  slot declares `source = "relation_prefill"`, never `source = "previous_filing"`;
  a `previous_filing` binding MUST carry a direct selector, and registry validation
  refuses a binding that is both relation-targeted and previous-filing-resolvable.
