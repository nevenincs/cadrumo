---
tags:
  - '#plan'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:9546363855ab6523ddb2257ea1b1bdfb57128e6d2bc13be459dcb4a70a6f9a8d'
tier: L2
related:
  - '[[2026-07-02-aeat-architecture-review-audit]]'
  - '[[2026-07-02-arch-remediation-program-adr]]'
  - '[[2026-07-02-arch-remediation-engine-lifecycle-adr]]'
  - '[[2026-07-06-arch-remediation-engine-lifecycle-research]]'
---
# `arch-remediation-engine-lifecycle` plan

### Phase `P01` - session-owner takeover

Make the bucket-session manager the single owner of engine lifecycle: lazy engine acquisition on first storage access, disposal on session close and switch, cache keyed on bucket identity, dispose_engine narrowed to an internal seam, explicit-database-URL route unchanged.

- [x] `P01.S01` - Make the bucket-session manager acquire the bucket engine lazily on first storage access within a session, registering the engine handle on the session; `src/aeat/adapters/persistence/storage/runtime.py`.
- [x] `P01.S02` - Dispose the bucket engine on session close and on profile switch through the same path that invalidates session state, so the two lifecycles cannot diverge; `src/aeat/adapters/persistence/storage/runtime.py`.
- [x] `P01.S03` - Re-key the engine cache on bucket identity rather than raw database URL, keeping the URL an implementation detail of engine construction; `src/aeat/adapters/persistence/storage/sql/engine.py`.
- [x] `P01.S04` - Narrow dispose_engine to an internal seam invoked by the session owner and the harness teardown only; `src/aeat/adapters/persistence/storage/sql/engine.py`.
- [x] `P01.S05` - Confirm the settings-driven explicit-database-URL route keeps its current direct engine path unchanged; `src/aeat/adapters/persistence/storage/sql/engine.py`.

### Phase `P02` - harness sweep

Sweep the shared secure-SQL test harness ephemeral and synthetic-session path onto the unified lifecycle in the same change, since the harness ships with the wheel and is production surface for this purpose.

- [x] `P02.S06` - Sweep the shared secure-SQL harness ephemeral and synthetic-session path onto the unified lifecycle so engine routing follows the session through the harness teardown; `src/aeat/tests/secure_sql.py`.
- [x] `P02.S07` - Confirm the harness synthetic-session roundtrip suites pass against the unified lifecycle; `src/aeat/tests/secure_sql.py`.

### Phase `P03` - regressions and cleanup

Pin the two contract regressions and delete the now-unnecessary scattered dispose_engine calls from the CLI lifecycle, rename, and navigation tests.

- [x] `P03.S08` - Add a regression asserting an in-process profile switch cannot observe the prior bucket engine, via an engine-identity assertion across a switch; `src/aeat/adapters/persistence/storage/tests/test_engine_session_lifecycle.py`.
- [x] `P03.S09` - Add a regression asserting closing a session disposes its engine, verified by pool inspection; `src/aeat/adapters/persistence/storage/tests/test_engine_session_lifecycle.py`.
- [x] `P03.S10` - Delete the now-unnecessary scattered dispose_engine calls from the CLI lifecycle, rename, and navigation tests whose choreography the unified lifecycle makes redundant; `src/aeat/entrypoints/cli/tests`.
- [x] `P03.S11` - Confirm the existing session-lifecycle and profile-navigation suites pass with the scattered disposals removed and the use-time readiness guards untouched; `src/aeat/entrypoints/cli/tests`.

## Description

This plan implements the engine and bucket-session lifecycle unification decided
by the engine-lifecycle ADR, discharging deferral register item D10. The
persistence audit found that SQLAlchemy engine identity does not track
bucket-session identity: the engine layer keeps a module-global cache keyed by
database URL while the unlocked-bucket session is a separate process-global, so
a profile switch inside one process can leave a stale engine for the previous
bucket's URL alive and cached. The visible symptom is test choreography, CLI
lifecycle tests call `dispose_engine()` four or more times per test to force the
cache to follow profile switches.

Phase P01 makes the bucket-session manager the single owner of engine lifecycle:
the engine is acquired lazily on first storage access within a session (the
cold-start budget requires creation to stay deferred), disposed on session close
and switch through the same path that already invalidates session state, and the
cache re-keys on bucket identity; `dispose_engine` narrows to an internal seam.
The settings-driven explicit-database-URL route keeps its current direct path.
Phase P02 sweeps the shared secure-SQL test harness ephemeral and
synthetic-session path onto the unified lifecycle in the same change, because the
harness ships with the wheel and is production surface for this purpose and is
the highest-coupling consumer. Phase P03 pins the two contract regressions (an
in-process profile switch cannot observe the prior bucket's engine; closing a
session disposes its engine) and deletes the now-unnecessary scattered
`dispose_engine()` calls from the CLI lifecycle, rename, and navigation tests.

The ADR freezes the surrounding contracts: no behavioural change to encryption,
session idle-expiry semantics, or the readiness taxonomy, and the use-time
readiness and session-freshness guards remain untouched as the second defence
layer. This plan is Wave 2 in the program: it lands before the ports-inversion
campaign (Wave 3), which touches every repository constructor and should build on
the unified lifecycle rather than before it.

## Steps

## Parallelization

The three phases are hard-ordered and single-owner. P01 (session-owner takeover)
is the load-bearing change and must land before P02 (harness sweep), because the
harness's synthetic-session path depends on engine routing following the session
under the new ownership. P03 (regressions and cleanup) lands last: the two
regressions pin the P01 contract and the scattered-disposal deletions are only
safe once the unified lifecycle makes that choreography redundant. Within P01
the steps proceed lazily-acquire, dispose-on-close, re-key cache, narrow
`dispose_engine`, confirm explicit-URL route, in that order, all against the two
persistence-layer files. This is a single-owner campaign confined to the storage
adapter plus the test surface; it does not touch the contended orchestrator hub
files.

## Verification

- P01: engine creation stays lazy (deferred to first storage access) and the
  settings-driven explicit-database-URL route keeps its current direct path
  (P01.S05); `dispose_engine` is an internal seam with no remaining production
  caller outside the session owner (P01.S04).
- P02: the shared secure-SQL harness synthetic-session roundtrip suites pass
  against the unified lifecycle (P02.S07).
- P03: `test_engine_session_lifecycle.py` pins that an in-process profile switch
  cannot observe the prior bucket's engine (P03.S08) and that closing a session
  disposes its engine by pool inspection (P03.S09); the existing
  session-lifecycle and profile-navigation suites pass with the scattered
  `dispose_engine()` calls removed and the use-time readiness guards untouched
  (P03.S11).
- The plan is complete when every Step is closed and each Step carries an exec
  record per the plan-closure discipline.
