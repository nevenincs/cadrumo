---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:3ece9dc31107a0748518a7353bdd14c6567f3cf23c24dee2964580528c2966ff'
step_id: 'S479'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Establish that the two custody owner receipt cases fail on this host because the Windows credential store is unreachable from this logon session rather than on any defect, and leave them failing rather than pinning a null keyring that would defeat what they exercise

## Scope

- `src/cadrumo/application/user_profile/tests/test_custody_transactions.py` (read only)

## Changes

NOTHING WAS CHANGED, AND NOTHING SHOULD BE. This step is the evidence that the
two failures are an environment limitation on this host rather than a defect.

`test_delete_owner_receipts_are_durable_and_idempotent` and
`test_owner_receipts_resume_after_owner_effect_precedes_journal_state` fail
with:

    KeyringUnavailableError: OS keychain raised unexpectedly on the
    profile-session key write: (1312, 'CredRead', 'A specified logon session
    does not exist. It may already have been terminated')

CONFIRMED BELOW CADRUMO ENTIRELY. A three-line probe against `keyring` itself,
touching no project code, fails the same way:

    backend: keyring.backends.Windows.WinVaultKeyring (priority: 5)
    write FAILED: error (1312, 'CredRead', 'A specified logon session does not
    exist. It may already have been terminated')

So the Windows credential store is unreachable from this logon session. The
adapter is reporting that correctly; there is nothing here for a code change to
repair.

WHY THEY NEED IT AND THE OTHER THIRTY-TWO DO NOT. Both call
`_persist_real_current_session_acceleration`, whose docstring states the point:
"Create the current encrypted session record through its production writer."
`mint_profile_session` writes the session key to the OS keychain, and the
adapter has no file-store fallback on that path -- both arms of its `except`
raise `KeyringUnavailableError`, differing only in wording.

WHAT I DELIBERATELY DID NOT DO. The docs sandbox pins the credential vault
absent (`PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` plus
`keyring.set_keyring`), and it would have been easy to copy that here and turn
the tests green. That would be wrong twice over: these two cases exist to
exercise the REAL production writer, so pinning a null backend would leave them
asserting nothing about the thing they name, and `aeat-local-execution` forbids
substituting a mock for a gate that claims to exercise a real integration. The
same rule says an unavailable external dependency is reported explicitly, which
is what this record is.

## Notes

THIS IS NOT THE SAME AS THE SANDBOX PINNING, and the distinction is worth
keeping straight. The docs sequences pin the vault absent because a golden that
records `session_persisted: true` on a vault-bearing workstation and
`session_not_persisted` on a headless runner encodes the CAPTURING MACHINE --
there the host's posture is noise. Here the host's posture is the SUBJECT: the
test is about what the production writer durably does with a real keychain.

CONSEQUENCE FOR THE CAMPAIGN'S MEASUREMENTS. Any full-suite number I report from
this workstation carries these two, and they will not go green here whatever is
fixed. They are environment-limited, not open work, and should not be counted
against the repository.

STILL OPEN: the export-tree group stopped in S472 and characterised in S474, and
the three operator decisions -- the 125 `cli.*` extras, the 5 `application.*`
extras, and the `tui.ledger.reconciliation.direction` spelling.
