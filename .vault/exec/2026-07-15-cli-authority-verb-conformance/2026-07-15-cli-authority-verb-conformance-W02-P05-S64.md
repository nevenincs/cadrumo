---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S64'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Invoke target-scoped auth reset and delete canonical secure-storage certificate secrets before each target deletion without certificate keyring reconciliation or migration

## Scope

- `src/cadrumo/application/config_reset.py`

## Description

- Add an auth-clearing pass that runs for every target before any deletion, skipping targets already at or past the auth-cleared phase so the pass is idempotent under resume.
- Persist the auth-clearing phase to the journal before invoking auth reset, and persist the auth-cleared phase after it returns, so a crash mid-clear is recoverable.
- Invoke the canonical `reset_operator_auth` with all providers selected and the target bucket identifier supplied, consuming it through the auth package's public facade rather than reaching into its internals.
- Delegate certificate-secret deletion to that same canonical primitive, which removes the selected-profile secure-storage certificate source secrets as part of its scoped cleanup; add no second secret writer in the reset module.
- Advance an absent target straight to the auth-cleared phase without invoking auth reset, since a dangling-pointer target has no bucket storage to clear.
- Re-assess the target after auth reset and refuse with a typed error when the target disappeared mid-clear, refreshing the recorded fingerprint and retention decision from that re-assessment.
- Preserve an operator-approved retention override across the refresh so an approval granted at start is not silently dropped when the decision is recomputed.

## Outcome

- Auth custody and certificate secrets are cleared through the single canonical authority for each target before that target's storage is erased, so no credential outlives the bucket it authenticated.
- Certificate-secret deletion is a delegation, not a re-implementation: the reset module contains no parallel secret write path, preserving the primitive's atomicity and its lifecycle-event emission.
- No certificate keyring reconciliation, probe, fallback, or migration path was added, matching the deliberate scope of this step and the project's zero-legacy posture.
- The fingerprint is refreshed after auth clearing, so the value later compared under the deletion lock reflects the bucket's post-clear state rather than a stale pre-clear digest.
- Landed in commit `60135859e2`.

## Notes

- The work was already committed when this record was curated; the record documents the landed state verified against `HEAD` rather than a fresh edit.
- Agents in this environment run over an SSH network logon, where Windows keyring operations fail with `WinError 1312`. That is an environment artefact of the agent session, not a defect in this code path, and only an operator console session can exercise real keychain behaviour.
