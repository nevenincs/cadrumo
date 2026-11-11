---
tags:
  - '#adr'
  - '#modelo-202-obligation'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:129c61af0f3d09ec051543697054631e2d590a0962177bcd74043eefee3c5c14'
related:
  - "[[2026-06-19-m202-first-period-attestation-adr]]"
  - "[[2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr]]"
  - "[[2026-09-23-calendar-obligations-payer-fact-declaration-state-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-11-11-cli-action-envelope-precondition-alternative-actions-adr]]"
  - '[[2026-11-11-modelo-202-obligation-research]]'
---

# `modelo-202-obligation` adr: `Modelo 202 filing obligation facts` | (**status:** `proposed`)

Proposed 2026-11-11 for the lifecycle lane. Not accepted. The lane's rulings on the open choices are at the end of Constraints.

## Problem Statement

The calendar decides whether a sociedad owes a Modelo 202 for an instalment (`src/cadrumo/domain/calculations/registry/applicability_modelo202.py:233-279`, catalogue `src/cadrumo/_data/registry/aeat/facts/0101-modelo-202-applicability-catalogue.toml`). Above the LIS art. 40.3 INCN threshold, filing is owed every instalment. At or below it, a 202 is owed only in an instalment where an ingreso results (Orden HFP/227/2017, BOE-A-2017-2778, art. 1.3). Whether an ingreso results depends on the art. 40.2 base or on an art. 40.3 election. The application records neither, so every sociedad at or below the threshold is INCOMPLETE for every instalment (`src/cadrumo/application/overview/tests/test_calendar_legal_entity.py:82`). This record decides where those two inputs come from.

## Considerations

- LIS (Ley 27/2014, BOE-A-2014-12328) art. 40.2 bases the instalment on the cuota integra of the last periodo impositivo whose filing deadline had passed on the first day of the payment window of the instalment (1 April, October or December), less deducciones, bonificaciones, retenciones and ingresos a cuenta. The payment is 18 per cent of that base (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-40.html`). A base of zero or less yields no ingreso.
- Art. 40.3: the election is made in the declaracion censal, in February of the first calendar year it covers, or within the stated window for a non-calendar periodo impositivo. It binds that periodo impositivo and the following ones until renounced in a later declaracion censal.
- Art. 40.3 places the threshold on the INCN of the 12 months before the start of the periodo impositivo the instalment belongs to, not before the instalment itself.
- Art. 40.1, second paragraph, and Orden art. 1.3 exclude the art. 29.4 and 29.5 entities from the payment and the filing. Orden art. 1.3 also excludes resident-only AIE and UTE under LIS title VII chapter II, and art. 1.2 sends grupos fiscales to Modelo 222.
- The registry already declares the art. 40.2 base as a binding: `modelo-202-cuota-base-ejercicio-anterior` copies Modelo 200 casilla `DP200014B:00599` with per-instalment offsets, 1P two filing years back and 2P and 3P one (`src/cadrumo/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/bindings/0001-declarations.toml:33-44`). It is declared only at that edition. Its own comment records that the earlier instructions carry the same art. 40.2 wording.
- `2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr`, as amended on 2026-11-11, admits `ATTEST_PRIOR_VALUE` on a scalar relation-prefill dependency whenever the application holds no upstream return. The base binding is such a dependency. The attest door is served beside the create door (`2026-11-11-cli-action-envelope-precondition-alternative-actions-adr`).
- `2026-09-23-calendar-obligations-payer-fact-declaration-state-adr` keeps a stated no, a stated yes and never-asked distinct, requires a named calendar warning for every gating key, and adds a new path through a schema bump (`src/cadrumo/domain/user_profile/schema_migration.py:124-143`).
- Profile facts already carry `valid_from` and `valid_to` (`src/cadrumo/domain/user_profile/values.py:231-263`). The INCN field is effective-dated (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:460`).
- `2026-06-19-m202-first-period-attestation-adr` scopes out the 202 dependency only when the activity-start year is at or after the target year. Under art. 40.2 the 1P instalment of the second year also has no base, because the Modelo 200 deadline of the first year has not passed on 1 April.

## Considered options

- **Profile election fact plus the registry base binding, with attestation where no Modelo 200 is held (chosen).** The election is a censal fact of the entity. The base is a fact of an earlier return and already has one canonical binding.
- **Attestation alone (the operator states the base, or no ingreso, per instalment).** Rejected. It ignores a Modelo 200 the application holds and adds a second source beside the binding.
- **Modelo 200 derivation alone.** Rejected. A sociedad whose earlier return was filed outside the application stays INCOMPLETE indefinitely, against the 2026-11-11 operator ruling that attestation suffices.
- **The art. 40.2 base as a profile fact.** Rejected. It is a per-instalment figure of an earlier return, not a fact of the entity, and it goes stale when that return is amended.
- **Absent election read as not elected.** Rejected. A default would decide the method silently, which the payer-fact ADR forbids.

## Constraints

- No year literal. Years, editions and the envelope come from `supported-filing-years.toml` through `revision_temporal_resolution` (`2026-08-14-registry-temporal-coverage-adr`). The source year of an instalment comes from the declared offsets of the binding, never from a comparison in code.
- One base mechanism. The obligation reads the art. 40.2 base only through the resolution of `modelo-202-cuota-base-ejercicio-anterior` for that instalment. There is no second derivation from Modelo 200 casillas.
- The base is never inferred. Absent stays INCOMPLETE.
- A BORRADOR Modelo 200 does not decide the obligation. A local PRESENTADO revision or captured filed evidence does, and its provenance is shown. This governs the calendar verdict only. Verification of the Modelo 202 itself keeps the cross-period clean-state rules unchanged.
- An attestation counts only where no source is held. A conflicting Modelo 200 that appears later raises the existing blocking conflict finding.
- Above the threshold nothing changes: APPLICABLE every instalment, whatever the election.
- Out of scope, stated as known gaps with no fact: art. 29.4 and 29.5 entities, resident-only AIE and UTE, grupos fiscales (Modelo 222), a non-calendar periodo impositivo (the binding offsets assume a calendar one), and the art. 40.2 second-paragraph proration when the last concluded period is shorter than a year. None is presented as resolved.
- Lane rulings on the open choices (LIFECYCLE, 2026-11-11, for acceptance): (a) a calculated Modelo 202 of that instalment decides: a positive result is APPLICABLE, a zero result NOT_APPLICABLE; until it exists the verdict stays INCOMPLETE with the calculate door, because the regulated arithmetic is the registry calculation's and Orden HFP/227/2017 art. 1.3 turns only on whether an ingreso results. (b) the reconciliation of `2026-06-19-m202-first-period-attestation-adr` is applied in the same change, because it uses the same binding offsets and the second year's 1P has no art. 40.2 base either. (c) a local PRESENTADO Modelo 200 or captured filed evidence may decide the calendar verdict, shown with its provenance; a BORRADOR may not. The calendar is a read projection, not a filing-grade gate; the cross-period clean-state gate keeps its own blocking rule for filing.

## Implementation

We will decide the Modelo 202 obligation of a sociedad at or below the threshold from one new dated profile fact, the art. 40.3 election, and from the art. 40.2 base resolved per instalment through the existing registry binding, with operator attestation where the application holds no Modelo 200.

- **Election fact.** A new effective-dated optional boolean in the `taxpayer_type` section of the profile schema, working name `pago_fraccionado_art_40_3_elected`, legal ref `ley-27-2014:art-40-3`, with source provenance. `true` is an election stated in a declaracion censal, with `valid_from` the start of the first periodo impositivo it binds. `false` is a stated no, or a renuncia whose `valid_from` is the periodo impositivo it takes effect in. Absent is never asked. There is no catalogue or setup default; only an interactive answer or an explicit CLI flag writes it, and the calendar names it as a gating key. The value read is the one effective at the start of the periodo impositivo the instalment belongs to.
- **Verdict per instalment.** The per-profile modality stays in the domain. The per-instalment outcome is decided where the calendar already evaluates windows:
  - INCN undeclared: INCOMPLETE, as today.
  - INCN above the threshold: APPLICABLE.
  - Election never asked: INCOMPLETE, with the door to state the censal election.
  - Election stated yes: INCOMPLETE with its own reason, because the ingreso depends on the base imponible of the 3, 9 or 11 months, which only the Modelo 202 calculation of that instalment produces. Door: calculate that 202. Under ruling (a): a calculated 202 with a positive result decides APPLICABLE and a zero result NOT_APPLICABLE.
  - Election stated no: resolve the base binding for the instalment. A positive base gives APPLICABLE. Zero or negative gives NOT_APPLICABLE, citing art. 40.2 and Orden art. 1.3. A source periodo impositivo that ended before the declared activity start means no prior return exists, so NOT_APPLICABLE with operator-declared provenance. An absent base gives INCOMPLETE, with the Modelo 200 create or capture door first and the attest door as an alternative.
- **Attestation.** Reuse `ATTEST_PRIOR_VALUE` on the base binding of the Modelo 202 work unit for that instalment, under the absence rule of the 2026-11-11 amendment. The calendar reads it from the operator layer of the latest revision of that work unit, with operator-attested provenance. INCOMPLETE applicability does not block creating that work unit (`BLOCKING_APPLICABILITY_VERDICTS` in `src/cadrumo/application/modelo/profile_readiness_gate.py`). No new intent kind.
- **Registry.** Declare the base binding at the earliest Modelo 202 edition whose instructions carry the art. 40.2 wording, after checking the instructions of each edition, so later editions inherit it. Where the resolved edition still declares no base binding, the verdict stays INCOMPLETE; there is no fallback. Reword `reason.filing_depends_on_ingreso` in the catalogue and add one served reason per outcome above.
- **Schema.** Profile schema 9 introduces the new path. The 8 to 9 transition clears nothing, and a schema-8 record carrying the path is refused, as `PATHS_INTRODUCED_IN_V7` does today.

## Rationale

The election is a declaration the entity makes in its censal record, and it binds across periods until renounced. A dated three-state profile fact has that shape, and the payer-fact contract already separates a stated no from never asked. The art. 40.2 base belongs to an earlier return, and the registry already models that return through one binding with per-instalment offsets. Reading that binding keeps one path from calendar to calculation. Attestation covers a return the application does not hold, under the 2026-11-11 operator ruling, without a second store.

## Consequences

- A sociedad at or below the threshold that states no election and holds or attests its Modelo 200 base gets a definite verdict per instalment. 1P can differ from 2P and 3P because its base comes from an earlier year.
- Persona table: sociedad Modelo 202 rows move from INCOMPLETE to APPLICABLE or NOT_APPLICABLE per instalment once the persona states the election and holds or attests the base. Personas with the election unasked stay INCOMPLETE with the new door. Above-threshold personas are unchanged.
- Profile schema 9, its forward migration, the setup question, the CLI flag, the calendar warning, locale keys and docs goldens change. The authority is republished for the catalogue and the earliest-edition binding.
- The calendar reads Modelo 200 sources and the operator layer of a Modelo 202 work unit, which it did not read before.
- Reconsider if a captured censal observation exposes the art. 40.3 option, which would let capture supply the fact, or if a non-calendar periodo impositivo comes into scope.
