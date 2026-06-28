---
step_id: "S23,S24,S25"
tags:
  - "#exec"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related:
  - "[[2026-05-31-trabajador-del-mar-plan]]"
  - "[[2026-05-31-trabajador-del-mar-adr]]"
---

# trabajador-del-mar W03.P07.S23-S25 step record

## Steps

- S23: verify CLI accepts worker_class = trabajador_del_mar in the config input path
- S24: verify CLI JSON output for trabajador_del_mar profile includes maritime CasillaObservation with legal_refs
- S25: verify RETMAR mandatory-filing warning surfaces in CLI output when retmar_registered = True

## Discovery

W03.P07 is verification of contracts that W01/W02 established; no new
construction. Three structural observations shaped the test design:

1. `worker_class` is a registered field of the user-profile schema
   (`src/aeat/_data/registry/aeat/user_profile/schema.toml`, section
   `maritime_worker`). The CLI profile-edit path (`aeat config profile
   edit ... --quiet`) reads its field schema from the same singleton
   exposed by `load_user_profile_schema()`. Verifying schema acceptance
   at the singleton level is therefore the canonical CLI-input contract
   for the fact -- no wizard-question wiring exists yet to expose it
   interactively, but the schema-driven validation path accepts it.

2. The CLI emit envelope wraps typed CasillaObservation rows with
   `legal_refs` and `source_refs`; the flat `casilla_values` mapping is
   a derived projection per `aeat-calculation-grounding`. The
   application-service envelope already carries the BOE anchors
   (verified by `test_maritime_exemption_service.py` at the service
   layer). Verification at the CLI layer reduces to asserting the
   envelope contract through the same singleton entry point a CLI verb
   would invoke.

3. RETMAR warning emission is rendered by the CLI error boundary at
   `aeat.entrypoints.cli._errors`, which translates any `AeatError`
   subclass through its registered `message_key`. W02 registered
   `ProfileCompletenessError` -> `ERROR_RENTA_PROFILE_COMPLETENESS_WARNING`
   and `MaritimeExemptionInactiveError` ->
   `REFUSED_RENTA_MARITIME_EXEMPTION_INACTIVE`. The S21 Spanish
   translations now pin the RETMAR / Ley 47/2015 anchor (and the DA 41
   / Ley 35/2006 anchor) in the rendered message, so any CLI verb that
   raises either error will emit a regulatorily grounded line.

The current CLI surface has no verb that invokes the maritime
exemption service directly. The verification is honest about that and
exercises the singletons each contract depends on rather than mocking
a verb that does not yet exist.

## Files Touched

- `src/aeat/entrypoints/cli/test_trabajador_del_mar_surface.py`
  (new, 168 lines):
  - `TestWorkerClassProfileFactAcceptance` -- two tests covering S23:
    schema field is declared, enum values are correct, legal_refs cover
    all three pathway anchors.
  - `TestMaritimeExemptionEnvelopeCarriesLegalRefs` -- three tests
    covering S24: Art. 7.p) envelope carries BOE-A-2006-20764, REBECA
    envelope carries BOE-A-1994-16100, flat casilla_values matches the
    typed observation value.
  - `TestRetmarMandatoryFilingWarningSurface` -- five tests covering
    S25: both AeatError subclasses are registered with correct code +
    message_key; the Spanish translations of both message_keys carry
    the regulatory anchors; ProfileCompletenessError fires on
    retmar_registered=True with the right message body.

## Commit

`0d03d65dc` -- test(entrypoints/cli): trabajador-del-mar W03.P07 CLI surface verification

## BOE Citations

- Ley 35/2006 Art. 7.p) BOE-A-2006-20764 -- asserted in Art. 7.p) envelope legal_refs
- Ley 19/1994 Arts. 73-75 BOE-A-1994-16100 -- asserted in REBECA envelope legal_refs
- Ley 35/2006 DA 41 BOE-A-2006-20764 -- asserted in DA 41 inactive translated message
- Ley 47/2015 BOE-A-2015-11346 -- asserted in RETMAR translated message and in
  ProfileCompletenessError context

## Outcome

10/10 new tests pass. Full trabajador/maritime suite green at 74/74
(domain + application + CLI surface tests). Close-gate audits:

- `rg "DA 24|dietas a bordo" src/aeat/entrypoints/cli/ src/aeat/locales/`
  reports zero hits (the pre-W02 misframings are absent).
- `python -m aeat.locales audit` reports ca/en/es/hu all ok.

Honest deviation from the plan: no CLI verb currently invokes
`resolve_maritime_exemption`. The verification tests cover the
contracts a future verb will rely on (schema acceptance, envelope
shape, error-boundary translation). Wiring a consumer verb -- whether
through Modelo 100 calculation or a dedicated config-edit path for
`worker_class` -- is downstream of W03 and not in scope here.
