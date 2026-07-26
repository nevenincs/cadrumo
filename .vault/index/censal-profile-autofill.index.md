---
generated: true
tags:
  - '#index'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - '[[2026-07-25-censal-profile-autofill-P01-S01]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S02]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S03]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S11]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S12]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S13]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S16]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S17]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S18]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S19]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S20]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S23]]'
  - '[[2026-07-25-censal-profile-autofill-P01-S24]]'
  - '[[2026-07-25-censal-profile-autofill-P02-S04]]'
  - '[[2026-07-25-censal-profile-autofill-P02-S05]]'
  - '[[2026-07-25-censal-profile-autofill-P02-S06]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S07]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S08]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S09]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S10]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S14]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S15]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S21]]'
  - '[[2026-07-25-censal-profile-autofill-P03-S22]]'
  - '[[2026-07-25-censal-profile-autofill-adr]]'
  - '[[2026-07-25-censal-profile-autofill-plan]]'
  - '[[2026-07-25-censal-profile-autofill-research]]'
  - '[[2026-07-25-censal-profile-autofill-tooling-honesty-audit]]'
  - '[[2026-07-26-censal-profile-autofill-campaign-close-honesty-review-audit]]'
---

# `censal-profile-autofill` feature index

Auto-generated index of all documents tagged with `#censal-profile-autofill`.

## Documents

### adr

- `2026-07-25-censal-profile-autofill-adr` - `censal-profile-autofill` adr: `profile-borne auth credentials and a read-only censal autofill` | (**status:** `accepted`)

### audit

- `2026-07-25-censal-profile-autofill-tooling-honesty-audit` - `censal-profile-autofill` audit: `tooling honesty`
- `2026-07-26-censal-profile-autofill-campaign-close-honesty-review-audit` - `censal-profile-autofill` audit: `campaign close honesty review`

### exec

- `2026-07-25-censal-profile-autofill-P01-S01` - Declare the auth section in the user-profile schema with provider, dni_nie and numero_soporte at identity sensitivity, and pin its shape with a schema test
- `2026-07-25-censal-profile-autofill-P01-S02` - Resolve Clave credentials from the active profile with a settings fallback, refusing a Clave mode missing either half and naming what is absent
- `2026-07-25-censal-profile-autofill-P01-S03` - Make the manager authentication action mode-aware over the profile fields, offering certificate selection only when a certificate is registered
- `2026-07-25-censal-profile-autofill-P01-S11` - Declare the DNI validity-date contraste beside numero_soporte and resolve it profile-first with the settings fallback, refusing a non-QR route that carries neither form
- `2026-07-25-censal-profile-autofill-P01-S12` - Resolve the Clave credentials in the operator readiness probes and status surfaces through the same profile-first resolver the session entry uses, so a profile-borne credential reports as configured
- `2026-07-25-censal-profile-autofill-P01-S13` - Collect the DNI validity-date contraste in the manager auth form and require a contraste only on the non-QR route, satisfied by either the soporte or the validity date, so the default QR flow and Clave Permanente are not refused
- `2026-07-25-censal-profile-autofill-P01-S16` - Bind the schema declared provenance set to UserProfileFact, widening it first for the shipped censal token, and gate every shipped fact path and provenance token against the schema
- `2026-07-25-censal-profile-autofill-P01-S17` - Declare the renta sex fields with the value set the AEAT registro design defines, and anchor the provenance contract at the schema rather than at a consuming module
- `2026-07-25-censal-profile-autofill-P01-S18` - Make the readiness probes no-session contract the subject of a test, asserting the profile read is declined rather than merely survived
- `2026-07-25-censal-profile-autofill-P01-S19` - Hold every auth provider to the identity guard, since each binds a comparable NIF at session bind and an absent expectation silently disarms the downstream session check
- `2026-07-25-censal-profile-autofill-P01-S20` - Retire the dead censo-derived provenance token and make its gate enumerate the published set rather than naming one member
- `2026-07-25-censal-profile-autofill-P02-S04` - Discover the authenticated consulta URL and DOM for mis datos censales against a live session and record the selectors
- `2026-07-25-censal-profile-autofill-P02-S05` - Build the read-only censal reader in the sede adapter over the shared authenticated session and access gate
- `2026-07-25-censal-profile-autofill-P02-S06` - Prove the reader cannot write, failing closed at runtime on any BU36- or .zul or ModifDomiDual landing and on the /Sede/procedimientoini/ launcher prefix, with a static string check kept only as the weaker of two walls
- `2026-07-25-censal-profile-autofill-P03-S07` - Map the identity and address fields read from mis datos censales onto profile schema paths with a provenance token naming the consulta surface, the regime fields being out of scope while they have no route
- `2026-07-25-censal-profile-autofill-P03-S08` - Commit pulled facts through apply_cotejo, adopting only blank paths and reporting every disagreement
- `2026-07-25-censal-profile-autofill-P03-S09` - Delete the register-based censal pull, its manager action and its tests, and re-point the causa-casilla mapping it fed
- `2026-07-25-censal-profile-autofill-P03-S14` - Restore aeat config profile censo pull as the live-transport sibling of censo file --file, reading through the censal reader and persisting through apply_cotejo behind the same --apply door, so both transports reconcile identically
- `2026-07-25-censal-profile-autofill-P03-S15` - Offer the censal pull as a manager action gated on the auth mode having everything it needs, unavailable with an instructive refusal until the credentials are complete
- `2026-07-25-censal-profile-autofill-P03-S21` - Feed the censal ownership refusal from the read itself rather than from a projected tuple named for adoption, so editing that tuple cannot disarm the guard
- `2026-07-25-censal-profile-autofill-P03-S22` - Make the clear branch consult provenance as the value branch does, so a clear the app wrote cannot earn the protection reserved for an operator decision
- `2026-07-25-censal-profile-autofill-P01-S23` - Salvage the authenticated Clave session a post-auth navigation failure was closing unread, so a spent second factor becomes a retryable navigation
- `2026-07-25-censal-profile-autofill-P01-S24` - Pin the session-identity comparison the certificate provider's only fail-closed check rests on, asserting the refusal and the per-return wiring rather than the expectation alone
- `2026-07-25-censal-profile-autofill-P03-S10` - Verify the whole path live end to end in three phases, a pull onto a blank profile that adopts, a second unchanged pull that is a no-op, and a third pull after the operator edits an adopted value that reports the divergence rather than overwriting it

### plan

- `2026-07-25-censal-profile-autofill-plan` - `censal-profile-autofill` plan

### research

- `2026-07-25-censal-profile-autofill-research` - `censal-profile-autofill` research: `where the taxpayer's censal data actually lives`
