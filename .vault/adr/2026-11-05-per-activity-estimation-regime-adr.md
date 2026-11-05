---
tags:
  - '#adr'
  - '#per-activity-estimation-regime'
date: '2026-11-05'
modified: '2026-11-05'
body_schema: 'body-v2'
body_hash: 'sha256:40b6b3c74599ba748107fa8d4f0991d2a6feea4bb230883597f743fe9202d5ed'
related:
  - "[[2026-11-05-per-activity-estimation-regime-research]]"
  - "[[2026-11-05-per-activity-estimation-regime-reference]]"
  - "[[2026-07-26-multi-activity-profile-adr]]"
  - "[[2026-08-07-calculation-chain-integrity-activity-type-placement-adr]]"
  - "[[2026-08-04-profile-derived-selectors-adr]]"
---

# `per-activity-estimation-regime` adr: `Hold the IRPF estimation regime on each activity, with the taxpayer-wide field as a derived projection` | (**status:** `accepted`)

Accepted 2026-11-05: operator approval relayed by FRONTEND-2, 2026-11-05, as written, including the removal of the `directa_normal` applicability default and taking on the indexed-row writer layer as step 1.

## Problem Statement

The profile states the IRPF estimation method once per taxpayer: `irpf.estimation_regime` is a single dated enum. The law selects the method per activity and allows two methods in one ejercicio when a new activity starts. Under RIRPF art. 35, earlier activities stay in objetiva while the new one is in directa; under art. 28.3, they stay in simplificada while the new one is in normal. Modelo 100 records activities by method (`ActividadEstDirecta`, `ActividadEstObj`). That year cannot be stated today. The 2025 Anexo D inventory resolver refuses it safely, but other readers answer it wrongly. The prefill drops Modelo 130 or Modelo 131 when both are due, casilla 0169 and the amortisation modality are decided taxpayer-wide, and applicability reads an absent regime as `directa_normal` (`2026-11-05-per-activity-estimation-regime-reference`). The operator ruled on 2026-11-05 that this decision should be made now. Code waits for approval, after cohort 10, the M10 slot and the FIXTURES merge.

## Considerations

- The fact is per activity. Under RIRPF art. 32.1, objetiva applies "a cada una de las actividades… aisladamente consideradas" (`2026-11-05-per-activity-estimation-regime-research`).
- The incompatibility (LIRPF art. 31.1.3ª.a, RIRPF arts. 28.3 and 35) makes a uniform method the steady state. The mixed state is lawful only in the start year, only for the activities already running before the new one, and it ends on 1 January of the next year (art. 34.1–34.3) (same research).
- In the lawful direction, the mixed state is not an operator choice. A shape the law forbids must refuse, not be accepted as declared.
- The return already carries the method per activity, so a per-activity profile fact maps one-to-one onto the form.
- 14 application and domain modules plus the 131 deadline predicates read the scalar. Some ask a per-activity question (Anexo D rows, asset disposal route, amortisation modality, 347 scope); others ask whether any activity in force in a period is in method X (130/131 obligations, prefill, advisories) (reference).
- The activities section is already declared repeatable and effective-dated, and `profile_section_rows` reads its rows. No indexed-row writer is established, and `2026-07-26-multi-activity-profile-adr` (proposed) owns that gap.
- `2026-08-04-profile-derived-selectors-adr` (accepted) already provides derived profile paths that refuse operator writes and are computed at calculation time.

## Considered options

- **A. Keep the taxpayer-wide scalar and add a per-activity override** for the new activity in a start year. Rejected. It creates two answers to one question: which value wins must be ruled at every one of the 14 readers, and an override left in place after the start year silently creates a mixed state the law forbids.
- **B. Keep the scalar and add a dated "art. 35 exception" fact naming the new activity.** Rejected. It encodes the exception rather than the fact. It also cannot represent the art. 28.3 normal/simplificada case without a second exception field, and it still leaves the form's per-activity occurrences derived from a taxpayer-level guess.
- **C. Hold the method on each activity row, and make the taxpayer-wide view a derived reading with typed uniform, mixed and undeclared states.** Chosen.
- **D. Do nothing and keep refusing.** Rejected by the operator's ruling. The refusal is safe only in the inventory resolver; the other readers misreport a lawful year.

## Constraints

- Supported years, tokens and vocabulary come only from the governed sources (`supported-filing-years.toml`, `0125-irpf-regime-vocabulary.toml` through `irpf_regimes.py`). No consumer or test redeclares them.
- This record depends on the indexed-row writer and index-aware reading of `2026-07-26-multi-activity-profile-adr`. By the operator's approval, the writer layer of its Implementation is step 1 here, unchanged. Its principal-activity and field-set rulings are not needed here and are not adopted.
- `2026-08-04-profile-derived-selectors-adr` governs the retired scalar path: derived, write-refused, computed. Nothing here amends it.
- `2026-08-07-calculation-chain-integrity-activity-type-placement-adr` (proposed) places the activity type on the same row. The two are compatible, and the row gains both fields if both are accepted.
- Persisted profile facts are private custody. The migration runs through the profile write funnel with revision guards and an event, never as a raw store rewrite.
- No product code until operator approval, and not before cohort 10's verdict, the M10 slot and the FIXTURES merge.

## Implementation

We will make the estimation method a field of each activity row and replace every read of the taxpayer-wide scalar with one typed reader.

**Schema.** Add `activities.<n>.estimation_regime`: an enum over the governed vocabulary, `effective_dated`, carrying `model_selectors` and the legal refs of the scalar plus `rd-439-2007:art-28`, `art-32`, `art-34` and `art-35`. Add `activities.<n>.start_date`, the censal alta of that activity (RD 1065/2007 art. 9). The exception is defined by when each activity started, which the single `censo.activity_start_date` cannot say for two activities. `irpf.estimation_regime` becomes a derived path under `2026-08-04-profile-derived-selectors-adr`. Operator writes to it refuse, naming the activity rows as the surface to edit.

**One reader.** An application-layer reader, `estimation_regimes_in_force(record, period)`, samples the period on fact boundaries the way `inventory.py:126-140` does now and returns exactly one of:

- `no_activities`;
- `undeclared`: some row in force has no method, naming the rows;
- `uniform(method)`;
- `mixed(rows by method)`: only in a shape the law admits;
- `incompatible`: a refusal naming the rows and the article.

A mixed state is admitted only when the activities in the dragging method (directa against objetiva under art. 35; normal against simplificada under art. 28.3) all started within the ejercicio and after every activity in the other method, which must have started earlier. Any other mix, including one carried into the next ejercicio, reads `incompatible`. The reader never defaults a missing method. The `applicability_models.py:450` fallback to `directa_normal` is removed in the same change, and an absent method becomes an incomplete applicability.

**Consumers.** Each of the 14 readers asks the reader the question it actually has:

- Per activity: the M100 activity occurrences route each row to `ActividadEstDirecta` or `ActividadEstObj` by its own method. The Anexo D inventory counts rows whose method is direct, which replaces the inference from the taxpayer scalar. The asset disposal route and the amortisation modality read the method of the asset's own activity. The 347 scope reads the method of the invoice's activity and refuses in a mixed year when an invoice names no activity.
- Any activity in the period: the 130/131 obligations, the prefill (which stops excluding the other modelo when mixed), the calendar warning, the explain key and both advisories.
- Casilla 0169 is stated when any activity in force is direct, because the election is per return.

The 131 deadline predicates move from `irpf.estimation_regime equals objetiva` to a condition over the regimes in force in the window: a new `includes` operator on a derived `irpf.estimation_regimes_in_force` path. The change is authored at the earliest edition that carries the predicate and inherited, per the registry delta rule. Whether 130 and 131 are both due for the same quarter in a mixed year (RIRPF arts. 110–111) is a grounding item that must close before this step ships.

**Carry-over of existing profiles.** A journaled, revision-guarded profile migration works through every stored `irpf.estimation_regime` fact. For each activity row in force during that fact's validity, it writes `activities.<n>.estimation_regime` with the same value over the intersection of the two validity intervals. An undated scalar maps to an undated row fact. If a profile holds a scalar and no activity row, the value goes to row `0`; that row then reports its required `description` as missing through the existing completeness check rather than inventing one. Days a row is in force with no scalar stay undeclared. The migration is idempotent, records one event, and refuses rather than overwrites a row that already states a different method. The retired scalar facts stay in history; the derived path computes from the rows. `start_date` is not inferred: a profile that needs it for a mixed year reports it missing.

**Surfaces.** The wizard asks the method per activity row. A "same for all activities" answer writes one fact per row. Words, vocabulary and refusals come from the backend; frontends render them.

**Proof.** Each reader is tested through the real resolver for uniform, undeclared, lawful-mixed (art. 35 and art. 28.3), next-year-carried-mixed (refuses) and new-activity-under-directa-dragging (Manual Ejemplo 1, where no mix is admitted) cases. Every supported year comes from the registry envelope. `just check-registry`, `just check-bindings` and the registry populations stay green.

## Rationale

The knockout is the law's own unit. Art. 32.1 selects objetiva per activity, and the return records each activity under its method. A taxpayer-wide fact can only ever be a projection, and treating the projection as the fact is what makes the 14 readers wrong in the one year the law allows a difference. Options A and B keep the projection as the fact and patch around it, so every reader must still learn the exception. Option C states the fact once, makes uniform the common derived answer, and places the incompatibility rule in one reader where it refuses in law's terms. That reader also removes an existing default that states a method the taxpayer never declared.

## Consequences

- A lawful start year calculates: both activity occurrences fill, both quarterly modelos can be scheduled, and the Anexo D inventory stops refusing a correctly stated profile.
- An unlawful mix, including the start-year mix left unchanged the next year, now refuses with the article named instead of being read as whatever the scalar said.
- Removing the `directa_normal` default changes behaviour for profiles with no stated method: modelos that applied by default become incomplete until the method is stated. This is accepted as correct, but it will surface on existing fixtures.
- This is a persisted schema change with a data migration. Its risks are the indexed-row writer it depends on and a partial reader migration. A reader left on the derived scalar reads `mixed` as absent, so the sweep must be complete and is verified by grep plus the reference's inventory.
- Open grounding before code: whether 130 and 131 are both due in a mixed year, and whether Modelo 036/037 records the method per activity, which would let the censal cotejo adopt it later.
- Reconsider if AEAT or the BOE allow a lasting mix of methods outside a start year, or if the form stops recording activities by method.
