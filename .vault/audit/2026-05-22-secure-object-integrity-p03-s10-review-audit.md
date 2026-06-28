---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---



# `secure-object-integrity` Code Review


S10-001 | HIGH | Initial subprocess environment did not guarantee root-fallback route

The first S10 test harness copied the parent environment and only removed `AEAT_DATABASE_URL`. Review found that parent `AEAT_ACTIVE_PROFILE` values or project `.env` content could make the child process classify as an explicit or active-bucket route, letting guarded write assertions pass through per-command no-active-profile handling rather than the root-fallback guard branch.

Status: resolved. The subprocess harness now filters parent `AEAT_*` variables, builds a real `Settings` object with `_env_file=None`, installs it inside the child process, and asserts `classify_storage_route()` returns `ROOT_FALLBACK_DATABASE` before dispatching the CLI.

S10-002 | MEDIUM | Guarded refusal tests did not prove root fallback storage stayed untouched

Review found that guarded write tests asserted refusal text but not whether a root fallback database had already been created.

Status: resolved. Guarded write tests now assert the fresh root does not contain `aeat.db` after refusal.

S10-003 | LOW | Subprocess invocations were unbounded

Review found that subprocess calls had no timeout, which could hang if the guard regressed and a live-adjacent command proceeded into slow work.

Status: resolved. The subprocess harness now uses a fixed timeout for each CLI invocation.

S10-004 | INFO | Final review

Final scoped review found no remaining critical or high blockers. The reviewer confirmed the child process forces the root-fallback route before dispatch, parent `AEAT_*` leakage is filtered, root fallback database absence is asserted after guarded refusals, subprocess calls have a timeout, and test-policy constraints are satisfied.
