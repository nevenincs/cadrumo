---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:a013c53fdd709a9d86ee7243e9fc75ec8d4359b6c094fad4ac8f73f85f8ba6fe'
step_id: 'S56'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Record a formal decision on whether the custody verbs need a failed-attempt throttle, documenting the same-user offline-attack equivalence that makes the present absence defensible so the gap is a declared position rather than an oversight

## Scope

- `src/cadrumo/application/user_profile/_login_session.py`

## Description

- Confirm the asymmetry the review reported: the failed-attempt backoff has exactly one production consumer, profile login, and the passphrase-change, recovery-verify, and flat-recover verbs call none of it while all three are bootstrap-exempt.
- Weigh extending the backoff to the custody verbs against affirming the absence, on the review's own low-exploitability assessment rather than on a fresh threat model.
- Record the decision in the follow-on ADR scaffolded for this feature: no throttle, deliberately, with the reasoning and an explicit reachability tripwire.
- Land the reasoning in the custody module's own docstring, stated in its own terms, so the position sits next to the code that depends on it.

## Outcome

The absence is affirmed as deliberate and is now a declared position rather than an oversight. It shares the accepted ADR `2026-07-25-auth-cert-recovery-custody-adr` with the channel decision of `S53`; both are posture questions raised by one review over one door, and the ADR filename convention allots one record per feature per date.

The reasoning is that a throttle would reduce no attacker capability. Any caller able to run these verbs already holds same-user read access to the wrapped key artefacts and can mount the identical Argon2id attack offline at the same cost, so the oracle a throttle would close is already open at identical cost to anyone who can reach the verbs at all; and the recovery mnemonic carries 256 bits of entropy drawn from `secrets.token_bytes`, which is not guessable at any rate. Extending the backoff would spend a lockout failure mode on the recovery path — the one surface whose purpose is restoring access to an operator who has already lost it — to defend a boundary that is not there.

The reasoning, the entropy figure and its source, and the tripwire are recorded in the custody module docstring in the module's own terms, carrying no vault, ADR, or plan-step reference. The tripwire is stated plainly: if these operations ever become remotely or cross-user reachable, the offline-equivalence argument collapses and the failed-attempt backoff must be extended to cover them.

No throttle code was written, and `_login_session.py`, the file this step's Scope names, was deliberately not modified. The decision is that its backoff stays scoped to profile login; the deliverable is the recorded position, which belongs with the custody module it exempts rather than with the throttle it declines to extend.

## Notes

The decision is contingent, and the contingency is the point. Its validity rests entirely on the custody verbs remaining same-user locally reachable, which is why reachability is the declared tripwire rather than a periodic re-review — a scheduled re-read would ask a reviewer to re-derive the argument, whereas the tripwire attaches a stated obligation to the specific change that would invalidate it.

This is a formal deferral, which the review explicitly names as an acceptable outcome here given its honest low-exploitability assessment, while naming an unrecorded gap as unacceptable. Nothing about the surface changed; what changed is that the gap is now written down next to the code, with the condition under which it must close.
