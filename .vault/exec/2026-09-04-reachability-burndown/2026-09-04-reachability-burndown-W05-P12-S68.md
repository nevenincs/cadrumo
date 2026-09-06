---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:53f1edc3f6229d1b6f5eab5c23f8c6b6c51691db647b2fa4e5520f8a10337300'
step_id: 'S68'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Re-test the remaining session port facades and reverse two: the idle-deadline advance is reached through the port object rather than the module-level facade, with the login session service calling the acceleration advance method and the storage adapter implementing it by the persisted-session advance, so the behaviour the facade wraps happens without it; and the persisted-session type guard narrows an untyped object that nothing supplies, because the adapter annotates the port directly on the functions that take and return it and constructs the concrete record itself

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` ledger validated by direct script -- closed class vocabulary, evidence
  present, no symbol in two clusters, every cited path resolving to a named subject

## Notes

A near-miss worth recording: the first grep for idle-deadline handling returned
the AEAT BROWSER session, which refreshes its own `idle_deadline` against
`AEAT_SESSION_IDLE_TTL`. That is a different subject from the profile login
session, and reading it as the live path would have produced the right verdict
by the wrong evidence. The actual live path is the port method, called from the
login-session service and implemented in the storage adapter.

The port-facade cluster is now down to one symbol from four; three of the four
reversed on re-test, all for the same reason -- callers reach the behaviour
through the port object or a typed mapper rather than the module-level helper.
