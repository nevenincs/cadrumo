---
tags:
  - '#adr'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - "[[2026-07-02-aeat-architecture-review-audit]]"
  - "[[2026-07-02-arch-remediation-program-adr]]"
  - '[[2026-07-06-arch-remediation-engine-lifecycle-research]]'
---
# `arch-remediation-engine-lifecycle` adr: `engine and bucket-session lifecycle unification` | (**status:** `accepted`)

## Problem Statement

The persistence audit found that SQLAlchemy engine identity does not track
bucket-session identity: the engine layer keeps a module-global cache
(`_engines`, keyed by database URL) while the unlocked-bucket session is a
separate process-global, so a profile switch inside one process can leave a
stale engine for the previous bucket's URL alive and cached. Today misuse is
backstopped at use-time (the readiness runtime's `ROUTE_NOT_ACTIVE_BUCKET`
refusal, the repository's session-freshness check), and the hazard is most
visible as test choreography: CLI lifecycle tests call `dispose_engine()`
four or more times per test to force the cache to follow profile switches.
Lifecycle management has leaked to callers; the audit registered it as D10
and the operator directed deferrals into regression scope.

## Considerations

- The two globals have different owners today: the engine cache belongs to
  the SQL adapter (`storage/sql/engine.py`), the active-session state to the
  storage runtime; nothing ties disposal to session close/switch.
- The use-time backstops are real and must survive: defence-in-depth stays;
  this ADR moves enforcement earlier, it does not replace the guards.
- The test harness's synthetic sessions (the `ephemeral` bucket id used by
  the shared secure-SQL fixture) depend on engine routing following the
  session — unification simplifies that harness rather than breaking it,
  but it is the highest-coupling consumer and must be swept in the same
  change.
- The CLI cold-start budget (the lazy command-tree discipline) requires
  engine creation to remain lazy: unification binds DISPOSAL to the session
  boundary; creation stays deferred to first storage access within a
  session.
- WAL/busy-timeout multi-process semantics are engine-configuration
  concerns and are untouched; this decision is purely in-process lifecycle
  ownership.

## Considered options

- **Option A: status quo plus documentation.** Pro: zero change. Con: the
  audit's evidence is that callers already pay the cost (scattered
  disposals) and the stale-engine window is real; rejected.
- **Option B: no caching — fresh engine per storage access or per verb.**
  Pro: eliminates staleness by construction. Con: connection churn, WAL
  checkpoint pressure, and per-verb latency against the cold-start budget;
  rejected.
- **Option C (chosen): bind engine disposal to the bucket-session
  lifecycle.** The session owner acquires/creates the engine lazily on
  first storage access and disposes it on session close or switch; the
  cache keys on bucket identity rather than raw URL; `dispose_engine`
  becomes an internal of the session owner.

## Constraints

- No behavioural change to encryption, session expiry semantics
  (idle-timeout refusal), or the readiness taxonomy — the typed readiness
  codes and `SessionExpiredError` contract are frozen surfaces other layers
  cite.
- The shared test harness (`cadrumo.tests.secure_sql`) and the ephemeral
  synthetic-session path must be swept in the same change; the harness is
  in-package and ships with the wheel, so its contract is production
  surface for this purpose.
- Settings-driven explicit database URLs (the non-bucket route the
  readiness runtime classifies) must keep working: the session owner
  manages bucket-routed engines; explicit-URL engines keep the current
  direct path.
- Parent stability: depends only on the existing session and engine
  surfaces; no frontier risk. Sequenced in Wave 2 (program ADR) because the
  ports-inversion campaign (Wave 3) touches every repository constructor
  and should land against the unified lifecycle, not before it.

## Implementation

One owner, two hooks. The bucket-session manager becomes the single owner of
engine lifecycle for bucket-routed storage: opening a session registers the
bucket's engine handle (created lazily on first storage access), and the
close/switch path disposes it — the same path that already invalidates the
session state, so the two lifecycles cannot diverge. The engine cache keys
on bucket identity; the URL remains an implementation detail of engine
construction. `dispose_engine` narrows to an internal seam invoked by the
session owner (and by the test harness's teardown), and the scattered
per-test disposal calls are deleted as each test's choreography becomes
unnecessary. Two regressions pin the contract: an in-process profile switch
cannot observe the prior bucket's engine (identity assertion across a
switch), and closing a session disposes its engine (pool inspection). The
use-time guards remain untouched as the second layer.

## Rationale

The audit's framing holds: coupling enforced at use-time, not at the
lifecycle boundary, is why callers carry disposal choreography. Binding
disposal to the session close/switch path puts the invariant where the
state transition happens, matching how the substrate already treats the
session as the custody boundary for key material — the engine is just the
last resource that had not joined that boundary. Option B was rejected on
measured grounds (the busy-timeout/WAL configuration exists precisely
because engines are long-lived within a session).

## Consequences

- Test suites simplify materially: the repeated `dispose_engine()` calls in
  CLI lifecycle, rename, and navigation tests become deletable, and a class
  of flaky stale-engine failures becomes structurally impossible.
- The stale-engine window across in-process profile switches closes at the
  boundary instead of at first misuse.
- Risk: long-lived processes (MCP server) hold sessions longer than CLI
  invocations; the session idle-expiry already bounds this, and disposal on
  expiry rides the same unified path.
- Small migration cost in the harness and any test that constructed engines
  directly; one-time, swept with the change.
- Opens a follow-on: per-bucket pool sizing and instrumentation get a
  natural single home once the session owner owns the engine handle.
