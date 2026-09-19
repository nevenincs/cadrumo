---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:81a26f3c2bf647c76b81ee2e48b830fcfbe09c71819b7dec5d9ffa3791169f99'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S228 profile delete sequence review`

## Scope

Audit the S228 guide and sequence contract against the real logout and
single-profile deletion boundaries, the hermetic sequence runner, and the
CLI-owned golden-record gate.

## Findings

### s228-profile-delete-sequence-review | high | logout cannot reach the login-gated delete verb

The real page refresh executes `config logout` successfully, then the root CLI
refuses `config profile delete docs-sequence-sandbox --yes` with exit 2 and
`REFUSED_CLI_BOUNDARY`: the operator is no longer logged in. This is consistent
with the explicit negative admission in `LOGIN_GATED_VERB_PATHS`, but conflicts
with the lifecycle test that claims deletion succeeds from a no-session state.
The sequence runner therefore cannot generate the required golden record, and
the requested logout-then-delete journey is not a live product behaviour.

### s228-profile-delete-sequence-review | high | executed sequence has no CLI-owned golden

The corrected contract uses one visible logout frame and one terminal delete
result whose success payload must report `deleted == true`. Because the terminal
verb is refused, the CLI refresh writes no `profile-setup-delete` golden. An
executed documentation sequence cannot be merged or closed without that
generated ownership record.

### s228-profile-delete-sequence-review | resolved | sessionless deletion now reaches the custody boundary

S238 removed inactive deletion from the root login gate while retaining active
profile refusal, exact target binding, explicit confirmation, and the custody
preflight. The real sequence now logs out and deletes the exact sandbox profile
successfully; its result reports `deleted == true` and no active profile.

### s228-profile-delete-sequence-review | resolved | generated golden and terminal page ordering are complete

The sequence refresh CLI generated the logout/delete golden, and S239 enrolled
only the destroyed encrypted-byte digest as a central command-and-path-specific
mask. Stable fingerprint counts remain asserted. Deletion is now the guide's
last profile operation, so later examples never reuse a destroyed profile.
Independent formal re-review passed with no findings.

## Recommendations

- Reconcile whether irreversible profile deletion is intentionally login-gated
  or intentionally reachable after strong-close logout; implement and test one
  boundary consistently before closing S228.
- Once the real subprocess journey succeeds, refresh through the sequence CLI,
  commit its generated golden, rerun page coherence and nitpicky documentation
  gates, and request a fresh formal review.
- Close S228 on the real sequence, terminal page placement, generated golden,
  and clean formal re-review evidence. Track concurrent registry schema and
  unrelated cross-page sequence baseline failures with their owning work.
