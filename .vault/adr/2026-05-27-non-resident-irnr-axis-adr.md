---
tags:
  - '#adr'
  - '#non-resident-irnr-axis'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-21-taxpayer-type-applicability-adr]]"
  - "[[2026-04-28-ccaa-in-profile-adr]]"
  - '[[2026-06-04-non-resident-irnr-axis-research]]'
---


# `non-resident-irnr-axis` adr: Non-resident IRNR fiscal-residency axis | (**status:** `accepted`)

## D1 — Context

The AEAT persona audit rounds confirmed three distinct non-resident scenarios:
Olivia (round-16, UK national post-Brexit), Khadija (round-25, Moroccan
seasonal agricultural worker), and Felipe (round-26, Argentine freelancer).
All three require IRNR (Impuesto sobre la Renta de No Residentes) rather than
IRPF, or alternatively an IRPF filing with a distinct non-resident treatment
for certain casillas.

Prior to this ADR, `TaxpayerProfile` had no fiscal residency field. The
`deadlines` domain accepted any profile as a resident IRPF filer. Seasonal
workers like Khadija who spend more than 183 days in Spain may become tax
residents under LIRPF art. 9, while those who do not remain IRNR filers
subject to the Spain-origin country double-taxation convenio. The application
had no way to distinguish these situations, and the wizard never asked about
country of fiscal residence.

Grounding references: LIRPF art. 9 (183-day residency test), LIRNR art. 12
(permanent establishment and withholding), Spain-Morocco double-taxation
convenio, Spain-UK treaty post-Brexit.

## D2 — Decision

### D2.1 — Add `fiscal_residency: FiscalResidency` enum to profile

Add a closed `FiscalResidency` enum with members `RESIDENT` (IRPF filer) and
`NON_RESIDENT` (IRNR filer). The field is mandatory on `TaxpayerProfile` with
a default of `RESIDENT` for all existing records to preserve backward
compatibility.

### D2.2 — Add `country_of_fiscal_residence: str` field to profile

Add `country_of_fiscal_residence: str` as a mandatory ISO 3166-1 alpha-2
country code. Defaults to `"es"` for existing records. The wizard captures
this during onboarding and the `work` CLI surface validates it against the
list of countries with active double-taxation convenios published by AEAT.

### D2.3 — Add derived `ue_eee_status: bool` property

Add a `@property` `ue_eee_status` on `TaxpayerProfile` that returns `True`
when `country_of_fiscal_residence` is an EU or EEA country code. This
derived property controls which IRNR tax rates apply (EU/EEA residents
benefit from the 19% rate vs the general 24% rate under LIRNR art. 25).

### D2.4 — Wire fiscal residency into the deadlines domain

`DeadlineProfile` in `src/aeat/domain/deadlines/_profiles.py` receives a
`fiscal_residency` field so deadline windows can differentiate between IRPF
filing periods (April 1 – June 30) and IRNR submission periods
(model-100 vs model-210 window).

## D3 — Alternatives considered

**Alternative A: single `ccaa` field with null-for-non-resident.** The existing
`ccaa: ComunidadAutonoma` field already covers territorial context for
residents. Extending it with a sentinel `NON_RESIDENT` value was considered.
Rejected: `ComunidadAutonoma` is a territorial enum for autonomous communities
within Spain; extending it with a non-resident sentinel conflates a filing-
jurisdiction dimension with an administrative-territory dimension. Every
downstream consumer that interprets `ccaa` for IRPF allocation tables would
need a guard for the sentinel, and the IRNR path has no ccaa equivalent.

**Alternative B: separate `IrnrProfile` model.** A wholly separate profile
model for non-residents was considered, mirroring the way `RentaFamilyProfile`
extends the base. Rejected at this time: IRNR implementation is future work;
adding just the schema fields establishes the axis without requiring a full
IRNR engine. A full `IrnrProfile` can be added once the M210 filing engine is
planned.

**Alternative C: string field only, no enum.** Using a plain
`fiscal_residency: Literal["resident", "non_resident"]` was considered.
Rejected: a closed enum provides a stable import target for downstream
consumers (deadline engine, wizard, CLI advice rendering) and avoids the need
for exhaustiveness guards on string comparisons.

## D4 — Trade-offs

- **Schema surface vs IRNR engine completeness.** The decision adds profile
  fields and wizard capture but does not implement the full IRNR calculation
  engine (M210). This is intentional: the schema axis is required now for
  correct deadline routing and advisory output; the M210 engine is a future
  campaign item.
- **Backward compatibility.** Defaulting `fiscal_residency = RESIDENT` and
  `country_of_fiscal_residence = "es"` on all existing records avoids a
  migration. The trade-off is that existing profiles silently assume residency
  even if the operator intended otherwise; this is an acceptable risk given
  that all current beta personas are Spanish residents.
- **Derived property vs stored field.** `ue_eee_status` is a pure derivation
  from `country_of_fiscal_residence` and does not need to be persisted. The
  trade-off is that the EU/EEA country list must be kept in sync with
  membership changes; the list is encoded as a `frozenset` constant in
  `src/aeat/domain/deadlines/_models.py`.

## D5 — Consequences

- `TaxpayerProfile` gains `fiscal_residency`, `country_of_fiscal_residence`,
  and the derived `ue_eee_status` property. All existing persisted profiles
  remain valid with their defaults.
- The wizard `_setup_answers.py` and `_catalogue.py` capture fiscal residency
  during onboarding. The 183-day advisory is emitted when a non-EU
  `country_of_fiscal_residence` is set, reminding the operator to confirm
  LIRPF art. 9 status.
- The deadlines domain can route non-residents to IRNR filing windows. The
  IRNR M210 engine itself remains future work; no calculation logic is
  introduced here.
- 241 new tests verify residency derivation, `ue_eee_status`, and wizard
  round-trip.
