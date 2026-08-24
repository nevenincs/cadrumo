---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:772ff55fedca635192b25d4d4d2d8d4164605a8259f6efa3b8a0b74cac4605ff'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S219 mandatory recovery documentation`

## Scope

Audit the S219 operator-facing custody documentation, locale-owned CLI help,
and regenerated sequence evidence against the accepted mandatory verified
recovery-at-creation, cannot-add-later, restore-only, and password-login-
independence decisions.

## Findings

### generated-profile-setup-sequences | high | Five committed sequence contracts cannot execute under the mandatory secret and recovery channels

The generated-source check `python -m dev.docs.sequences check --page
how-to/profile-setup` reports five divergences. `profile-setup-multiple`,
`profile-setup-worked-example`, `profile-setup-capabilities`, and
`profile-setup-history` still invoke headless `profile create` without a
passphrase channel or the paired recovery handoff and verification channels;
`profile-setup-logout` expects a successful status response after the seeded
profile has no resumable login session. The committed JSON goldens therefore
do not currently witness the live mandatory-recovery CLI. The sibling
`how-to/protect-data-access` sequence page checks cleanly.

### unavailable-recovery-artifact-export | medium | Operator guidance requires an artifact that no live CLI command can export

`docs/how-to/protect-data-access.md` tells the operator to keep the phrase with
its separately exported recovery artifact, and the reference repeats that the
artifact is required for the explicit restore proof. The live CLI exposes
`profile restore --artifact` but no recovery-artifact export command. The only
callers of `export_profile_recovery_artifact` are tests; no production CLI
surface gives an operator the artifact the guide requires. The restore-only
description is semantically correct once an artifact exists, but the documented
operator journey is not executable and leaves the mandatory creation phrase
without its documented portable proof.

## Recommendations

- Update every affected profile-setup sequence contract to use a real bounded
  passphrase channel and paired recovery handoff/verification channels, or a
  truthful seeded-profile prerequisite where creation is not the subject;
  regenerate through `python -m dev.docs.sequences refresh --page
  how-to/profile-setup`, then require the corresponding `check` command to pass.
- Add and document the accepted authenticated, exclusive recovery-artifact
  export surface, or state the current capability gap instead of instructing
  operators to perform an unavailable export. Keep the artifact explicitly
  restore-only and separate from normal archives.

### global-docs-locale-completeness | high | The full localized user-documentation gate remains red outside the three S219 catalogues

`pytest -n 0 dev/docs/tests/test_docs_localization.py` reports 30 incomplete
catalogues out of 57 in each target language, three `download.md` dash-policy
violations in each language, and an orphan
`reference/environment-overrides.po` catalogue in each language. The three
protect-data-access catalogues are complete, non-fuzzy, and match their
regenerated source messages, but the whole-corpus locale gate cannot pass until
the external drift is closed.

## Re-review disposition

The profile-setup high finding remains external and unresolved by this scoped
commit. Its contracts and goldens are not staged here, so their concurrent
worktree state is not evidence for S219 closure.

The medium finding is closed as a truthful target-surface documentation fix.
The operator guide now states that the CLI does not currently export a recovery
artifact, that the phrase alone is not a complete recovery path, and that only
an external provisioning workflow supplying the matching artifact can use the
explicit artifact restore door. The prose does not imply that an unavailable
export command exists.

Independent review finds no critical, high, or medium defect in the scoped
protect-data-access guide, its three catalogues, or its generated goldens. The
external profile-setup and whole-corpus locale findings remain open for their
own closure work.
