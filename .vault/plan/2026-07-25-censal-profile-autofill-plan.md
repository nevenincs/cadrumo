---
tags:
  - '#plan'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-26'
tier: L2
related:
  - '[[2026-07-25-censal-profile-autofill-adr]]'
  - '[[2026-07-25-censal-profile-autofill-research]]'
---

# `censal-profile-autofill` plan

### Phase `P01` - Auth credentials on the profile

Give an authentication mode somewhere to keep what it needs, on the encrypted profile rather than a dotenv, and make the setup surface collect it.

- [x] `P01.S01` - Declare the auth section in the user-profile schema with provider, dni_nie and numero_soporte at identity sensitivity, and pin its shape with a schema test; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `P01.S02` - Resolve Clave credentials from the active profile with a settings fallback, refusing a Clave mode missing either half and naming what is absent; `src/cadrumo/application/auth/_sessions.py`.
- [x] `P01.S03` - Make the manager authentication action mode-aware over the profile fields, offering certificate selection only when a certificate is registered; `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`.
- [x] `P01.S11` - Declare the DNI validity-date contraste beside numero_soporte and resolve it profile-first with the settings fallback, refusing a non-QR route that carries neither form; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `P01.S12` - Resolve the Clave credentials in the operator readiness probes and status surfaces through the same profile-first resolver the session entry uses, so a profile-borne credential reports as configured; `src/cadrumo/application/auth/_operator_probes.py`.
- [x] `P01.S13` - Collect the DNI validity-date contraste in the manager auth form and require a contraste only on the non-QR route, satisfied by either the soporte or the validity date, so the default QR flow and Clave Permanente are not refused; `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`.
- [x] `P01.S16` - Bind the schema declared provenance set to UserProfileFact, widening it first for the shipped censal token, and gate every shipped fact path and provenance token against the schema; `src/cadrumo/domain/user_profile/_values.py`.
- [x] `P01.S17` - Declare the renta sex fields with the value set the AEAT registro design defines, and anchor the provenance contract at the schema rather than at a consuming module; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `P01.S18` - Make the readiness probes no-session contract the subject of a test, asserting the profile read is declined rather than merely survived; `src/cadrumo/application/auth/tests`.

### Phase `P02` - Read-only censal reader

Build the sede reader for mis datos censales, pinned to the consulta view and provably unable to reach the filing tool.

- [x] `P02.S04` - Discover the authenticated consulta URL and DOM for mis datos censales against a live session and record the selectors; `src/cadrumo/adapters/outbound/aeat/sede`.
- [x] `P02.S05` - Build the read-only censal reader in the sede adapter over the shared authenticated session and access gate; `src/cadrumo/adapters/outbound/aeat/sede`.
- [x] `P02.S06` - Prove the reader cannot write, failing closed at runtime on any BU36- or .zul or ModifDomiDual landing and on the /Sede/procedimientoini/ launcher prefix, with a static string check kept only as the weaker of two walls; `src/cadrumo/adapters/outbound/aeat/sede/tests`.

### Phase `P03` - Autofill and retirement

Commit pulled censal facts through the cotejo authority, and delete the register-based pull that reads a surface carrying no censal data.

- [ ] `P03.S07` - Map the identity and address fields read from mis datos censales onto profile schema paths with a provenance token naming the consulta surface, the regime fields being out of scope while they have no route; `src/cadrumo/application/live`.
- [ ] `P03.S08` - Commit pulled facts through apply_cotejo, adopting only blank paths and reporting every disagreement; `src/cadrumo/application/live`.
- [x] `P03.S09` - Delete the register-based censal pull, its manager action and its tests, and re-point the causa-casilla mapping it fed; `src/cadrumo/application/live/_censo_036_pull.py`.
- [ ] `P03.S10` - Verify the whole path live end to end in three phases, a pull onto a blank profile that adopts, a second unchanged pull that is a no-op, and a third pull after the operator edits an adopted value that reports the divergence rather than overwriting it; `src/cadrumo/application/live/tests`.
- [x] `P03.S14` - Restore aeat config profile censo pull as the live-transport sibling of censo file --file, reading through the censal reader and persisting through apply_cotejo behind the same --apply door, so both transports reconcile identically; `src/cadrumo/entrypoints/cli/_config/_censo_file.py`.
- [x] `P03.S15` - Offer the censal pull as a manager action gated on the auth mode having everything it needs, unavailable with an instructive refusal until the credentials are complete; `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`.

## Description

## Steps

## Parallelization

## Verification
