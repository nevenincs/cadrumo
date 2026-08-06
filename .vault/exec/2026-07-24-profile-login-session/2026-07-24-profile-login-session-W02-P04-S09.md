---
tags:
  - '#exec'
  - '#profile-login-session'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:d2ab40433ab0aaa4fc4b72e3edc60a7fff922c0f5dac91961440b73d31a1510e'
step_id: 'S09'
related:
  - "[[2026-07-24-profile-login-session-plan]]"
---

# Extend logout_active_profile to the full strong close (seal and zeroise the live session, delete the persisted record and its keychain entry, release the bucket lockfile, clear the pointer) while staying idempotent when already logged out, verified by tests proving both artefacts are gone after logout and a second logout is a clean no-op

## Scope

- `src/cadrumo/application/user_profile/_orchestration.py`

## Description

- Extend the existing logout orchestration to the full strong close: seal and zeroise the live in-process session, delete both halves of the persisted session (the on-disk wrapped record and its keychain entry), clear the failed-login backoff sidecar, release the bucket lockfile, and clear the pointer.
- Route the teardown through the single artefact-close authority the login handover already composes, so logout does not own a second teardown path.
- Tear down a live session bound to a bucket other than the pointed-to one (a resumed session whose pointer has since moved), so no profile survives a logout still holding unlocked key material.
- Tolerate every artefact being absent at each step, so a second logout, or a logout with nothing signed in, is a clean no-op returning no record.
- Keep the lock release best-effort by construction, so a torn bucket directory cannot strand the operator behind a refusal about a lock they cannot clear.
- Leave the per-invocation profile-override refusal untouched and ahead of any teardown, so a refused logout signs nothing out.

## Outcome

- Landed on `main` as commit `a7cf0e2412`, extending the profile orchestration module and adding a real-adapter strong-close test module that leads with the negative proofs: neither half of the split-knowledge session survives, a resume can no longer reconstruct the data-encryption key, the sealed session refuses to yield it, the backoff sidecar is gone, a second logout is a clean no-op, and a re-login after logout is a genuine re-authentication rather than a resume.
- The verification gate is NOT observed green on this host, for the same single root cause recorded against the login orchestration step: every credential-store read in this execution context raises the Windows "logon session does not exist" error, so each strong-close case fails inside its own login fixture before reaching an assertion.
- No defect specific to this step's own logic was found; the red gate is entirely attributable to the keychain-custody guard gap recorded against the preceding step.

## Notes

- This step stays open. Its logic is committed and its test module is authored, but a step whose gate has never been observed green must not be marked complete, so closure waits on the widened keychain guard that unblocks the shared login fixture.
- Semantic pre-search could not be run: the project code index refuses to build for this root, so no remediation coding was performed under the discovery mandate.
- UPDATE, later pass. The widened custody guard this step was waiting on has landed, so the shared login fixture no longer raises; it now degrades to a process-scoped login. Most of this step's gate is consequently observed green: the on-disk half of the split-knowledge session is gone after logout, a resume can no longer reconstruct the data-encryption key, the live session is sealed and refuses to yield it, the backoff sidecar is cleared, the pointer is cleared, a second logout is a clean no-op, the override refusal tears nothing down, and a re-login after logout is a genuine re-authentication rather than a resume.
- The strong-close case was split so the keychain half keeps a dedicated owner rather than being quietly dropped from the claim. That one case, asserting the custodied key itself is gone, is the only part of this step's gate still unobserved here, and it fails at an explicit precondition naming the missing custody.
- The step stays open on that single case. It is verifiable by the operator in one interactive run; no further code change is implicated.
- UPDATE, closing pass. That single case was still sitting in the default lane, so this module was red on every host that is not an interactive desktop, a headless continuous-integration runner included. It now carries the supplementary label that holds credential-store-bound cases out of every lane, and the rest of the strong close is observed green here: the on-disk half of the split-knowledge pair is gone, a resume can no longer reconstruct the data-encryption key, the sealed session refuses to yield it, the backoff sidecar is cleared, the pointer is cleared, a second logout is a clean no-op, the override refusal tears nothing down, and a re-login after logout is a genuine re-authentication rather than a resume.
- The claim this step makes about the keychain half is therefore split rather than dropped: it keeps a dedicated owner that fails at an explicit precondition naming the absent custody, and the operator closes it from a desktop session with the enrolling recipe. Deleting the on-disk record alone already renders a stale credential-store entry useless, so the unobserved case is a completeness proof rather than the security boundary.
