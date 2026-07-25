---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S03'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Prove reset removes provider state, sessions, locks, registrations, and secrets only for the explicit target

## Scope

- `src/cadrumo/application/auth/tests/test_operator.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S44` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Add a real-behavior test proving a provider-scoped `reset_operator_auth` clears only the target provider's artefacts.
- Configure the certificate provider with a real persisted session, an acquisition lock, a named source registration, and its secure-storage secret, and place an unrelated Cl@ve Móvil session and acquisition lock in the same bucket.
- Reset the certificate provider and assert every certificate artefact is removed while the Cl@ve Móvil session and lock survive untouched.
- Assert the returned removed-session, cleared-lock, removed-source, removed-secret, and cleared-configuration counts match the target-only cleanup.

## Outcome

The proof exists at HEAD. `src/cadrumo/application/auth/tests/test_operator.py`
declares `test_reset_provider_scope_removes_only_the_target_provider_artefacts`.

Attribution is a single clean commit: `1b428b4c87`, "test(auth): prove
provider-scoped reset removes only the target provider's artefacts", dated
2026-07-17. A content search of the file's history attributes the test name to
that commit and no other.

The originating record reports the focused module passing at twenty-eight tests,
twenty-seven prior plus this proof, with clean Ruff, and states the test
exercises real encrypted secure storage, real acquisition-lock files, and the
real `reset_operator_auth` application service with no mocks, stubs, or
monkeypatching.

## Notes

Substantiated without reservation: the named test node is present at HEAD and
one commit introduced it.

The verification figures quoted above are transcribed from the originating
record and were not re-run for this reconciliation.

The originating record notes that provider-scoped session and lock cleanup is
driven by the resolved auth operation scope, so an unrelated provider's
artefacts in the same bucket are never in scope, and that no source change was
required for this step because only the missing proof was absent.
