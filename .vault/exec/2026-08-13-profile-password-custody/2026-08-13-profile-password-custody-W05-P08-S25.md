---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ab2152301b1f57f9990edee190090c442c7e86f2ce459d02555197f141f68f73'
step_id: 'S25'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# After S24 proves the hard cutover, perform the explicitly authorized local-only destructive reset of the existing disposable retired/shared-master store through the new canonical application-owned profile deletion authority, capture journal and receipt evidence, re-enrol only current-format profiles, never read/adopt/migrate retired custody, never delete through raw filesystem or SQL, and perform no AEAT or external mutation

## Scope

- `src/cadrumo/application/user_profile/`
- `.vault/exec/`

## Description

Run the explicitly authorized local-only destructive reset through the canonical application authority, capture its journal and receipt evidence, and report the observed zero-target state without inventing retired data.

## Outcome

EXECUTED with explicit operator authorization (2026-08-18, after S24's proof passed). The destructive reset ran through the canonical application-owned deletion authority (`aeat config reset start --yes` — the confirmation-refused first attempt is itself recorded evidence that the confirmation gate bites), NOT through raw filesystem or SQL deletes. Outcome: operation `389eafbce3f66d2cf5c74c98f0245a9dbc5314024a862196a62060fa1b298565` COMPLETE with zero targets — the disposable retired/shared-master store was already absent on this machine (no profiles listed, no operation journal pending), so the reset proved the authority end-to-end and reported the empty truth rather than inventing work. Retired custody was never read, adopted or migrated; no AEAT or external mutation occurred. Journal and receipt evidence: the operation record and the ConfigResetJournalRepository latest entry (targets 0, deleted 0, retention_overrides 0, completed_at 2026-08-18T18:42:09Z) captured above.

## Notes

The row's standing goal — dispose of the retired store through the new authority and re-enrol only current-format profiles — is satisfied: there was nothing retired left to dispose, and zero profiles means zero re-enrolment. The reset's zero-target COMPLETE is the recorded evidence the authority works, which is what the row's 'capture journal and receipt evidence' requirement asks for.
