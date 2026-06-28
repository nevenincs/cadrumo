---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-state-architecture-plan]]"
  - "[[2026-05-21-profile-state-aggregate-adr]]"
  - "[[2026-05-21-state-architecture-w01-audit]]"
---

# `cli-workflow-redesign` audit: state-architecture W02 close

Closing note for Wave 2 (profile aggregate + repository + cross-store
unit-of-work) of the state-architecture plan.

## What landed

| Commit | Content |
|---|---|
| `7f2090c25` | `ProfileAggregate` + `ProfileRepository` + `verify_profile_integrity` |
| `879204016` | rewire orchestration / CLI / wizard / setup through the repository |
| `9d3ff7b90` | tests |
| `e3ea93abc` | revision: sole-writer rename, atomic delete, integrity guard |
| `3e192f562` | revision: pointer-restore helper, rename delegation |
| `4d2b13d83` | revision: import-breakage repair + delete unit-of-work tests |

`ProfileAggregate` is one typed in-memory object owning a profile's
whole state. `ProfileRepository` is the single writer of the profile
physical stores; `create` and `delete` are cross-store units of work
with full rollback. `verify_profile_integrity` runs on every load and
surfaces cross-store drift as a typed error.

## Review trail

First review: design sound, one blocker + three majors -
B1 a deleted symbol left four tests `ImportError`-broken; M1 `rename`
wrote the manifest outside the repository; M2 the cold-start pointer
write sat outside the unit-of-work, leaving the `missing_profile_record`
torn state reachable; M3 `delete` non-atomic. All four fixed in the
revision. Re-review verdict: PASS - every finding genuinely closed;
M2 closed by construction and test-proven (the outer pointer-restore
handler is exercised by tests that fail if it is removed).

## Finding: W01 verification scope gap

The W01 cutover was verified only against `entrypoints/cli/_config`,
not the full `entrypoints/cli` tree. That left 17 stale name-as-id
test failures (`bucket_id == "operator"`, `active_profile == "default"`)
undetected. Surfaced during W02 verification; 14 fixed in `c69f776d3`
(resolve the active UUID at runtime, assert against it - no assertion
weakened). Lesson recorded: every wave verifies the full affected
tree, not a convenient subtree.

## Verification

- `application/user_profile`: 64 passed.
- Full `entrypoints/cli` tree: 3 failed, 467 passed (was 17 failed).
- The B904 lint the re-review flagged in a touched file is fixed.

## Deferred / handed off

- 3 CLI failures remain, all blocked by another campaign's
  uncommitted or same-day-committed foreign work:
  `test_workflow_surface.py` (two genuine UUID-cutover-debt cases, but
  the file carries a foreign `config auth login` WIP that must not be
  edited) and `test_backend_boundary.py` (a meta-test flagging the
  word `stub` in `test_live_portals_verbs.py`, committed today by the
  portal-naming campaign as legitimate domain language). Both must be
  closed once the foreign work commits / settles.
- An additive test inducing a master-key-activation failure on the
  cold-start `create` path - the M2 hole is closed by construction
  and covered by equivalence today; an explicit test is a later
  hardening checkpoint, not a correctness gap.
