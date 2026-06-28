---
step_id: "S19,S20,S21,S22"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W03.P06.S19-S22 step record

## Steps

- S19: scaffold locale keys for worker_class selector and trabajador_del_mar value
- S20: scaffold locale keys for art_7p / rebeca / da41 inactive / retmar_mandatory_filing
- S21: add Spanish (es) translations for all new keys
- S22: run locale audit to confirm no orphan or missing keys

## Discovery

W02 wired two AeatError subclasses (MaritimeExemptionInactiveError,
ProfileCompletenessError) into the central error-code registry at
`src/aeat/core/errors/registry/_domain.py` with message_keys

- `errors.refused.refused_renta_maritime_exemption_inactive`
- `errors.error.error_renta_profile_completeness_warning`

`python -m aeat.locales scaffold` had already materialised both keys as
self-referencing placeholders across ca/en/es/hu. No additional tr()
calls or selector labels were introduced in W02 beyond the registered
error codes, so S19 and S20 reduce to "the scaffold ran and produced
the two error-message slots"; the four-locale parity exists.

The brief scopes S21 to Spanish only. ca/en/hu retain their existing
self-reference placeholders (out of scope for this Wave).

## Files Touched

- `src/aeat/locales/es.yml`: two leaf values set via
  `python -m aeat.locales set es <key> <value>`:
  - `errors.refused.refused_renta_maritime_exemption_inactive` -> Spanish
    prose covering DA 41 LIRPF inactivity, EU state-aid clearance
    requirement, Ley 35/2006 DA 41 / BOE-A-2006-20764, Ley 6/2018 /
    BOE-A-2018-9268.
  - `errors.error.error_renta_profile_completeness_warning` -> Spanish
    prose covering RETMAR mandatory IRPF filing since January 2023,
    Ley 47/2015 / BOE-A-2015-11346.

## Commit

`5da848f9c` -- feat(locales/es): trabajador-del-mar W03.P06 Spanish translations

## BOE Citations

- Ley 35/2006 DA 41 BOE-A-2006-20764 -- inactive-pending-EU-clearance prose anchor
- Ley 6/2018 BOE-A-2018-9268 -- DA 41 enabling-law anchor
- Ley 47/2015 BOE-A-2015-11346 -- RETMAR mandatory-filing anchor

## Outcome

`python -m aeat.locales audit` reports ca/en/es/hu all ok. The two
Spanish translations are now operator-grade: when a future CLI verb
raises either AeatError the boundary at `aeat.entrypoints.cli._errors`
will emit a regulatorily grounded message in Spanish (the default
output language).

The CLI emit contract is verified separately by the W03.P07 record.
