---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b21641903b8bfa36e90d41d7047be83592d12d7f4508450c9c9646a850152e59'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-W02-P05-S28]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-research]]"
---

# `tui-architecture` audit: `S28 recovery review`

## Scope

Independent read-only review of `W02.P05.S28`, commit `84686da7077`, the
current `src/cadrumo/application/operations/tests/test_supervisor_recovery.py`,
the production supervisor and operation persistence adapters, and the
accepted supervisor, cursor, cancellation, deadline, and reconciliation
authority. Production code, tests, the plan, and the existing execution record
were not modified.

The focused real-adapter lane was rerun with the four S28 tests plus the three
pre-existing cancellation and deadline tests cited by the execution record:
seven tests passed in 3.39 seconds with `-n 0`. This confirms current behavior
is green but does not supply the missing acceptance assertions described below.

## Findings

### acceptance-scope | high | S28 omits its commissioned cancellation and deadline race proof

The plan requires detach, cursor replay, duplicate-response refusal,
cancellation races, deadline races, and restart reconciliation with real
journal storage. `test_supervisor_recovery.py:39-187` never declares a
cancellation or deadline capability and never requests cancellation. The
execution record instead narrows the Step to four recovery tests and delegates
the omitted clauses to pre-existing S24 coverage in `test_supervisor.py`, while
its recorded command ran only the four-test S28 module. Commit `84686da7077`
therefore supplies neither an S28 review nor executed close evidence for every
commissioned clause; it adds an S27 audit and an execution record that itself
says S28 remains open. A Step cannot narrow its own completion criterion, so
S28 cannot close on this evidence.

### cursor-reconnect | medium | The detach test never replays events missed by a new observer

`test_supervisor_recovery.py:50-56` submits, starts, detaches, and replays from
cursor zero through the same supervisor, without committing any event after
detach. The assertion proves a full initial journal read is contiguous, but it
does not prove the accepted D3 contract that a new observer reconnects from a
saved nonzero cursor and receives only events missed while detached. A
supervisor-local replay dependency or an inclusive-cursor regression could
survive this test.

### reconciliation-persistence | medium | Returned recovery state is not reloaded from its durable authority

The resumable case at `test_supervisor_recovery.py:144-152` checks the returned
snapshot and one filtered reconciliation outcome but does not reload and
compare the durable successor or assert takeover ownership. The interruption
case at `test_supervisor_recovery.py:184-187` checks only the object returned by
`reconcile`; it does not reload the journal, verify the reconciliation event,
or establish exact lease release. Those assertions are necessary to prove that
the supervisor persisted authoritative recovery state instead of merely
returning an in-memory successor.

### inherited-owner-restart | low | Duplicate refusal proves re-instantiation under inherited live authority

`test_supervisor_recovery.py:84-94` recreates the supervisor with the same
owner identity and lease token. This usefully proves durable interaction
consumption across object re-instantiation, but it is not an owner-loss restart
or takeover proof. The latter belongs to the reconciliation cases, so this
test's claim should remain limited to same-owner supervisor reconstruction.

### acceptance-scope-resolution | high | Resolved by S28-owned cancellation and deadline race cases

Resolved on 2026-08-24. `test_supervisor_recovery.py:264-389` now declares the
real cooperative cancellation and deadline capabilities, races them against a
running executor after detach, reloads settling and terminal snapshots through
a separately constructed filesystem journal adapter, and verifies exact lease
release and resource cleanup. The focused six-test S28 lane passed in 3.02
seconds with `-n 0`; the execution record no longer delegates these obligations
to S24.

### cursor-reconnect-resolution | medium | Resolved by nonzero missed-event replay through a fresh observer

Resolved on 2026-08-24. `test_supervisor_recovery.py:50-91` saves the initial
nonzero cursor, detaches, commits a response event, reconstructs journal, lease,
secure-reference, and supervisor objects, and replays from the saved cursor.
It proves the fresh observer receives exactly sequence `saved_cursor + 1`, and
that the replay cursor and reloaded durable snapshot agree.

### reconciliation-persistence-resolution | medium | Resolved by journal reload and exact lease assertions

Resolved on 2026-08-24. `test_supervisor_recovery.py:139-197` reloads and
strictly compares the resumed durable snapshot, then verifies the exact active
takeover owner, token, scope, acquisition, and expiry. Lines `206-259` reload
the interrupted terminal snapshot and reconciliation event and prove the lease
is absent after settlement. Both paths use newly constructed real persistence
adapters.

### inherited-owner-restart-resolution | low | Resolved by honest same-owner naming

Resolved on 2026-08-24. The test and execution record now describe same-owner
supervisor reconstruction, while the separate reconciliation cases retain the
owner-loss and takeover claims.

### formatting-closeout | low | Ruff format check remains red

The focused integration lane and Ruff lint check pass, but `ruff format
--check` reports that `test_supervisor_recovery.py` would be reformatted at its
repository-construction and initial cursor assertions. The scoped quality gate
is therefore not fully green.

### exec-attestation | low | The remediated execution record has an unstamped body edit

`vaultspec-core vault check modified-stamp --feature tui-architecture` reports
that `2026-08-11-tui-architecture-W02-P05-S28.md` still carries its 2026-08-14
stamp and an obsolete body fingerprint after the remediation rewrite. The
record's narrative is accurate, but its machine-owned attestation is not.

### formatting-closeout-resolution | low | Resolved by canonical Ruff formatting

Resolved on 2026-08-24. `ruff check` passes and `ruff format --check` reports
that `test_supervisor_recovery.py` is already formatted.

### exec-attestation-resolution | low | Resolved by CLI-owned re-attestation

Resolved on 2026-08-24. The S28 execution record now carries modified date
2026-08-24 and a body fingerprint matching its remediated content.
`vaultspec-core vault check modified-stamp`, `frontmatter`, and `exec-mapping`
all pass for `tui-architecture`.

## Recommendations

Keep `W02.P05.S28` open. Add explicit real-journal cancellation and deadline
race cases to the S28 acceptance module, or formally rerun and adjudicate the
existing cases as S28 evidence without narrowing the Step. Strengthen cursor
replay with a saved nonzero cursor, a post-detach durable event, and a newly
constructed observer. Reload the journal and inspect exact lease state after
resume and interruption before accepting their returned snapshots as durable
truth. Then rerun the complete scoped lane and commission a fresh independent
review.

Re-review result: the original HIGH and MEDIUM findings are resolved with real
adapters, and no new supervisor or persistence-authority defect was found. Keep
S28 open only until the Ruff format check is green and the execution record is
re-attested through the Vaultspec owning verb. After those two mechanical
closeout items pass without changing the reviewed semantics, S28 may close
without another architecture review.

Final closeout result: every HIGH, MEDIUM, and LOW finding in this audit is
resolved. The reviewed six-test real-adapter evidence remains substantively
accepted, the scoped Ruff gates are green, and the execution record is validly
attested. Accept `W02.P05.S28` as PASS; S28 may close.
