---
tags:
  - '#adr'
  - '#autonomic-deduccion-auto-trigger'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:671814ddb07f5f7e99e16ca8ac7b983529febc00e82f00ffff81f0a99d1ddde2'
related:
  - "[[2026-07-01-autonomic-deduccion-auto-trigger-research]]"
  - "[[2026-06-19-m100-dependent-modelo-applicability-adr]]"
  - "[[2026-05-08-renta-cuota-integra-autonomic-scale-adr]]"
---

# `autonomic-deduccion-auto-trigger` adr: `autonomic deduccion auto-trigger framework, madrid nacimiento adopcion first slice` | (**status:** `accepted`)

## Problem Statement

Issue #550 (P1, systemic): no Modelo-100 autonomic-deducción box is auto-computed. Every comunidad's `deduccion_autonomica_res` casilla — including Madrid's "Por nacimiento o adopción de hijos" (casilla `1039`) — is a manual-input box (research F1). The `adoption_date` axis, the descendant model, and the Madrid deducción casilla all exist independently, but nothing connects a profile signal (an adoption or birth event) to an auto-populated deducción. A taxpayer entitled to the deducción files zero unless they know the box exists and type the amount by hand.

This is not a one-box fix. A faithful auto-trigger for even a single autonomic deducción needs cross-cutting machinery: per-CCAA per-child amount, a double income-limit test on casillas `0435`+`0460`, unidad-familiar base aggregation, a multi-year applicability window (entry year plus the two following), parent prorrateo, and — for the sibling international box — a +50 % uplift. The decision is therefore a FRAMEWORK: the auto-trigger capability, with Madrid nacimiento/adopción as the worked first case. #550's audit amount (€600) is stale; the current Madrid figure is 721,70 € (DL 1/2010, from 2023).

## Considerations

- The codebase already owns the canonical compute mechanism (research F2): `_profile_binding.py` injects derived facts (marriage-month integers, menores-3 count, state-attribution ratio) into synthetic keys that registry formulas/bindings consume through the Decimal/enum/date channels, enrolled in the live calculate mesh. A date-axis auto-trigger is the same shape the marriage precedent already ships.
- The `DescendantInfo` model already carries `adoption_date`, `birth_date`, `convive_con_contribuyente`; `_entry_date()` is the exact deducción key; persistence and CLI capture exist (F3). No new capture axis is needed for the first slice.
- CCAA residence is already a typed `CCAA` enum dispatch key (F4); the registry formula op set (`if_then_else`, `greater_than`, `min`, `multiply`, `lookup_bracket_by_ccaa`, CCAA-scoped `parameters`) already expresses the income gate and the amount (F6). No new op or source kind is required.
- Two terms cannot be a pure registry formula: the per-descendant date-window/convivencia count, and the unidad-familiar spouse-plus-children base aggregate (no casilla on this filer's declaration holds the spouse's base — F5, F9). Both must be Python-derived facts, exactly as marriage-month and menores-3 already are.
- Binding rules: `casilla-grounding-corrects-actividades-default-by-section` (autonomic → art-77), `registry-calculation-legal-grounding` (cite the binding provision that fixes 721,70), `legal-grounding-verifies-bundled-authoritative-corpus` (cross-check the figure, honest `reviewed_by`), `aeat-safety-legal-gates`, `no-silent-under-declaration`, `aeat-registry-authority-flow`, `no-dormant-source-resolvers`, `one-aggregation-path-pull-equals-calculate`, `revision-resolution-is-law-determined`.

## Considered options

**Mechanism (decision D1):**

- **A — Reuse the profile-derived-fact injector + registry formula pipeline (CHOSEN).** A new `_inject_derived_autonomic_deduccion_facts` computes the eligible-count and unidad-familiar aggregate (the terms no casilla holds); a registry formula on casilla `1039` applies the income gate and the CCAA-scoped per-child amount. Pro: no new source kind, rides the enrolled mesh, grounded, pull=calculate parity for free, one canonical mechanism. Con: the deducción logic is split across a Python injector and a registry formula (mitigated — this split is exactly the existing marriage/menores-3 precedent, and it is the RIGHT split: registry owns the regulated figures, Python owns the per-descendant date/aggregation the schema cannot express).
- **B — A bespoke autonomic-deducción resolver / new binding `source` kind.** Rejected: violates `no-dormant-source-resolvers` / `calculation-source-canonical-mechanism` (a new mechanism for a value an existing taxonomy row covers), and re-forks the compute path the marriage/family injectors already own.
- **C — Pure registry formula, no Python derived fact.** Rejected: the registry cannot express the per-descendant 3-year window, convivencia, or the spouse's base aggregate; the formula would silently omit the income gate's unidad-familiar term.
- **D — Pure Python compute writing the casilla value directly, bypassing the registry.** Rejected: bypasses registry authority (`aeat-registry-authority-flow`), drops legal_refs/source_refs grounding, and breaks calculate/pull parity — the export path would not see the value.

**Advisory-first vs direct-compute (decision D4):**

- **Advisory-first with conditional direct-compute (CHOSEN).** Compute the value through the registry formula so it appears as a grounded `CasillaObservation`, but surface it as a non-blocking `Notice` (advisory) rather than silently finalising it; auto-populate the casilla value only when every input is complete and unambiguous (single filer, convivencia known, income under limit, unidad-familiar term evaluable). Pro: honours `no-silent-under-declaration` (surface, never silent) while respecting that a deducción OVER-claim is the symmetric hazard the operator must confirm.
- **Direct-compute always (silently finalise).** Rejected: prorrateo depends on the other parent's filing choice the app cannot observe, and the unidad-familiar limit may need spouse data the app does not hold — silently applying an unverified deducción risks an over-claim.
- **Advisory-only (never write the casilla).** Rejected: when inputs ARE complete the value is deterministic and grounded; withholding it re-creates the manual-entry gap #550 exists to close.

## Constraints

- The unidad-familiar 61.860 € aggregate needs the other unidad-familiar members' base imponible, which is not verified to be persisted (research F9). Until confirmed, the aggregate is either operator-supplied or the trigger is advisory-only when it cannot be evaluated — a fail-closed default (no auto-apply on missing data), consistent with `2026-06-19-m100-dependent-modelo-applicability-adr`.
- The precise disposición that set 721,70 from 2023 must be identified and added to the legal catalogue with a `corpus_ref` before the value ships as grounded (`registry-calculation-legal-grounding`); the framework art-77 alone is insufficient for the amount.
- Parent stability: the mechanism depends on `_profile_binding.py` (stable, enrolled in the mesh) and the fragmented 2025 M100 revision loader (stable). No frontier dependency.
- The figure is verified against the bundled 2025 manual but must be cross-checked against live BOE/AEAT and shipped with honest agent-prepared `reviewed_by` pending operator re-stamp (`legal-grounding-verifies-bundled-authoritative-corpus`).

## Implementation

Three layers, all reusing canonical surfaces.

1. **Signal (no new capture).** The trigger reads existing `renta_family.descendiente.{n}.adoption_date` / `.birth_date` / `.convivencia` facts and the `tax_residence.ccaa` enum. For the first slice the CCAA gate scopes to Madrid.

2. **Python derived-fact injection (decision D2 shared primitives).** A new `_inject_derived_autonomic_deduccion_facts(fact_index, filing_year)` in `_profile_binding.py`, companion to the marriage and menores-3 injectors, backed by a `RentaFamilyProfile.madrid_nacimiento_adopcion_count(filing_year)` helper. It counts descendants whose entry year (`_entry_date().year`) satisfies `entry_year <= filing_year <= entry_year + 2` and who cohabit, and computes the unidad-familiar base aggregate where the data exists. These become synthetic Decimal facts (`renta_family.madrid_nacimiento_adopcion_eligible_count`, and the unidad-familiar base term) consumed through the Decimal channel. The reusable primitives — a per-descendant multi-year applicability-window helper and a unidad-familiar base-aggregation helper — are the framework that later CCAA/deducción enrollments reuse.

3. **Registry formula + CCAA-scoped parameters (decision D3 bounded slice).** Casilla `1039` flips from manual to computed by gaining a formula (`target_casilla_id = "1039"`) that expresses the double income-limit gate over casillas `0435`+`0460` (contribuyente limit dispatched by declaration-type: 30.930 individual / 37.322,20 conjunta) and the unidad-familiar 61.860 limit, times the eligible count times the per-child parameter (721,70, a CCAA-scoped registry `parameter`; a 600 pre-2023 variant gated on entry year), divided by the prorrateo factor. Amount and limits are registry parameters grounded to `ley-35-2006:art-77` plus the Madrid DL 1/2010 provision defined in the legal catalogue with a resolving `corpus_ref`. Only casilla `1039`, filing year `2025`, is in the first slice; the international box `1040` (+50 %) and other CCAA/deducciones enroll later under the same framework.

4. **Surface (decision D4).** The computed value rides `engine_result.values` as a grounded `CasillaObservation` and is surfaced through the typed `Notice` advisory channel (`cli-notices-are-the-only-diagnostic-channel`); the casilla auto-populates only when every input is unambiguous, otherwise the Notice states eligibility and the amount and leaves the operator to confirm. The value is identical on the calculate and Sheets-pull paths because the injector runs on both (`one-aggregation-path-pull-equals-calculate`).

## Rationale

Option A is the only mechanism that reuses the enrolled canonical pipeline (research F2) without forking a resolver (`no-dormant-source-resolvers`, `calculation-source-canonical-mechanism`) — the knockout criterion is that B/C/D each either invent a parallel mechanism, cannot express the regulated logic, or drop grounding/parity. The Python/registry split (A over C) is not a compromise but the correct boundary: the registry owns the regulated figures and the income gate (F6), Python owns the per-descendant date-window and unidad-familiar aggregation the schema cannot reach (F5). Advisory-first (D4) resolves the tension `no-silent-under-declaration` creates for a deducción: the rule forbids a SILENT grant, and a deducción's failure mode is over-claim, not under-declaration, so surfacing-and-confirming is the faithful reading. The bounded first slice (D3) follows the campaign discipline of one worked case grounded in the current authority (721,70, not the stale 600 — F5, `aeat-safety-legal-gates`), with the framework generalising to the remaining comunidades and the international box as later enrollments.

## Consequences

- Closes #550 for the Madrid nacimiento/adopción box and establishes the reusable auto-trigger framework (multi-year window helper, unidad-familiar aggregation, income double-limit gate, CCAA-scoped amount parameter) that unblocks every future autonomic-deducción auto-trigger ask.
- The compute logic is deliberately split across a Python injector and a registry formula; a reader must know both surfaces to trace one deducción. This is the accepted cost and matches the existing marriage/menores-3 precedent.
- The unidad-familiar limit is only as complete as the app's spouse-income data (F9); until that is confirmed, the trigger is advisory-only for multi-member units — an honest gap, not a silent one.
- The 721,70 figure and its binding provision must be operator-re-stamped before the value is treated as filing-grade authority; the first slice ships agent-prepared grounding.
- No live-write, no new source kind, no new CLI root; the change is additive to the registry and one application injector, gated by the existing calculate/verify surface.

## Codification candidates

Deferred to review: if the Python-injector-plus-registry-formula split proves the durable pattern for autonomic deducciones across a second CCAA enrollment, a rule (e.g. `autonomic-deduccion-splits-derived-count-from-registry-amount`) may be promoted. Not codified on first encounter, per `vaultspec-codify`.
