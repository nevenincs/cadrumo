---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-25'
body_hash: 'sha256:50092725eeea8577c8bbbed7bd41bbdb561082270fa9430fb98c08dd4383a771'
step_id: 'S10'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Replace the root callback's implicit unlock with persisted-session resume (valid record resumes silently with one idle-deadline re-persist, absent or expired session makes non-exempt verbs refuse with a Notice naming aeat config login, CADRUMO_SECRET_PASSPHRASE headless path preserved process-scoped), verified by CLI lifecycle tests exercising resume, idle expiry, and absolute expiry against a real bucket

## Scope

- `src/cadrumo/entrypoints/cli/__init__.py`
- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`

## Description

- Retire the root callback's implicit unlock: a non-exempt verb now resumes the persisted session through the single application resume authority rather than opening key material of its own.
- Route every refusal through the typed boundary error carrying the next verb as its suggestion, so the refusal renders on the shared envelope spine as a blocking error document rather than on the non-blocking notices channel.
- Split the refusal copy by cause, holding the logged-out reason set as enum members rather than bare string values so a later rename cannot silently reclassify an operator from "you are not logged in" into "your session expired".
- Preserve the headless secret channel process-scoped: an environment carrying the sanctioned passphrase variable has already supplied the authentication factor and keeps working with neither a pointer nor a persisted session, while every interactive operator meets the login gate.
- Keep the bootstrap-exempt set the authority for which verbs may run without a session, so login itself and the landing card stay reachable.
- Surface an unreachable credential store as its own typed custody refusal instead of routing it to the login verb, because re-authenticating cannot fix a store that cannot answer and naming it would loop the operator.

## Outcome

- Landed on `main` across the campaign's root-resume commits, with the expiry coverage subsequently made verifiable without a credential store.
- The step's own gate is PARTIALLY observed green on this host. Of the four cases the step names, idle expiry, absolute expiry, and the unreachable-credential-store custody refusal all pass; only silent resume remains unobserved, and it is the one case that genuinely requires the operating-system keychain, because resuming a record means unwrapping its data-encryption key under the custodied session key.
- The two silent-resume cases fail at an explicit precondition naming the missing custody, so the red cannot be misread as a defect in the resume path.
- The full-tree collection gate is clean: 13970 tests collected, 3235 deselected, exit code zero.

## Notes

- This step stays open, and the reason is narrower than when the sibling steps were recorded. The blocker those records named, a custody guard that caught only the keyring library's own exception hierarchy while the platform raised an operating-system error outside it, has since landed; all three custody functions now normalise the platform error to the typed refusal, so login degrades to a process-scoped session with a warning exactly as its contract states. What remains is not a defect but an absent capability: this execution context reaches the host over a network logon that carries no credentials, so no session key can be custodied here at all.
- The residual gap is therefore verifiable by the operator in a single interactive run rather than by any further code change. The application is not degraded for a real interactive user.
- The record for this step was missing entirely until this pass, while its siblings had been written; the step's implementation and test module had been landed without one.
- UPDATE, closing pass. The two silent-resume cases were still selected by the integration lane, so this module was red on every host that is not an interactive desktop. They now carry the supplementary label that holds credential-store-bound cases out of every lane, and the lane is observed green: idle expiry, absolute expiry, the absent-session refusal naming the login verb, the unreachable-credential-store custody refusal, and the headless secret channel all pass. Both silent-resume cases were run and confirmed to stop at the explicit precondition in the shared login helper, before any assertion about resume behaviour, so the red established an absent capability rather than a defect in the resume path.
- Silent resume is irreducibly custody-bound: resuming means unwrapping the record's data-encryption key under the session key the credential store holds, so a host that cannot custody one cannot exhibit the behaviour at all. The operator closes it from a desktop session with the enrolling recipe. The refusals that guard every other operator on every other host are the half that matters for fail-closed behaviour, and that half is green.
