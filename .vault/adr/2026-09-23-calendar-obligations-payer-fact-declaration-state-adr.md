---
tags:
  - '#adr'
  - '#calendar-obligations'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:35be4a07041d8f3583bfec014c934a93ea770cc0bfa10472d721ba64792cb5cd'
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
