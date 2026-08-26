---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:2e0599d4094230536bc0fe12d568e4c565fe61c6217d7c415e4b51e2c75a1e77'
related:
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S249 provisioning sequence review`

## Scope

Reviewed only `W06.P12.S249`: the five changed profile/recovery sequence
contracts, their five owning-CLI-generated goldens, and the four coupled prose
pages. Grounding was the accepted per-profile password-custody ADR, the CLI
contract, the secure-storage rule, and the live profile create, login, list,
status, and repair payloads. The review checked mandatory paired recovery
creation, removal of password-only and unsafe secret-transport promises,
truthful static blockers, profile list/status composition, page order, and the
absence of an invented production-code dependency.

All four scoped page-coherence checks passed, and all five scoped sequence
golden checks passed. The diff changes only the five named contracts, five
matching generated goldens, and four named pages; it contains no production
change and no unrelated broad golden refresh.

## Findings

### profile-list-readiness | medium | Profile setup still promises a readiness field the list payload cannot expose

`docs/how-to/profile-setup.md` says that `aeat config profile list` flags an
incomplete profile so the operator can spot it later. The current
`ConfigListResult` contains only `active_profile` plus profile rows carrying
`name`, `bucket_id`, and `active`; its own contract explicitly assigns setup
readiness to the authenticated profile-record projection instead. The revised
`profile-setup-multiple` assertion correctly limits itself to `active`, but the
same page still makes the broader, false list-composition promise. A reader who
saves an incomplete wizard cannot perform the documented check. The clean
coherence and golden checks do not cover this prose-only claim.

### shared-master-custody-prose | medium | Three scoped pages still describe the superseded shared-master model

`docs/how-to/quickstart.md` says local data is encrypted with a master key
derived from a passphrase, while `docs/how-to/check-aeat-notifications.md` and
`docs/how-to/troubleshooting.md` call the credential a master-key passphrase.
The accepted custody ADR instead makes each immutable profile own an independent
random DEK wrapped by that profile's password; the password is sufficient for
normal unlock but is not itself the data key, and the shared master-key design
is superseded. These phrases leave the newly corrected recovery explanation
next to an obsolete custody model and misstate the compromise and rotation
boundary.

## Recommendations

For `profile-list-readiness`, rewrite the save-and-resume guidance to use the
authenticated readiness owner, such as `aeat config profile status`, or state
only what the unauthenticated list actually reports. Add a documentation
contract assertion for the chosen current payload field, rerun the owning page
coherence and scoped golden checks, and request re-review before closing S249.

For `shared-master-custody-prose`, replace the master-key wording on all three
scoped pages with the accepted per-profile model: the password unlocks that
profile's independently generated data-encryption key, while the separately
verified recovery phrase is the creation-time recovery route. Keep the wording
operator-level, but do not imply a shared or password-derived data key.

### Resolution verification

Re-review found both findings resolved. The save-and-resume guidance now says
the authenticated `aeat config profile show` reports `setup_state`, while
`profile list` deliberately reports only saved names and active selection. That
matches `ConfigProfileShowResult` and `ConfigListResult` ownership exactly.

The quickstart now describes one independent random encryption key per profile,
wrapped by that profile's passphrase. The notifications and troubleshooting
pages likewise say the profile passphrase unwraps that profile's independent
encryption key. No scoped master-key wording remains, and the corrected prose
matches the accepted per-profile random-DEK custody model without exposing
implementation secrets.

Re-review verdict: **PASS**. Both medium findings are closed; no new findings
were identified in the repair diff.
