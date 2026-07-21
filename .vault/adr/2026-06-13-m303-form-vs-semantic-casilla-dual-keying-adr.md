---
tags:
  - '#adr'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-06-09-modelo-iva-routing-carry-adr]]"
  - "[[2026-04-17-modelo-303-formulas-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-06-04-m303-form-vs-semantic-casilla-dual-keying-research]]"
  - "[[2026-06-01-m303-iva-resultado-semantic-casilla-mismatch-research]]"
---

# `m303-form-vs-semantic-casilla-dual-keying` adr: `M303 official Diseno box population via semantic projection (Stage 2)` | (**status:** `accepted`)

This ADR amends and extends the accepted 2026-06-01 dual-keying ADR. It supersedes that ADR's stale Finding A (corrected below) and authorises Stage 2 of the official-Diseno box wiring. The Stage 1 advisory floor (calculate-path advisory plus two ADVISORY verify predicates) shipped at commit 330ab6771; this ADR specifies the mechanism that POPULATES the official numbered boxes so the operator transcribes real cuota rather than zeros, and the verify-gate transition that follows. Status is proposed: the operator ratifies before any Stage-2 code lands. No code is changed by this ADR.

## Problem Statement

The Modelo 303 `2023-y-siguientes` revision carries two casilla layers in one revision:

- A **semantic aggregate layer** -- `iva.repercutido.general`, `iva.soportado.interiores`, `iva.autorepercutido.intracomunitaria`, `iva.cuota-devengada-total`, `iva.cuota-deducible-total`, `iva.resultado-regimen-general`, `iva.resultado`, etc. These rows are `input_kind = "bound"` (ledger-fed) or `input_kind = "computed"` (formula-fed) and carry value on a ledger-driven calculate.
- An **official Diseno-de-Registros numbered layer** -- rows whose `id` is the bare AEAT field number (`"01"` through `"77"`, plus `"109"`, `"110"`, `"150"` through `"170"`), each stamped `semantic_role = "dr303_NN"` and `input_kind = "manual"` with no binding and no formula. These are the field positions the AEAT sede (and the BOE fichero) actually read.

On a ledger calculate the engine folds real cuota into the semantic layer, so `iva.cuota-devengada-total` is positive, while every official numbered cuota box (`09`, `13`, `27`, `29`, `33`, `37`, `45`, ...) stays zero. An operator transcribing the official boxes to the sede sees zeros -- a silent under-declaration (`no-silent-under-declaration`): the human files the numbered layer, all zero, outside the application.

The defect is observable end-to-end in the export adapter. The BOE/fichero export field `modelo-303-page-01-casilla-27` (`kind = "casilla"`) references `casilla = "27"` (the manual numbered box) -- which is zero -- so the export artifact writes zero into the official "Total cuota devengada" position. Yet the sibling field `modelo-303-page-01-casilla-46` references `casilla = "iva.resultado-regimen-general"` (the semantic id) and therefore carries value. The two export fields are wired inconsistently to two different layers; that inconsistency is the root cause this ADR resolves.

Stage 1 (commit 330ab6771) made the contradiction non-silent by emitting a calculate advisory and two ADVISORY `implies_any_nonzero` verify predicates (`iva.cuota-devengada-total` implies at least one of `03/06/09/11/13`; `iva.cuota-deducible-total` implies at least one of `29/33/37`). Stage 2 must actually POPULATE the numbered boxes -- but the naive route (binding each numbered box to `ledger_iva_aggregation`) would select the SAME ledger observations the semantic layer already aggregates, producing a second aggregation path for one value. That violates `one-aggregation-path-pull-equals-calculate`, `calculation-source-canonical-mechanism`, and the dual-modelling prohibition in `relation-slot-bindings-declare-relation-source`. The prior chain-rewire attempt under task #111 (4b0010a0c) regressed and was reverted (64baa15a6); Stage 2 must not repeat that class of error.

## Considerations

### Correction of Finding A (supersedes the 2026-06-01 ADR's Finding A)

The accepted 2026-06-01 ADR's Finding A states: "There are no purely form-numbered ids in this revision." That claim was true on 2026-06-01 but is **stale against HEAD**. Verified read-only against `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.part-001.toml` and `0001-casillas.part-002.toml` on 2026-06-13:

- **93** casilla rows carry `semantic_role = "dr303_NN"` (36 in part-001, 57 in part-002; the count is 36 + 57 = 93). Every one of these rows has `id` equal to its bare AEAT field number (e.g. `id = "01"`, `id = "09"`, `id = "27"`, `id = "77"`, `id = "150"`), `input_kind = "manual"`, no `binding`, no `formula`, and an `export_refs` entry of the shape `modelo-303-page-NN-casilla-NN`. These ARE purely form-numbered ids, added in the 2026-06-10 registry pass that post-dates the 2026-06-01 ADR.
- The semantic layer (ids of the shape `iva.*`) coexists in the same revision and is the layer the engine populates.

The corrected Finding A reads: **The M303 2023-y-siguientes revision carries BOTH a semantic-keyed layer (`id = "iva.*"`, bound/computed) AND a purely form-numbered Diseno layer (`id = "NN"`, `semantic_role = "dr303_NN"`, manual, 93 rows). The single-axis "id is always semantic" framing of the prior Finding A no longer holds.** The prior ADR's load-bearing D1/D2 contract -- the engine resolves casilla state only by `casilla.id`, never by `casilla.number` -- is UNAFFECTED and still holds: the numbered boxes are addressed by their `id` (which happens to equal the number), and the `number` field is still never the engine's lookup key.

### The numbered boxes are presentation projections, not a second aggregation surface

Each cuota-bearing numbered box restates a value the semantic layer already computed from one canonical aggregation. Box `09` ("IVA devengado RG tipo general 21pct - Cuota") restates the cuota already aggregated into `iva.repercutido.general`; box `27` ("Total cuota devengada") restates `iva.cuota-devengada-total`; box `45` ("Total a deducir - Cuota") restates `iva.cuota-deducible-total`. The number on the sede is a **copy of the already-computed semantic value**, not an independent re-aggregation from ledger observations. Therefore the canonical mechanism to populate a numbered box is a **projection (single-source copy) of its semantic casilla**, evaluated AFTER the semantic value is computed -- never a fresh ledger aggregation.

### The registry formula vocabulary already supports a single-source projection

`FormulaDefinition` (`src/aeat/domain/calculations/registry/_schema.py`) is `id, target, expression` where `expression` is a `FormulaExpression`. The formula evaluator's leaf handler (`_evaluate_leaf` in `_formula_runtime.py`) resolves a leaf whose `expression.casilla = "<id>"` to `values["<id>"]` -- i.e. a `FormulaExpression` that is a bare single casilla-id reference evaluates to that casilla's already-computed value. A numbered box flipped from `input_kind = "manual"` to `input_kind = "computed"` with `formula = "<projection-id>"`, where the projection's `expression` is the single leaf referencing `iva.<source>`, is exactly a copy. The engine evaluates formulas in topological order and guards "casilla referenced before evaluation", so the semantic source is computed before the box projection -- no ordering hazard. This is the SAME primitive the existing `iva.cuota-devengada-total` formula uses to fold its constituents; no new schema field, op, resolver, or source kind is introduced.

## Constraints

- **ONE-AGGREGATION-PATH / NO DUAL-MODELLING.** The projection formula MUST reference the semantic casilla id as its single operand. It MUST NOT carry a `binding` to `ledger_iva_aggregation` or any ledger source, and MUST NOT re-select ledger observations. A second ledger aggregation for a value the semantic layer already owns is precisely the violation of `one-aggregation-path-pull-equals-calculate` and `calculation-source-canonical-mechanism` this ADR exists to avoid. Because pull and calculate share the one formula-evaluation path, a projection formula is identical across both transports by construction.
- **PROJECTION IS NOT A RELATION OR A PREVIOUS_FILING CARRY.** A same-revision intra-modelo copy is not a cross-modelo fold-in (relation), not a cross-period carry (`previous_filing`), and not a cross-member fan-in (`per_grupo_member`). It is a `computed` formula leaf. The numbered box MUST NOT declare `source = "relation_prefill"` or `source = "previous_filing"`; those are binding source kinds and the box has no binding. `relation-slot-bindings-declare-relation-source` is satisfied vacuously (no binding), and the collision gate it describes does not apply.
- **REGISTRY-CALCULATION-LEGAL-GROUNDING.** Each box-to-semantic projection MUST carry the numbered box's existing `legal_refs` (LIVA art. 88 for devengado cuotas, art. 92 for deducible cuotas, art. 84 for inversion del sujeto pasivo), which already match the semantic source's grounding, AND the new `FormulaDefinition` MUST itself carry those `legal_refs` per the formula-grounding requirement. No projection may be authored for a box whose semantic source is itself ungrounded or absent.
- **MODELO-EXPORT-MIRRORS-OFFICIAL-STRUCTURE.** After Stage 2, every export field of `kind = "casilla"` that today points at a numbered box (`casilla = "27"`) keeps pointing at the numbered box -- but that box now carries the projected value, so the export reads value, not zero. The export layer's inconsistency (some fields point at the numbered box, some at the semantic id) is resolved by making BOTH layers carry the same value via projection, so whichever the export field references, it reads the correct figure. The workbook/BOE parity gate must continue to pass.
- **NO FABRICATION / SELECTIVE MAPPING.** Only cuota-bearing boxes whose value equals a single computed semantic casilla are projection candidates. **Base** boxes (`01`, `04`, `07`, `10`, `12`, `28`, `30`, ...) and **tipo (percentage)** boxes (`02`, `05`, `08`, `23`, ...) have NO ledger-derived semantic source in the current engine and MUST stay `manual`. A box with no exact single-source semantic equivalent is NOT force-fitted; it remains operator-entered and continues to surface under the Stage 1 advisory until a real semantic source exists. Regimen-simplificado boxes (`47` onward) and boxes grounded only in the eight LIVA articles still absent from the corpus (per the 2026-06-09 routing ADR) are out of scope until their grounding lands.
- **PARENT-FEATURE STABILITY.** The semantic aggregation layer (the bindings and formulas that compute `iva.cuota-devengada-total`, `iva.cuota-deducible-total`, `iva.resultado-regimen-general`) is the load-bearing parent. Stage 2 adds copies downstream of it; it does not touch the parent aggregation. The resultado-chain numbered boxes that are ALREADY computed/bound (`46`, `64`, `65`, `66`, `69`, `71`) are out of scope -- they already carry value.

## Implementation

This ADR authorises the Stage-2 shape; a separate plan and executor land the registry edits. No code or registry TOML is changed by this ADR.

### Box-to-semantic-source projection map (the authorised Stage-2 wiring)

Each box below flips from `input_kind = "manual"` to `input_kind = "computed"`, gains `formula = "modelo-303-dr303-<NN>-projection"`, and that `FormulaDefinition` has `target = "<NN>"`, an `expression` that is the single casilla leaf naming the semantic source id, and `legal_refs` copied from the box row. The cuota-bearing devengado and deducible cuota boxes, plus the two official totals, are the in-scope set:

- Devengado regimen-general cuotas:
  - `09` (RG 21% cuota) from `iva.repercutido.general` (LIVA art. 88)
  - `06` (RG 10% cuota) from `iva.repercutido.reducido` (LIVA art. 88)
  - `03` (RG 4% cuota) from `iva.repercutido.super-reducido` (LIVA art. 88)
- Devengado inversion del sujeto pasivo cuotas:
  - `11` (AIC bienes y servicios cuota) from `iva.autorepercutido.intracomunitaria` (LIVA art. 84). Note the AIC devengado/deducible parity casillas net to zero and are NOT the projection source for the resultado; box `11` projects the devengado cuota the operator must show on the sede.
  - `13` (otras ops inversion sujeto pasivo, excl. intracom. cuota) from `iva.autorepercutido.interior.devengado` (LIVA art. 84)
- Devengado total:
  - `27` (Total cuota devengada) from `iva.cuota-devengada-total` (LIVA art. 88)
- Deducible cuotas:
  - `29` (interiores corrientes cuota) from `iva.soportado.interiores` (LIVA art. 92)
  - `33` (importaciones bienes corrientes cuota) from `iva.soportado.importaciones` (LIVA art. 17 + art. 92)
  - `37` (AIC corrientes cuota) from the single deducible-cuota equivalent the executor confirms against the box label and the 2026-06-09 routing decisions (LIVA art. 92). The executor MUST verify the exact 1:1 source against the box label before wiring; if no exact single source exists, leave `37` manual and keep the Stage 1 advisory.
- Deducible total:
  - `45` (Total a deducir cuota) from `iva.cuota-deducible-total` (LIVA art. 92)

Boxes whose semantic source is the eight-LIVA-article-blocked categories (per the 2026-06-09 ADR's Tier-2 gate) are excluded until that grounding lands. Base and tipo boxes are excluded permanently (no semantic equivalent). The executor produces the exact authoritative list as a reference document, cross-checked box-label-against-semantic-label, before editing TOML.

### Verify-gate transition (Stage 1 advisory to Stage 2 consistency)

Once a box is projection-populated it can no longer be silently zero while its total is positive, so the Stage 1 `implies_any_nonzero` ADVISORY for that constituent set is satisfied by construction. The Stage 2 verify shape replaces the unpopulated-advisory with a **consistency predicate**: for each projected box, assert the box value equals its semantic source (an equality/consistency check that the projection did not drift). If the existing DSL lacks an equality operator, the executor either adds one (a small, separately-grounded DSL extension) or retains the projection as self-evidently consistent (the copy cannot diverge from its source within one evaluation) and RETIRES the corresponding Stage 1 advisory for the now-populated constituents. The calculate-path advisory in `_official_box_advisory.py` continues to fire ONLY for the boxes that remain manual (base/tipo/blocked), so it narrows rather than disappears. The advisory module needs no change -- it reads the same ADVISORY predicates, and predicates for populated constituents stop firing because the constituents are now non-zero.

### What does NOT change

- No new binding, source kind, resolver, relation, or `previous_filing` carry.
- The semantic aggregation layer and its formulas are untouched.
- The already-computed/bound resultado-chain boxes (`46`, `64`, `65`, `66`, `69`, `71`) are untouched.
- `casilla.number` is still never an engine lookup key; D1/D2 of the prior ADR still hold.

## Rationale

The projection mechanism is the only candidate that does not create a second aggregation path. A ledger binding on each box would re-aggregate the same observations the semantic layer owns (dual-modelling, the reverted-#111 class). A relation would mis-declare an intra-revision copy as a cross-modelo fold-in. A `previous_filing` carry would mis-declare it as a cross-period carry. A single-leaf computed formula referencing the semantic casilla id is a pure copy evaluated after the source, using a primitive the registry and `_formula_runtime.py` already implement and the existing `iva.cuota-devengada-total` formula already exercises. Because pull and calculate evaluate the one formula graph, the projection is identical across both transports, satisfying `one-aggregation-path-pull-equals-calculate` by construction rather than by an added parity test. The selective mapping (only cuota boxes with an exact single semantic source) honours `no-silent-under-declaration` without fabricating a source for base/tipo/blocked boxes, which correctly stay manual and advisory-covered.

## Consequences

- **Gains.** The operator transcribes real cuota to the sede; the BOE/fichero export writes the real figure into the numbered positions regardless of which layer the export field references; the export-layer inconsistency (field to numbered box vs field to semantic id) is neutralised because both layers carry the same value. The silent-zero export under-declaration is closed for the in-scope cuota boxes.
- **Honest difficulty.** The box-to-semantic map is partial. Base and tipo boxes, regimen-simplificado boxes, and boxes blocked on the eight absent LIVA articles stay manual; the operator still hand-enters those, and the Stage 1 advisory still covers them. This ADR does not claim full official-box population -- only the cuota-bearing single-source subset.
- **Verification subtlety.** A projection copy cannot drift from its source within one evaluation, so a consistency predicate over a projected box is near-tautological; the value of keeping it is to catch a future mis-edit (a box re-flipped to manual, or a projection pointed at the wrong source). The executor decides per box whether to author the consistency predicate or simply retire the now-satisfied Stage 1 advisory; both are acceptable, and the choice is a plan-level detail, not an ADR ruling.
- **Pathway opened.** The same projection pattern generalises to any future modelo that carries a parallel official-numbered layer over a semantic aggregate layer (the two-layer pattern the Stage 1 advisory module already anticipates in its docstring).

## Open questions for the operator

1. **Ratification of the selective scope.** This ADR populates ONLY cuota-bearing boxes with an exact single semantic source and leaves base/tipo/blocked boxes manual. Confirm that partial population (rather than forcing every box) is the intended Stage-2 scope.
2. **Box 37 source.** Box `37` (AIC corrientes deducible cuota) has two plausible single sources in the current semantic layer (the interior-deducible autorepercutido casilla vs the AIC-deducible parity casilla). The executor will pin the exact 1:1 source against the box label before wiring; flag if you want a specific source mandated now.
3. **Verify transition style.** Prefer (a) authoring an equality/consistency predicate per projected box (requires a DSL equality operator, separately grounded), or (b) retiring the now-satisfied Stage 1 advisory for populated constituents and relying on the copy being inherently consistent. The ADR permits either; name a preference if you have one.
4. **Prior-ADR disposition.** This ADR corrects Finding A of the 2026-06-01 ADR in prose. Confirm whether you also want the 2026-06-01 ADR's body edited to stamp Finding A as corrected/superseded by 2026-06-13, or whether the cross-reference in this ADR is sufficient.

## Ratification

The operator ratified this ADR on 2026-06-13 and authorised the recommended defaults. Status moves `proposed` -> `accepted`. The four open questions are resolved as follows.

1. **Population scope (Open Question 1) -- selective in-scope set ratified.** Populate ONLY the listed cuota boxes via single-source projection: devengado cuotas `09` / `06` / `03`, inversion-del-sujeto-pasivo cuotas `11` / `13`, the devengado total `27`, deducible cuotas `29` / `33` / `37`, and the deducible total `45`. Base boxes, tipo (percentage) boxes, the boxes blocked on the eight LIVA articles still absent from the corpus, and the regimen-simplificado boxes (`47` onward) STAY `manual` and remain advisory-covered. They are NOT force-fitted to any semantic source. Partial population is the intended Stage-2 scope.

2. **Box 37 source (Open Question 2) -- executor pins the exact 1:1 source; no force-fit.** The executor pins box `37`'s deducible source from the M303 registry by label-match against the box's own label and the semantic casilla self-documentation. The registry carries a genuine self-label collision: BOTH `iva.autorepercutido.intracomunitaria.deducible` (label "...oficial casillas 36/37") AND `iva.autorepercutido.interior.deducible` (label "...oficial casilla 37") name casilla 37. Box `37`'s label is "IVA deducible adquisiciones intracomunitarias corrientes - Cuota", which is the AIC (adquisiciones intracomunitarias) leg, so the label-exact source is `iva.autorepercutido.intracomunitaria.deducible`. The executor MUST confirm this against the box label and the 2026-06-09 routing decisions before wiring. If the executor judges the two candidates genuinely ambiguous after that confirmation, box `37` stays `manual` and the Stage 1 advisory continues to cover it -- no guess.

3. **Verify transition (Open Question 3) -- NARROW the advisory AND add a consistency predicate.** Both moves are authorised. The Stage 1 ADVISORY `implies_any_nonzero` predicates are NARROWED so each constituent list retains only the boxes that REMAIN manual after Stage 2 (so the advisory keeps firing for base/tipo/blocked boxes and any box left manual, e.g. `37` if deferred) and drops the now-populated constituents. Because the advisory module reuses these same predicates as its single source of truth, narrowing the predicate lists narrows both the verify finding and the calculate advisory in lock-step. Separately, a consistency predicate (numbered box value == its semantic source value) is added for each populated box. The DSL has no equality operator today (only `implies_nonzero` / `implies_any_nonzero`); the executor adds a small, separately-grounded equality/consistency operator to the predicate DSL (registry `KNOWN_VERIFICATION_PREDICATE_OPERATORS`, the `_validate_surfaces` gate, and the `_verification_actions` evaluator) to express it. The consistency predicate is near-tautological within one evaluation (a copy cannot drift from its source); its value is catching a future mis-edit (a box re-flipped to manual, or a projection pointed at the wrong source).

4. **Prior-ADR disposition (Open Question 4) -- superseding-pointer added to the 2026-06-01 ADR body.** A superseding-pointer note is added to the 2026-06-01 ADR body flagging its Finding A as corrected/superseded by this 2026-06-13 ADR.

## Codification candidates

- **Rule slug:** `official-numbered-boxes-project-semantic-values`.
  **Rule:** A modelo official-Diseno numbered box that restates an already-computed semantic aggregate MUST be populated by a single-source projection formula (`input_kind = "computed"`, a `formula` whose expression is the one semantic casilla-id leaf), never by a second ledger binding or aggregation, so one value has exactly one aggregation path. (Promote only after Stage-2 lands and the parity gate is green.)
