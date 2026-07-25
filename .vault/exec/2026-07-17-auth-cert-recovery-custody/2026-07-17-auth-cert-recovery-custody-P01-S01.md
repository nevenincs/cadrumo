---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Atomically replace broad auth clear across backend and live CLI contracts with typed target-scoped logout_operator_auth and reset_operator_auth, complete provider session coverage, safe secret and lock cleanup, distinct schemas and events, exact contract, risk, help and write metadata, four-locale help, and real workflow and command tests without a compatibility wrapper

## Scope

- `src/cadrumo/application/auth/_operator.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S37` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Replace the broad auth-clear result and facade with distinct, strict, secret-free logout and reset contracts.
- Resolve explicit provider, all-provider, configured-provider, and explicit target-bucket scopes without switching the global active pointer.
- Delete provider sessions and locks through exact bucket routes, including the production Cl@ve Permanente session stem.
- Preserve provider and certificate configuration on logout; remove configuration, certificate registrations, and canonical secure-storage secrets on reset.
- Suppress duplicate state writes and events on idempotent reruns, and emit events only for providers whose artefacts or configuration changed.
- Replace the CLI command, payload schemas, operator contract, risk metadata, write policy, and help inventory without a compatibility alias.
- Migrate the four locale catalogues for the logout and reset grammar.
- Add real encrypted-storage, ambient-session restoration, token-root, event, reserved-provider, schema, language, and destructive-confirmation coverage.

## Outcome

The typed target-scoped split exists at HEAD and the broad clear is gone.
`src/cadrumo/application/auth/_operator.py` declares `logout_operator_auth` and
`reset_operator_auth` as separate public operations, supported by scoped helpers
`_delete_scoped_sessions`, `_clear_scoped_locks`,
`_delete_certificate_source_secrets`, `_clear_certificate_custody`, and the
per-request assertions `_assert_logout_request_matches` and
`_assert_reset_request_matches`. A repository-wide search of `src/` finds no
`clear_operator_auth` symbol and no `AuthClearResult` type, so no compatibility
wrapper survives.

The resumable-cleanup machinery the corrective pass added is also present:
`_build_auth_cleanup_intent`, `_apply_auth_cleanup_intent`,
`_cleanup_operation_id`, `_auth_cleanup_intent_has_effects`, and
`_auth_cleanup_bucket_events` are all declared in the same module.

Delivery attribution is a documented composite rather than a single commit. The
originating record carries a path-exact and hunk-exact ownership manifest across
seven commits; all of them resolve at HEAD:

- `1c59f64326` carried the application-layer auth split (facade, acquisition lock, operator, operator results, operator scope, sessions, storage-session tests, help, write policy, workflow verification test) plus auth-only hunks in the operator-surface contract and risk tables.
- `c247f94f97` carried the CLI door: the auth command module, its round-five surface test, the config payload schemas, and the destructive-confirmation, output-language, and workflow-surface tests.
- `3ac3fb25e1` carried the auth error registrations.
- `374d1d7e39` carried the four locale catalogues' auth hunks and removed the retired clear key.
- `001004ee2f` carried the originating execution record and the plan-row transitions.
- `1a8ee75547` is the corrective commit, wholly owned by this step across twenty-seven paths: revision-aware secure-object persistence, atomic workflow and event writes, the secret-free cleanup intent and mutation span, central live-session serialization, and the real recovery and concurrency tests.
- `33f7998ac3` is listed in the originating chronology but owns no path for this step.

The originating record reports focused verification at execution time of
thirteen auth and workflow tests, twenty-two auth CLI and confirmation tests,
six output-language tests, one hundred forty-nine schema and operator-contract
tests, seventeen registry tests, four locale audits, Ruff, and five kept
import-linter contracts; and, after the corrective commit, a one-hundred-
forty-six-test application authentication suite, an eight-test recovery and
concurrency suite, and five kept contracts over 3,427 files.

## Notes

Attribution for this step is hunk-level, not commit-level, for five of its
files. `1c59f64326`, `c247f94f97`, `3ac3fb25e1`, and `374d1d7e39` are
operator-directed mixed flush commits that co-carried unrelated ledger,
registry, user-profile, modelo, MCP, terminology, and locale work in the same
immutable commits. The operator-surface contract and risk tables and the four
locale catalogues each carried both this step's hunks and unrelated peer hunks.
This record does not claim commit-level ownership of those commits; it claims
only the hunks the originating manifest names, and that claim is not
independently re-derivable from the commit boundaries alone.

The end state is independently substantiated at HEAD by symbol presence and
symbol absence, which is the stronger evidence and does not depend on the
attribution manifest. The verification figures quoted above are transcribed
from the originating record and were not re-run for this reconciliation.

The originating record also recorded two execution incidents: a transient
Windows file-replace lock interrupted one Hungarian locale-manager write and was
resolved by retrying the manager operation rather than hand-editing the
catalogue, and the first CLI pytest invocations selected no tests because the
project default selects the unit marker, which was corrected by re-running with
the integration marker.
