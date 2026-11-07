---
tags:
  - '#adr'
  - '#calendar-obligations'
date: '2026-09-23'
modified: '2026-11-07'
body_schema: 'body-v2'
body_hash: 'sha256:be488202fd77432a48de1451816aef02ac8586e31b31530b0c177325294f512e'
related:
  - "[[2026-09-23-calendar-obligations-holiday-jurisdiction-adr]]"
  - "[[2026-06-30-obligation-coverage-completeness-adr]]"
  - '[[2026-09-23-calendar-obligations-payer-fact-declaration-state-reference]]'
---

# `calendar-obligations` adr: `payer facts carry a declaration state and 136 is scoped per quarter` | (**status:** `accepted`)

Accepted 2026-09-23 on the user's standing pre-approval of this work, relayed by the coordinator for the calendar lane: an explicit taxpayer answer must be able to reach not-applicable, and Modelo 136 must apply only in the quarter a prize was cashed.

## Problem Statement

A payer fact (`src/cadrumo/domain/calculations/registry/applicability_payer_facts.py`) resolves to a plain boolean. `payer_fact_holds` returns `False` both when the taxpayer answered "no" and when nobody asked, so `ModeloApplicabilityRule._payer_fact_result` (`src/cadrumo/domain/calculations/registry/applicability.py`) can only answer INCOMPLETE for a negative. A taxpayer who has answered for Modelos 347, 720 and 721 can therefore never reach NOT_APPLICABLE. Declared-no, undeclared and declared-yes are distinct states, and the engine collapses two of them.

The stored `false` cannot be read as an answer after the fact. The setup question defaults to `"false"` (`src/cadrumo/application/wizard/catalogue.py`, `_confirm`), so a non-interactive setup writes `false` for every payer fact without asking. A stored fact's `source` defaults to `manual_cli` (`src/cadrumo/domain/user_profile/values.py`, `UserProfileFact`), so provenance cannot separate an answer from a default either.

Modelo 136 is owed per quarter, for prizes cashed in the quarter immediately before the window (Orden HAP/70/2013 art. 7, `orden-hap-70-2013:art-7`). Only a taxpayer whose prize was not withheld owes it (art. 6, `orden-hap-70-2013:art-6`; LIRPF DA 33, `ley-35-2006:da-33`). A profile-wide boolean would make every quarter applicable once any prize was declared, which overstates the obligation.

## Considerations

- The profile schema version is pinned exactly. A pre-current stored version is refused on read and never repaired silently (`validate_profile_schema_identity`, `src/cadrumo/domain/user_profile/values.py`). A change to what a stored value means therefore needs a version bump and a forward migration.
- Deadline windows already carry typed profile predicates evaluated per window (`src/cadrumo/domain/deadlines/engine.py`, `_obligation_for_window`, and `src/cadrumo/domain/calculations/registry/schedules.py`). The predicate operations are only `equals` and `not_equals` (`src/cadrumo/domain/calculations/registry/schema_verification.py`, `ProfilePredicateOp`).
- The calendar gives a row only to an APPLICABLE verdict. INCOMPLETE and NOT_APPLICABLE are suppressed and listed with their reason (`src/cadrumo/application/overview/calendar.py`), so the three states stay visible without inventing rows.
- Multi-token profile values already use one delimited string validated at the boundary, as the IRPF income categories do (`src/cadrumo/domain/deadlines/profiles.py`, `_resolve_income_categories`).

## Considered options

- **Keep the boolean and treat a stored `false` as "no".** Rejected. A defaulted `false` becomes a confident not-applicable, which is the silent under-declaration this product refuses.
- **Rename each payer-fact path so that only new writes count as answers.** Rejected. The same concept would get a second name, and every CLI flag, locale key and binding would move for no semantic gain.
- **A three-state payer-fact value with a profile schema bump and a forward migration that drops unprovable negatives.** Kept.
- **A per-period payer-fact kind evaluated inside the applicability rule.** Rejected. The rule is evaluated per profile, not per window, so the period would have to be threaded through every applicability consumer.
- **A declared yes/no plus a set of prize quarters, with an `includes` predicate on each 136 deadline window.** Kept. It reuses the per-window predicate path, and each window states its own quarter as data.

## Constraints

- A persisted change needs a forward, deterministic, idempotent migration that is tested from every supported stored version. Profile schema 6 is the only supported stored version, because earlier versions are already refused.
- Filing-affecting data needs a republish of the authority, done through the coordinator's queue window.
- Live AEAT access is out of scope.

## Implementation

The payer-fact mechanism answers one of three declaration states instead of a boolean:

- declared yes gives APPLICABLE;
- declared no gives NOT_APPLICABLE, with the rule's not-applicable reason;
- undeclared gives INCOMPLETE, with the existing payer-fact rationale.

Profile fields for dated payer facts become optional booleans, where absent means undeclared. Setup stops defaulting payer-fact questions, so a non-interactive setup leaves them absent and only an interactive answer or an explicit CLI flag writes `true` or `false`. The coded payer facts (withholding, intracommunity, IVA group, OSS) keep their current evaluators. Only the dated, registry-declared payer facts move to the three-state contract.

Profile schema version 7 records that a stored `false` on a dated payer-fact path is an answer. The forward migration from 6 to 7:

- keeps every stored `true`;
- drops every stored `false` on those paths, because a version-6 negative cannot be proven to be an answer;
- leaves every other fact untouched.

The migration runs inside the profile store's own persistence boundary, atomically per profile, and is idempotent.

Modelo 136 gets two payer facts in fact 0139:

- a yes/no fact: obtained a prize subject to the gravamen especial on which no retención or ingreso a cuenta was made;
- a quarter set: the quarters in which such a prize was cashed, stored as a delimited string of `YYYY-nT` tokens and validated at the boundary.

The 136 applicability rule requires the yes/no fact, and fact 0139 names the quarter set as that fact's period companion:
- a declared yes counts as yes only when the companion set is non-empty;
- a yes without any declared quarter is undeclared, so 136 stays INCOMPLETE, never APPLICABLE with no rows.

A new `includes` predicate operation lets each 136 deadline window require that the quarter set contains that window's own quarter. The deadline rows are then exactly the quarters declared. `includes` is a generic operation: the observed value is a token set, and the predicate value is one token.

## Rationale

The three-state contract is the only option under which an operator who answered can reach NOT_APPLICABLE while a defaulted value cannot, and it keeps one name per concept. The migration drops only negatives that no stored evidence can support. Asking again costs the operator one question, whereas keeping those negatives could hide an obligation. Scoping 136 through the per-window predicate uses the path windows already take and keeps each window's condition in the registry next to the article-7 window it gates.

## Consequences

- Existing profiles that declared nothing, or only defaulted negatives, show Modelos 136, 347, 720 and 721 as INCOMPLETE with the reason until the taxpayer answers. The migration therefore records which facts it cleared. On the first open after migration, and in explain and the calendar, a localized notice names each cleared fact and the command or setup step that answers it, so the change never reads as a new obligation appearing from nothing.
- Every stored profile moves to schema 7 on first open after the upgrade. A profile bundle exported at version 6 must pass through the same migration before import.
- The `includes` operation is available to any future per-period obligation. A quarter token that matches no window is inert, not an error, so declared quarters outside a window's range produce no row.
- Docs sequence goldens that show setup flags, explain facts or applicability listings change with the new questions and must be regenerated in the same window.

## Amendment 2026-11-06: the six coded payer facts lose their defaults

Accepted 2026-11-06. The authorization is not one statement covering all six paths; it is two, and each covers named paths. Both were given by the operator on 2026-11-06 and relayed verbatim by the coordinator for this lane.

**The four originally reported paths** are `iva.does_intracomunitario`, `withholding.has_employees`, `withholding.pays_professionals_with_retencion` and `withholding.pays_rent_with_retencion`. Their disposition was put to the operator as a two-option question: clear a stored `false` and re-ask it, or keep it and notify the operator to reconfirm. The operator answered "yes drop old reask". Those words choose the first option for these four paths, and nothing wider: they are an answer to that question, not a general licence over stored negatives.

**`irpf.art109_activity_income_withholding_ge_70pct` and `withholding.pays_capital_income_with_retencion`** are covered by a second, direct instruction of the same day: "please ensure you fix the known issues related to your lanes". Both were already known defects of the same class in this lane when it was given, so it extends the ruling above to them on its own terms, and the two-option answer is not stretched to carry them. Their disposition is therefore identical: a stored `false` is dropped and re-asked, a stored `true` is kept.

The Art. 109 fact is the Modelo 130 exclusion, so its polarity is the reverse of the other four. RIRPF art. 109.1 exempts the taxpayer from pagos fraccionados when at least 70 per cent of the previous year's professional, agricultural, livestock or forestry activity income bore retención or ingreso a cuenta, so a declared yes makes Modelo 130 not applicable, a declared no leaves the pago fraccionado due, and an unanswered fact leaves it incomplete. A defaulted negative asserted an answer nobody gave and made the obligation read as settled.

`withholding.pays_capital_income_with_retencion` carries the same defect with a third shape. That fact is what the Modelo 117, 123, 126, 128, 187, 188, 193 and 194 rules require, so it decides eight modelos. Its profile field stayed a plain `bool` defaulting to `False`, which left the fact two-state: the stored negative could not be told apart from an unanswered question, so the eight modelos were reported incomplete whether the taxpayer had answered or not, and a taxpayer who states that he pays no rendimientos del capital mobiliario subject to retencion could never get them ruled out. The calendar's own unset warning for the fact could not fire either, because the catalogue default always left a value on the path. LIRPF art. 25 defines those rendimientos and art. 99 with RIRPF art. 90 and art. 108 fix the retencion and the periodic declaration, so a declared yes makes the eight applicable, a declared no rules them out, and an unanswered fact leaves them incomplete. Its profile field becomes `bool | None`, which is what `applicability_payer_facts.py` reads as the three-state contract: the registry declares no `three_state` key of its own, it derives the reading from the profile field's annotation, so the field change is the whole extension.

The Implementation section kept the coded payer facts (withholding, intracommunity) on their own evaluators. Those facts have since moved to the three-state contract: `_THREE_STATE_PAYER_FACTS` in `src/cadrumo/domain/calculations/registry/applicability_payer_facts.py`. Their setup defaults were never removed, though:

- `src/cadrumo/_data/registry/aeat/facts/0096-ley-49-2002-profile-binding-catalogue.toml` still declares `|bool|false` for `iva.does_intracomunitario`, `withholding.has_employees`, `withholding.pays_professionals_with_retencion`, `withholding.pays_rent_with_retencion`, `withholding.pays_capital_income_with_retencion` and `irpf.art109_activity_income_withholding_ge_70pct`;
- the setup questions in `src/cadrumo/application/wizard/setup_tax_sections.py` still default to `"false"`.

`setup_answer_projection.py` fills an absent path with that default. An unanswered profile therefore reaches the three-state evaluator as a declared no, so Modelos 111, 115, 180, 190, 216, 296 and 349 are refused as not applicable, and Modelo 130 is reported as applicable, instead of either being reported as incomplete. That is the silent under-declaration this decision rejected.

The amendment extends the dated-fact contract to these six paths:

- **Defaults:** the six catalogue entries and their setup questions carry no default, as `withholding.colegio_concertado` and the Modelo 347 and 720 questions already do. Only an interactive answer or an explicit CLI flag writes `true` or `false`.
- **Migration:** profile schema version 8 records that a stored `false` on these paths is an answer. Its forward migration keeps every stored `true`, drops every stored `false` on the six paths, and leaves every other fact untouched. It runs atomically per profile inside the profile store's persistence boundary and is idempotent. It records the cleared facts, so the existing localized notice names each one and the step that answers it.
- **Migration scope:** the migration clears an enumerated list of paths, not every stored `false`. The list is `PAYER_FACT_PATHS_CLEARED_FROM_V7` in `src/cadrumo/domain/user_profile/schema_migration.py`, and it holds exactly these six: `irpf.art109_activity_income_withholding_ge_70pct`, `iva.does_intracomunitario`, `withholding.has_employees`, `withholding.pays_capital_income_with_retencion`, `withholding.pays_professionals_with_retencion` and `withholding.pays_rent_with_retencion`. A stored `false` on any other path keeps its value and its meaning. This decision authorizes no drop-all-negatives sweep, and a path is added to that list only under its own authorization: whether other defaulted negatives in the profile carry the same defect is a separate question, still open.
- **An unanswered fact warns; it does not block:** under current policy an INCOMPLETE applicability verdict stays outside the readiness gate's blocking set (`BLOCKING_APPLICABILITY_VERDICTS` in `src/cadrumo/application/modelo/profile_readiness_gate.py`, which holds NOT_APPLICABLE and ATTRIBUTION_PASS_THROUGH only). So a cleared fact leaves the operator a calendar warning, an explain reason and a cleared-fact notice, while the work unit he already has stays calculable, verifiable and filable on his own figures. That is a policy choice about what an unanswered question should cost, not a consequence of the three-state contract, and it is pending the open decision on profile-fact drift; a ruling that an unanswered gating fact must stop the work unit would change this line and the assertion that pins it.
- **Notice scope:** a rule gates its modelo through the fact it requires and equally through the fact an exclusion reads, so the modelo-scoped cleared-fact notice reads both. Without that, the Art. 109 fact would never be re-asked on Modelo 130, the only modelo it gates.
- **Supported stored versions:** every version this build has ever migrated stays a supported stored source, so a profile that was not opened across a release is never locked out. Each transition owns the paths it clears: leaving schema 6 clears the three dated payer facts, and leaving schema 7 clears these six. A record stored at schema 6 crosses both transitions in one write and has both sets dropped, named together in its one cleared-fact history event, which also records the version it came from. A stored `false` on a dated payer fact is kept when the record is stored at schema 7, because that version did read it as an answer. The same door authenticates a restored or imported bundle at either version, so a portable profile takes the same migration on first open.
- **Unchanged:** `censo.public_administration_budget_gt_6000000` keeps its current treatment. It is not a payer fact and cannot turn an unanswered question into a not-applicable verdict. `censo.large_company` was listed here too, on the same reasoning; the second amendment below retires that and converts it, because the condition does decide an applicability verdict through the Modelo 347 SII derivation, and because its stored default silently picked a filing cadence.

The rationale is the original one: asking again costs the operator one question, while a kept defaulted negative could hide a withholding, intracommunity or pago fraccionado obligation.

## Amendment 2026-11-06: the residency category, the IVA enrolments and the large-company condition lose their defaults

Accepted 2026-11-06. The operator was shown the three facts below as one group with three options, and chose the first:

- "the same rule for all, residency included";
- "re-ask the IVA facts but confirm residency";
- "new profiles only".

His answer, verbatim: "Same rule: drop and re-ask (Recommended)". That ruling covers this closed list of paths and nothing else. "The same rule" is the rule the amendment above states for the six coded payer facts: the catalogue and setup defaults are removed, the fact becomes three-state, and the schema 7 to 8 transition drops the stored default so the question is asked again.

**`taxpayer_type.fiscal_residency`** is the one select. The setup binding catalogue declared it `|str|resident_irpf`, so `setup_answer_projection` filled an absent path with the resident category and every profile carried an answer nobody had given. LIRPF art. 9 makes habitual residence in Spain the test for the IRPF and TRLIRNR art. 2 makes its absence the test for the IRNR, so the category selects the tax and with it the modelo family. The defaulted token therefore silently ruled Modelo 210 out and admitted Modelos 100, 130, 151, 200, 202 and 840. The rule's residency gate also let an unanswered category fall through to applicable rather than refusing, so removing the default alone would have admitted the non-resident autoliquidación to every taxpayer instead. An unanswered residency is now INCOMPLETE on every rule that names its residencies, under the undeclared-taxpayer-model rationale, because the axis is part of the taxpayer model. Being a select rather than a boolean, it carries no second spelling: the blank sentinel the other optional selects already use is the unanswered state, and the registry's own `fiscal_residency.default_token` is no longer read onto a profile.

**The six IVA enrolment facts** are `iva.roi_enrolled`, `iva.oss_enrolled`, `iva.group_member_enrolled`, `iva.group_dominant_entity_enrolled`, `iva.sii_enrolled` and `iva.intracommunity_operations_exceed_50000_eur`. Their catalogue entries already carried no default and their setup questions already defaulted to nothing; the collapse was in the projection, which read each one as `profile.iva.<field> is True`, so the profile model could only hold two states. A taxpayer who stated that he is not a member of a grupo de entidades got the same incomplete verdict as one who had never been asked, and Modelos 322, 353 and 369 could never be ruled out. Each of these enrolments selects an obligation the taxpayer opted into: LIVA arts. 163 quinquies and following with RIVA art. 71 for the grupo de entidades (Modelo 322 for the member, Modelo 353 for the dominant entity), LIVA art. 163 octiesdecies and following for the one-stop-shop (Modelo 369), and the Modelo 349 cadence threshold. The fields become `bool | None`, the projection routes them through the same declared-bool reader as the withholding facts, and the three coded facts `iva_group_member`, `iva_group_dominant_entity` and `oss_enrolled` move from their own evaluators into `_THREE_STATE_PAYER_FACTS` keyed on their dotted profile paths, which is how 322, 353 and 369 reach NOT_APPLICABLE on a stated no and INCOMPLETE when unanswered. No coded payer fact keeps an evaluator of its own; the two-state reading survives only for a dated projection over a plain boolean field.

**`censo.large_company`** was declared `|bool|false` in the catalogue, defaulted in its setup question, and typed `bool = False` on `SetupAnswers` and `ModeloEnrollment`. It is a member of the derived `iva_books_kept_through_sii` fact, which decides Modelo 347, so it does turn an unanswered question into a verdict and the "Unchanged" bullet above was wrong on its own terms. It also selects the filing cadence of Modelos 111, 115, 123, 216 and 303 under LIVA art. 121 with RIVA art. 71. What an unanswered condition implies is neither cadence: a quarterly schedule requires the condition stated as a no and a monthly one as a yes, so an unstated condition selects no schedule and the modelo gets no window for the period. The engine does not guess. The operator is not left with an unexplained silence, because the condition is a gating key and the calendar emits its named unset warning against exactly those modelos. One registry correction was needed to make that true: the Modelo 303 quarterly schedule asked `enrollment.large_company not_equals true`, which an absent value satisfies, so silence still produced the quarterly cadence. It now asks `equals false`, as the Modelo 111, 115, 123 and 216 quarterly schedules already did.

**Named gaps for every gating key.** The calendar's profile-gap warnings named nine keys, and `_record_gating_field` silently drops a key it cannot name, so an obligation gated by any other fact was left unscoped with no statement of the missing answer. Every profile key the registry can gate an obligation on now declares a warning: the Modelo 720 and 721 thresholds, both Modelo 136 facts, the Modelo 347 SII keys, the Modelo 322, 353 and 369 enrolments, the Modelo 349 cadence threshold, the residency category, the large-company condition, the public-administration budget and the entity type. The derivation reads all three ways a profile fact decides what the operator sees, adding the filing schedules' own predicates to the applicability rules and the deadline windows, and a test derives the reachable set from the registry and fails when one key is unnamed or one mapping is unreachable. The Modelo 720 threshold needed a schema correction to be addressable at all: its field declared `schedule_predicates` without the matching `model_selectors` its Modelo 721 sibling has, so neither the warning nor the cleared-fact notice could resolve its path.

**Migration scope.** The schema 7 to 8 transition's cleared list, `PAYER_FACT_PATHS_CLEARED_FROM_V7` in `src/cadrumo/domain/user_profile/schema_migration.py`, now holds fourteen paths: the six from the amendment above, plus `censo.large_company`, `iva.group_dominant_entity_enrolled`, `iva.group_member_enrolled`, `iva.intracommunity_operations_exceed_50000_eur`, `iva.oss_enrolled`, `iva.roi_enrolled`, `iva.sii_enrolled` and `taxpayer_type.fiscal_residency`. A stored value on any other path keeps its value and its meaning; this still authorizes no drop-all-negatives sweep, and a path is added only under its own authorization.

What "cleared" means is now declared per path rather than assumed to be `false`, because the residency path is not a boolean. Each cleared path is mapped to the exact value its question defaulted to, compared by type and value: `false` for every yes/no fact and the `resident_irpf` token for the residency select. A stored `non_resident_irnr` was never written unasked and keeps its value, as every stored `true` does.

Dropping a stored `resident_irpf` drops real answers as well, because a real answer and the wizard's default are the same bytes and nothing in the record tells them apart. That is the cost the operator chose when he chose drop and re-ask over confirm: re-asking a question already answered is recoverable, while reading a default as an answer silently decides which tax a taxpayer pays. The cleared-fact notice carries a second wording for this one path, because a select is answered by one flag and a value and naming a negated flag would send the operator to an option the verb does not have.

Filed revisions are not rewritten. The migration transforms the profile record only; a `PRESENTADO` revision keeps the facts it was calculated on.
