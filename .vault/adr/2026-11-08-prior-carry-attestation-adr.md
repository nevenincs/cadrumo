---
tags:
  - '#adr'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:8ae8cbaa01ba8ba90aab91a30d9d3490d35e7e52b67b66e7af482cb69e44303e'
related:
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-06-13-first-filer-attestation-adr]]"
  - '[[2026-11-08-prior-carry-attestation-reference]]'
---

# `prior-carry-attestation` adr: `operator-attested zero for an absent prior-year carry` | (**status:** `accepted`)

## Problem Statement

A Modelo 100 carries pending negative general bases from earlier ejercicios
(boxes 1380, 1382, 1385 and 1388, fed by the bindings declared in
`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:47`
and `:1084` onward). Those carries exist only when a negative general base
liquidable arose in one of the four previous ejercicios (Ley 35/2006 art. 50.3),
so when no earlier return is held they are unknown, never zero. APP-QA D33 found
a filer with no earlier Modelo 100 in the app left with four required boxes and
no way to state that nothing is pending: typing 0 over each box was the only
path, and it reads as a figure the filer entered, not as the statement it is.

## Considerations

- Pending carries are a fact of one declaration's ejercicio. A profile fact would
  carry an absence into later years, where a later negative base can make it false.
- Absent, unknown and proven-zero stay distinct (rule 07): a typed 0 and "nothing
  is pending" must remain distinguishable by verification.
- A later captured earlier return that shows an amount must reach the filer as a
  structured finding. The existing `precedence_tier_divergence` disagreement
  already does this for a caller value against a filed figure
  (`src/cadrumo/domain/modelos/calculation_revision_sources.py:265`).
- The backend serves every word; the window renders.
- The activity-start scoping of `2026-06-13-first-filer-attestation-adr` covers a
  first filer. This record covers a filer whose earlier returns exist outside the app.

## Considered options

- Profile fact ("no pending negative bases"): rejected by the coordinator's ruling;
  it is per-ejercicio, and it would also need a `schema.toml` change.
- Typed 0 on each box: kept as a plain operator value, but it cannot be told apart
  from an attestation and offers no door.
- Served per-declaration form action that records an operator-attested zero on each
  carry: chosen.

## Constraints

- Coordinator ruling of 2026-11-08 (the authorization for this record): use the
  served form action, not a profile fact; record each of the four carries as an
  operator-attested zero on that work unit, with operator-entry provenance and
  revision-bound; keep it distinct from absent and unknown; a contradicting captured
  prior-year amount reaches the user as a structured finding; the words come from
  the backend; no `schema.toml` change.
- Amends `2026-08-24-modelo-edit-contract-adr` D4 by one binding intent kind.
- Revisions stored before this record keep their identity and mean "no attestation".

## Implementation

We will add a binding edit intent, `attest_no_amount`, that the form serves as one
action per declaration over its unresolved earlier-ejercicio carries, and record
its effect on the revision's operator layer as an attested zero.

- Scope: the registry declares which carries take the statement. A binding names
  its family in `absence_attestation`, a closed set whose one member is
  `renta_negative_general_bases_pending`
  (`src/cadrumo/domain/calculations/registry/binding_absence_attestation.py`). The
  schema refuses it on any binding that is not a decimal read from an earlier filing
  (`src/cadrumo/domain/calculations/registry/schema.py:292`). The four Modelo 100
  carries declare it in the 2022 bindings file, and later editions inherit it. No
  other modelo declares a family, so a Modelo 130 or 303 earlier-filing binding is
  never offered the statement.
- Intent: `ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT` carries no value. It is
  admitted only on a writable binding override whose binding declares a family.
  It sets the operator override to zero and marks the binding attested.
  `SET_OVERRIDE_VALUE` and `REMOVE_OVERRIDE` on that binding withdraw the attestation.
- Persistence: `CalculationOperatorLayer` gains `attested_binding_ids`, which must be
  a subset of its binding overrides holding zero. Its identity payload names the set
  only when it is non-empty, so stored revisions keep their identity.
- Resolution and verification: an attested binding resolves to zero at the caller
  tier with attested provenance. The earlier-filing resolver states it as attested
  by the filer, never as unrecorded. A typed value stays an operator entry.
- Contradiction: when an earlier return is later stored with a different amount,
  the existing `precedence_tier_divergence` disagreement is raised against the
  attested zero, with its served accept or revise actions.
- Form: the work form serves one action per declared family, with its action,
  statement and per-carry effect words and the binding addresses it attests. It
  serves the action while a carry of that family is neither resolved, entered nor
  attested. The window stages one `attest_no_amount` intent per address and applies
  them through the ordinary review. The field of an attested carry carries the
  family as `stated_absent` and served origin words, so it never reads as a zero
  that was typed.
- Evidence: real resolvers and real stores, for every Modelo 100 year the registry
  envelope admits.

## Rationale

The statement belongs to the declaration and its revision, where the edit contract
already binds operator values to a baseline and records them in the operator layer.
One intent with a recorded attested set keeps "nothing pending" distinct from a
typed zero, and reusing the disagreement finding makes a later contradiction visible
without a second mechanism.

## Consequences

- The edit contract, the operator layer and the work form change shape. The
  operation contract manifest and the window's wire types are regenerated.
- A filer can complete a first Modelo 100 in the app without an earlier return,
  and a later capture of that return is checked against the statement.
- Another earlier-filing carry takes the action only through a new registry family
  and its served words. This record scopes it to the Modelo 100 carries that D33 found.
- Amended 2026-11-08 on the coordinator's approval of the registry declaration,
  after the plan-close review found the scope inferred from the source kind.

## Amendment 2026-11-11: absence of pending rental expenses

Accepted 2026-11-11 by CADRUMO-PRIME under the operator's delegation, with the decision `2026-11-11-renta-rental-income-source-adr`. One more absence-attestation family is admitted: `renta_capital_inmobiliario_gastos_pendientes`, at row grain keyed by the property row identity, for absence and for stated amounts (amended 2026-11-11 23:25 on the rental decisions ruling, because situaciones 4 and 5 hold no referencia catastral and it is an editable fact). A first year in the app can then state that a property carries no pending expenses from earlier years into 0103, instead of leaving the box unresolved for want of a return the app does not hold.


## Amendment 2026-11-12: the negative savings balances pending from earlier ejercicios

Accepted 2026-11-12 00:51 by CADRUMO-PRIME with one condition, written in below (ruling: the 00:51 entry of PRIME's rulings log). Proposed in `2026-11-11-prior-carry-attestation-savings-carries-adr`, now retired.

Problem. A Modelo 100 compensates negative savings balances still pending from the four previous ejercicios (LIRPF art. 49.1.a and 49.1.b, `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:838-849`). Anexo C.3 holds them in two sections, ganancias y perdidas patrimoniales (opening rows 1259, 1261, 1264, 1267) and rendimientos del capital mobiliario (opening rows 1272, 1274, 1277, 1280), with the same rows and order in every bundled dictionary. They, their applied and carry-forward rows, and the applied boxes 0439-0455 were free operator inputs: no earlier return fed them and a filer with nothing pending could not say so. This is the gap this record closed for the general bases, in a second place.

Decision. The closed family set gains `renta_negative_savings_capital_income_pending` (art. 49.1.a) and `renta_negative_savings_gains_losses_pending` (art. 49.1.b), two families because the law and the form keep the kinds apart and a filer can hold one without the other. Each is declared on four earlier-filing bindings, one per Anexo C.3 opening row. Intent, operator layer, admission, form action, field origin, disagreement finding and stated-value path are reused as they are. The scope of this record widens from the four general-base carries to these twelve.

Implementation.
- Bindings: each opening row reads the previous return's row one origin year newer, `filing_year_offset` -1, declared once in the edition that declares the general-base carries (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml`, beside :1083-1115); gains and losses 1263, 1266, 1269 to 1259, 1261, 1264 and generated balance 1270 to 1267; capital mobiliario 1276, 1279, 1282 to 1272, 1274, 1277 and 1283 to 1280. No year is written anywhere.
- Absent upstream return: `attest_no_amount` per family, or `attest_prior_value` unchanged under `2026-06-05-cross-period-filing-clean-state-adr` as amended 2026-11-11.
- Applied amounts are fixed at the maximum the year allows (art. 49.2), never chosen, following the manual's Fase 2 (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:39522-39582`). Step 1: each kind's pending balances offset the same kind's positive balance after the current-year cross offset (0429 - 0446 for capital mobiliario, 0424 - 0436 for gains), fixing 0449-0452 and 0439-0442. Step 2: what remains offsets the other kind's remaining positive balance within 25 per cent of it, jointly with the current-year cross offset (0436 or 0446), fixing 0443, 0444, 0445, 0447 and 0453, 0454, 0455, 0448. Each applied box takes the gates `positive_application_le_present_stock` and `application_equals_present_maximum`.
- Cascade: each Anexo C.3 applied row sums its two boxes (for example 1260 = 0439 + 0453, 1273 = 0449 + 0443); each carry-forward row is its opening row minus its applied row; the fourth-year-back row lapses; 1270 and 1283 already compute this year's generated balance, so a return calculated in the application feeds the next one.
- Order among origin years (condition of acceptance): no official text found states the order in which origin years of one kind are applied inside a step; the general-base rows rest on the same unstated order (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/casillas/0001-declarations.toml:1695`). The limit to calculation grade bites only where that order changes a figure: when more than one origin year of one kind holds a pending balance and the step's capacity is smaller than their sum. A saver with one origin year of a kind, or whose capacity covers every pending balance of it, verifies and exports at filing grade. How the condition is detected is the lane's design; it is a typed finding, never a silent choice.
- Surfaces: refusal, statement, effect and origin words served per family; the refusal message map in `src/cadrumo/application/modelo/work_missing_input.py:134-138` gains the import-time completeness check the form maps have; `attest-prior-carries` takes `--family <token>` (a closed choice from the registry family set), agreed with the door's owner on 2026-11-12. Without it the door states every open carry only when exactly one family is open, as today; with two or more open it refuses before staging, in the pre-stage style of `ModeloPriorCarryNothingOpenError`, naming each open family with its own door, and an explicit `--all-families` states every family at once. A caller written when one family existed therefore never zeroes the savings families by default, which would be an attestation nobody made. The result names each family and binding attested; the operation contract manifest is regenerated and the window's type regeneration is recorded as native debt.
- Evidence: real resolvers and stores at every Modelo 100 year the envelope admits; the manual's worked example (`:39608-39692`, savings base 200) as oracle; a two-year cascade; a captured earlier return contradicting an attested zero raises `precedence_tier_divergence`.
- Registry correction landing in the same unit, approved with this amendment but not part of it: the registry's 0460 carried a +0041 term the official BIAHOH expression lacks (2025 dictionary line 784), and 0429/0430 had no source; they are derived from 0041 under art. 49.1.a and 0460 follows the design, fixed at the earliest edition where it is wrong.

Consequences. A saver can complete the savings base with or without an earlier return, and every statement of absence stays distinct from a typed zero. Revisions stored before the amendment keep their identity; an earlier return calculated before the carry-forward rows were computed lacks them, so the next year refuses with the unobserved-filing message until it is recalculated or the figure is stated. The general-base gains carries (Anexo C 1246-1257, art. 48) remain outside this record.

## Amendment 2026-11-12 (b): one statement covers every open family

Accepted 2026-11-12 03:31 by CADRUMO-PRIME (ruling: the 03:31 entry of PRIME's rulings log), with conditions written in below, and amended by PRIME on ACCEPTANCE's objection the same night: no `--all-families`. It replaces two clauses of the Surfaces bullet of the amendment above: "states every open carry only when exactly one family is open" stays, but the door no longer states one family while another is open, and the refusal no longer names each open family with its own door.

Problem. A statement commits only through the edit apply, and the apply's one effect is a fresh calculation (`src/cadrumo/application/modelo/edit_execution.py:662-719`). While any carry of another family is unstated, that calculation refuses with the unstated-carry refusal (`src/cadrumo/application/modelo/calculation_actions.py:961-974`, `src/cadrumo/domain/calculations/registry/formula_initial_values.py:560`), so nothing persists. A filer with no earlier return has every family open at once, because all of them read the same previous return; a door for one family therefore always fails in the main case. The edit preflight never recalculates, so it reads green while the apply refuses. The CLI door and the window share this path.

Decision. One statement covers every open carry family.
- `attest-prior-carries` takes `--family <token>` repeatedly, each a closed choice from the registry's carry families. With no option it states every open carry only when exactly one family is open. There is no option that states every family at once: each family is a separate fact, and a blanket option would let a filer state absence for a family never looked at, an inferred carry.
- A statement that leaves an open family out is refused before staging. The refusal names every missing family and serves a door that includes them: the same command naming every open family with `--family`. No door is served that cannot succeed.
- The window stages every chosen family in one review.
- The edit preflight raises a blocking finding when the staged intents leave an attestable carry open, so the preflight agrees with the apply.
- Conditions of acceptance: every statement and every served door names each open family, each as nothing pending or with its amounts; one statement may state absence for one family and an amount for another; nothing is zeroed by default.

Rejected. Recording a statement while other carries stay unstated would need a revision with unresolved required carries, against the engine contract and the refusal this record rests on. Keeping per-family doors would leave a door that works only for the last open family.

Evidence owed. A filer with three open families commits in one statement; a partial statement is refused before staging with the full door; a mixed statement (absence for one family, an amount for another) commits; the preflight blocks a partial statement.

## Amendment 2026-11-12 (c): the pension-reduction excesses pending from earlier ejercicios

Accepted 2026-11-12 15:14 by CADRUMO-PRIME under the operator's delegation, with four conditions written in below (ruling: the 15:14 entry of PRIME's ADR acceptance log). Proposed in `2026-11-12-prior-carry-attestation-prevision-social-excesses-adr`, now retired. Grounding: `2026-11-12-renta-prevision-social-contribution-source-research`.

Problem. LIRPF art. 52.2 lets a contribution that could not reduce the base, because the general base was insufficient or the percentage limit applied, reduce it in the five following ejercicios. Modelo 100 holds those excesses in Anexo C per contributing member: general social-welfare systems in rows 1284 to 1299 and collective dependency insurance in rows 1300 to 1315 (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:8636-8726`), with opening, applied and closing rows per origin year and a generated row for the year's own excess (1299, 1315). None has a binding or a formula, and without an earlier return the pending amounts are unknown, never zero.

Decision. The closed family set gains `renta_prevision_social_excess_pending` (general systems) and `renta_dependency_insurance_excess_pending` (collective dependency insurance), two families because the kinds carry and apply separately and a filer can hold one without the other. Each is declared on the opening rows of its kind, at row grain keyed by the contributing member, so a joint return keeps each member's excesses apart. Intent, operator layer, admission, form action, door and contradiction finding are those of this record and its savings amendments, unchanged.

Implementation.
- Bindings: each opening row reads the previous return's row one origin year newer (`filing_year_offset` -1), declared once in the earliest edition whose design holds the rows, inherited after. The oldest origin year lapses after its application year.
- Formulas: applied rows in the order the year's text states, closing rows as opening minus applied, generated rows (1299, 1315) as the part of the year's admissible contributions the S40 (a) limit formula could not reduce.
- A pension-reduction remainder never reaches the savings base (LIRPF art. 50).
- Surfaces: refusal, statement, effect and origin words served per family; the two tokens join the `attest-prior-carries --family` choices.
- Evidence: real resolvers and stores for every Modelo 100 year the envelope admits; the manual's worked example for each rule period as oracle; a two-year cascade; a joint return with excesses on one member; a captured earlier return contradicting an attested zero.

Conditions of acceptance.
1. Applied to this record as an amendment, preserving its body; the proposal is retired.
2. Only amounts blocked by insufficient base or by the percentage limit carry; the excess over the absolute limit never carries. The order of application is the official text's for each year, cited per edition; where no text fixes an order and the order changes a figure, the result is calculation grade only.
3. The 2021 employer-contribution split rows (1742 to 1763) are read in the 2021 official design before authoring. A third family is added only if that design carries them as a separate pending amount, and the citation is reported to CADRUMO-PRIME.
4. Depends on S40 (a) and (b): nothing of this amendment lands before S40 (a) is on feature/tui.

Consequences. A filer with or without an earlier return can complete the pension reduction, and nothing pending is never read from an unprinted box. The year's own excess feeds the next return. `PRIOR_CARRY_FAMILIES` and the carry door grow by two families, and the operation contract manifest is regenerated.
