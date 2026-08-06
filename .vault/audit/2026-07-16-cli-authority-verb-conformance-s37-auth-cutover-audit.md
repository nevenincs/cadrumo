---
tags:
  - '#audit'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:e750f9a14e60ae737c172ce552d78a42765fc70b0840b21f7dcb88f6a295fc3b'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-adr]]"
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# `cli-authority-verb-conformance` audit: `S37 auth logout/reset cutover review`

## Scope

Independent formal review of `W02.P06.S37` against the accepted ADR, plan,
revision-bound reference, and execution record. The review covered the current
HEAD plus delivery commits `1c59f64326`, `c247f94f97`, `3ac3fb25e1`,
`374d1d7e39`, `33f7998ac3`, and Vault commit `001004ee2f`.

The audit traced the public auth facade, target-bucket storage scope, persisted
session keys, acquisition locks, certificate-secret custody, workflow-state
events, error registry, CLI handlers, schemas, write and risk metadata,
operator help, locales, and real-behavior tests. It also checked the remaining
`config_reset.py` auth writer and old-token/RAG surfaces.

**Initial review status: REVISION REQUIRED.** The main logout/reset semantics
were implemented and focused gates were green, but the reset transaction could
leave partially completed destructive effects without truthful events and
could overwrite a concurrent auth change. The resolution review below records
the current accepted S37 status.

## Findings

### auth-reset-transaction | high | Irreversible cleanup precedes the authoritative state and event write

`reset_operator_auth` deletes certificate secrets, persisted sessions, and
acquisition locks before saving the reset `AuthState` and its events. A crash
or real repository-save failure after any deletion leaves the command failed
while some requested custody material is already gone. A retry can converge
the configuration, but it cannot reconstruct truthful
`auth.session.cleared` or `auth.lock.cleared` events for artefacts deleted by
the failed attempt.

The same sequence also has a lost-update window. The reset derives
`reset_auth` from an initial `repository.load()`, then
`WorkflowStateRepository.update()` loads again but the callback installs that
stale derived auth value. A concurrent provider configuration or certificate
source/secret change can therefore be overwritten; a newly added certificate
source can be removed from state without its newly stored secret being removed,
leaving an orphaned secret. Logout has the same stale-derived-auth pattern,
although its effect is limited to session readiness fields. This is a
significant integrity and concurrency defect and requires revision before the
step can be signed off.

### delivery-atomicity | high | S37 is split across mixed operator-flush commits

The intended atomic Step is distributed across application, entrypoint, core,
locale, cross-cutting test, and Vault flush commits, and each code commit also
contains unrelated campaign work. HEAD is buildable, but S37 cannot be
reviewed, reverted, cherry-picked, or attributed as one isolated Step. This
breaks the plan's one-Step/one-commit delivery discipline and makes a later
bisect unable to identify whether an auth regression belongs to S37 or the
co-flushed work. History need not be rewritten, but the execution record must
explicitly preserve the composite commit set and a path-level attribution
manifest, and no release checkpoint should treat any subset of those commits
as a complete S37 delivery.

### config-reset-parallel-writer | medium | The old AUTH reset authority remains live pending S62-S64

At the initial reviewed revision, `config_reset.py` exposed
`ConfigResetScope.AUTH` and `ALL` paths that
replace `AuthState()` directly, report `removed_auth_session=True`, and do not
call `reset_operator_auth`, delete persisted sessions or locks, remove bound
certificate secrets, or emit the canonical auth events. This is a real
parallel auth writer in the committed S37 baseline. It is not classified as an
independent S37 blocker because the approved plan assigns its removal and
composition to S62-S64, but that sequencing is binding: the branch must not be
released or represented as single-authority auth reset until those Steps land.

### old-token-grounding | medium | Generated and semantic-grounding surfaces still advertise auth clear

The executable application and CLI registrations no longer contain
`clear_operator_auth`, `AuthClearResult`, or `config.auth.clear`, and the live
CLI correctly rejects `auth clear`. However,
`src/cadrumo/_data/terminology/evaluation/coverage-report.json`, generated
static/build documentation, `dev/docs/cli_reference.py`, and the
revision-bound CLI authority reference still contain the removed spelling.
Fresh Vaultspec-RAG semantic search consequently returns the old
`clear_operator_auth` graph as a leading authority candidate. The generated
documentation and terminology work is assigned to later campaign Steps, but
the reference should be marked superseded for this cluster or regenerated and
the RAG index refreshed before it is used to ground further auth coding.

### auth-help-and-guidance | medium | New provider options lack help and the shared scope error suggests only logout

The live `logout` and `reset` help renders `--provider TEXT` with an empty help
cell even though `cli.config.auth.provider_help` already exists in every
catalogue. In addition, the central registry entry for
`AuthOperationScopeConflictError` always suggests
`aeat config auth logout --help`, including when the conflict came from reset.
Use the localized provider help on both commands and make the shared error
guidance neutral, or split it into operation-specific typed errors. Current
tests assert option presence but do not assert this guidance.

### real-behavior-coverage | low | Focused tests are real and clean but omit failure and concurrency oracles

The reviewed S37 tests use real encrypted profile storage, session-store
records, acquisition-lock files, secure certificate secrets, CLI invocation,
and ambient-session restoration. No mocks, fakes, stubs, monkeypatching,
`skip`, or `xfail` shortcuts were found in the touched test set. The principal
gap is that no test forces a real workflow-state save failure after cleanup or
runs concurrent auth configuration/reset, so the HIGH transaction defect is
not exercised.

## Recommendations

1. Revise `logout_operator_auth` and `reset_operator_auth` around one
   target-bucket mutation authority that serializes same-bucket auth changes
   and computes the final auth state from the state being committed, not an
   earlier snapshot.
2. Make destructive cleanup and event accounting recoverable. At minimum,
   persist intent/progress before external deletion and let retries emit
   truthful effects; preferably compose secure-object state and event writes
   transactionally where the storage boundary permits it.
3. Add real-behavior failure and concurrency tests without doubles: a genuine
   storage-write refusal after seeded secrets/sessions/locks, plus two real
   processes contending between configure/source mutation and reset.
4. Record the five code-flush commits and Vault commit as the immutable composite
   S37 delivery, with exact S37-owned paths and unrelated co-flushed paths
   distinguished. Do not rewrite history.
5. Keep S62-S64 as a hard pre-release gate so `config_reset.py` delegates to
   `reset_operator_auth` and cannot remain a second writer.
6. Add localized `--provider` help, correct the scope-conflict suggestion, and
   cover both in CLI/error-registry tests.
7. Complete the planned terminology/generated-document migration, supersede or
   annotate the stale auth-clear reference, rebuild the Vaultspec-RAG index,
   and confirm a fresh semantic search resolves the new logout/reset authority.

## Verification evidence

- `uv run --no-sync vaultspec-rag server doctor --json`: ready.
- Fresh semantic searches covered source, ADR, plan, reference, and execution
  records; exact symbols were confirmed with `rg`.
- Auth/workflow unit slice: 13 passed.
- Auth CLI and destructive-confirmation slice: 22 passed.
- Output-language slice: 6 passed.
- Schema, operator-contract, and help slice: 159 passed.
- Error-registry and operator-contract slice: 32 passed.
- Write-policy and MCP risk/mutability parity slice: 10 passed.
- Adjacent auth/session/lock slice: 36 passed.
- Targeted workflow CLI slice: 2 passed.
- Four-locale catalogue audit: `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`
  passed under an isolated storage root.
- Focused Ruff: passed.
- Uncached import-linter: 3,425 files, 16,196 dependencies, five contracts
  kept, zero broken.

## Resolution review

Independent remediation review was repeated against the accepted ADR, plan,
current authentication authority reference, live source, tests, and the
existing findings above. Vaultspec-RAG searches used the running service on
port `8766` and now return the logout/reset authority map and current
`logout_operator_auth` / `reset_operator_auth` implementation ahead of the
retired graph.

**Current status: S37 ACCEPTED; REPOSITORY PRE-RELEASE GATES OPEN.** The
original auth transaction, lost-update, live-session concurrency, help,
current-authority grounding, and composite-delivery attribution defects are
resolved. The planned `config_reset.py` duplicate and certificate-secret
set/remove recovery remain binding non-S37 pre-release gates.

### auth-reset-transaction | resolved | Cleanup is resumable and state plus events use revision-aware atomic persistence

`WorkflowStateRepository` now loads exact secure-object revisions, uses
compare-and-swap writes with bounded retry, handles first-writer absent-row
collisions, and commits workflow state with append-only bucket events in one
SQL unit of work. Logout and reset persist a secret-free
`AuthCleanupIntent` before deleting sessions, locks, or certificate secrets.
The matching operation resumes that intent after a failure; unrelated auth
mutations fail closed until it completes.

`auth_mutation_span` is the reentrant per-bucket writer boundary used by
provider configure, operator login, the public central session-acquisition
service, certificate source and secret mutations, logout, and reset. The
final state is derived from the freshly committed state rather than an
earlier snapshot. Certificate registrations carry registration-time
witnesses, and a pending reset blocks same-name secret replacement, closing
the reproduced lost-update and orphan-secret window.

Stable operation identifiers and timestamps make retry event identifiers
deterministic. Real SQLite-trigger tests prove that a failed logout or reset
finalization leaves the intent durable, external custody already removed is
reported by the resumed operation, workflow and append-only events are emitted
exactly once, and the next completed rerun reports zero effects. The result is
truthful at operation scope, including work completed before a resumed call.

### delivery-atomicity | resolved-recorded | Immutable composite delivery is attributed without rewriting history

The historical commit split was preserved. The S37 execution record now names
commits `1c59f64326`, `c247f94f97`, `3ac3fb25e1`, `374d1d7e39`,
`33f7998ac3`, `001004ee2f`, and corrective commit `1a8ee75547`; applies a
closed-world ownership rule; records exact S37 paths; identifies genuinely
mixed files at hunk level; and explicitly gives `33f7998ac3` zero S37
functional attribution. The delivery can now be audited and distinguished
from unrelated co-flushed work without falsifying or rewriting immutable
history.

### config-reset-parallel-writer | open-planned | S62-S64 remains a binding pre-release authority gate

Exact writer scans of the committed S37 baseline still find the sole
production auth replacement outside the canonical auth package at
`src/cadrumo/application/config_reset.py`, where `ConfigResetScope.AUTH` and
`ALL` install `AuthState()` directly. It neither acquires
`auth_mutation_span` nor composes `reset_operator_auth`. Uncommitted candidate
edits do not close this gate. This is not a new S37 blocker under the approved
sequencing, but it can bypass the recovery
intent and must be removed before release or any repository-wide
single-auth-writer claim. `W02.P05.S62` through `W02.P05.S64` remain mandatory.

### old-token-grounding | resolved-for-current-authority | Live source and semantic grounding resolve logout and reset

The executable source contains no `clear_operator_auth`, `AuthClearResult`,
`config.auth.clear`, or `clear` command registration. The live CLI lists
`logout` and `reset` and rejects `auth clear`. The current reference explicitly
marks the former graph retired, distinguishes historical records, and records
the generated-output refresh condition. Fresh semantic searches resolve that
reference and the current services. The known occurrence in generated
terminology/static artefacts remains assigned to the later regeneration wave
and is not an executable compatibility surface.

### auth-help-and-guidance | resolved | Provider help and shared error guidance are explicit

Both logout and reset render localized `--provider` help. The shared
`AuthOperationScopeConflictError` registry entry now suggests
`aeat config auth --help`, and focused tests assert the rendered help and
neutral error envelope.

### real-behavior-coverage | resolved | Real failure and concurrency oracles cover the former defect

The remediation tests use real encrypted profile storage, SQL revision
conflicts, SQLite abort triggers, session objects, acquisition-lock files,
certificate secrets, file-lock contention, and concurrent worker threads.
They contain no mocks, fakes, stubs, patches, monkeypatching, skips, or expected
failures. The focused recovery file passed all eight tests both serially and
under the configured parallel runner; the complete auth test directory passed
146 tests.

### certificate-secret-event-atomicity | high | Ordinary secret set/remove can commit before their audit event

This is a separate certificate-custody finding, not a failure of the
logout/reset cleanup journal. `set_operator_certificate_source_secret` writes
the `SecretStore` before recording its append-only event, and
`remove_operator_certificate_source_secret` deletes before recording its
event. A real SQLite-trigger reproduction made the later event transaction
fail: set returned an error while the secret remained present and a retry was
classified as rotation; remove returned an error while the secret was absent
and a retry could never emit the missing removal event.

Reclassify this concern from MEDIUM to HIGH because a security-sensitive
credential mutation can complete despite command failure and leave a missing
or incorrect audit trail. It does not block acceptance of S37 logout/reset,
whose reset path is protected by `AuthCleanupIntent`, but it is a pre-release
follow-up for the now-expanded `W02.P07.S48`, `W02.P07.S51`, and CLI proof in
`W04.P13.S118`. Those rows explicitly require a secret-free durable mutation
intent or outbox carrying a stable operation identifier, event kind and
timestamp, prior-presence state, and non-secret completion witness, plus real
failed-event-commit and retry tests for both set and remove.

### Resolution verification evidence

- Vaultspec-RAG semantic searches on port `8766` covered the audit, ADR, plan,
  execution record, current reference, CAS implementation, cleanup intent,
  session concurrency, duplicate writer, and certificate-secret event window.
- Recovery and concurrency suite: eight passed serially and eight passed under
  the configured parallel runner.
- Complete authentication application suite: 146 passed.
- Adjacent operator, certificate, secret-backend, and session slice: 74 passed.
- CLI auth, workflow, secure-object revision slice: 19 passed.
- Error-registry, destructive-confirmation, output-language, and workflow
  surface slice: 28 passed.
- Focused Ruff and `git diff --check`: passed.
- Uncached import-linter: 3,427 files, 16,219 dependencies, five contracts
  kept, zero broken. The remediation removes the auth adapter exemptions
  rather than adding architecture debt.
- Exact production scans of the committed S37 baseline found no retired
  executable auth-clear symbol or command and only the planned
  `config_reset.py` direct auth replacement.
- The revised S37 execution record contains the immutable composite
  commit/path attribution manifest and corrective commit evidence.
