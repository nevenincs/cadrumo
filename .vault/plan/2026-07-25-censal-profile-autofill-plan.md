---
tags:
  - '#plan'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
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
- [ ] `P01.S03` - Make the manager authentication action mode-aware over the profile fields, offering certificate selection only when a certificate is registered; `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`.
- [x] `P01.S11` - Declare the DNI validity-date contraste beside numero_soporte and resolve it profile-first with the settings fallback, refusing a non-QR route that carries neither form; `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`.
- [x] `P01.S12` - Resolve the Clave credentials in the operator readiness probes and status surfaces through the same profile-first resolver the session entry uses, so a profile-borne credential reports as configured; `src/cadrumo/application/auth/_operator_probes.py`.

### Phase `P02` - Read-only censal reader

Build the sede reader for mis datos censales, pinned to the consulta view and provably unable to reach the filing tool.

- [ ] `P02.S04` - Discover the authenticated consulta URL and DOM for mis datos censales against a live session and record the selectors; `src/cadrumo/adapters/outbound/aeat/sede`.
- [ ] `P02.S05` - Build the read-only censal reader in the sede adapter over the shared authenticated session and access gate; `src/cadrumo/adapters/outbound/aeat/sede`.
- [ ] `P02.S06` - Prove the reader cannot write: assert it exposes no submit and that the MOD036 filing path appears nowhere in the module; `src/cadrumo/adapters/outbound/aeat/sede/tests`.

### Phase `P03` - Autofill and retirement

Commit pulled censal facts through the cotejo authority, and delete the register-based pull that reads a surface carrying no censal data.

- [ ] `P03.S07` - Map the read censal fields onto profile schema paths with a provenance token naming the consulta surface; `src/cadrumo/application/live`.
- [ ] `P03.S08` - Commit pulled facts through apply_cotejo, adopting only blank paths and reporting every disagreement; `src/cadrumo/application/live`.
- [x] `P03.S09` - Delete the register-based censal pull, its manager action and its tests, and re-point the causa-casilla mapping it fed; `src/cadrumo/application/live/_censo_036_pull.py`.
- [ ] `P03.S10` - Verify the whole path live end to end: auth, pull, autofill, and a second pull that reports disagreement instead of overwriting; `src/cadrumo/application/live/tests`.

## Description

## Steps

## Parallelization

## Verification
