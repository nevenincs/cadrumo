---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:bd9a0a248d82d0d3cd5dead6feb3e4472df7dfa668041de9b9d1f8340f5c0441'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# `secure-storage-performance-hardening` audit: `S53 write-route authority review`

## Scope

Independent review of `W01.P01.S53` against the accepted callback-attached
write-route authority, real root dispatch, fail-closed classification,
proportional imports, complete deletion of the former profile-bound verb-path
catalogue and its consumers, and preservation of bootstrap/recovery behavior.
The review inspected the current uncommitted diff and current HEAD, searched
for retired symbols and consumers, compared live callback routes with existing
dispatch exemptions, ran the focused policy/entrypoint/operator/MCP tests, and
exercised the real `config login` root callback on a fresh store.

## Findings

### s53-write-route-authority-review | high | Recovery doors are misdeclared profile-bound and now refuse before their handlers

The live callback policy declares `config login`, `config logout`, `config
repair profile`, `config repair quarantine`, and `config repair reset-progress`
with `write_route="profile-bound"`, while the root now applies the fallback
route refusal from that declaration before reaching the existing bootstrap
session exemption. On a fresh store, a real `CliRunner` invocation of `config
login does-not-exist` now returns the generic no-active-profile refusal instead
of reaching login's target resolver and reporting the unknown profile. This
breaks the recovery door that establishes the very session other
profile-bound commands require. The deleted integration coverage previously
pinned that behavior, but the replacement tests call
`inspect_storage_write_policy` directly and inspect root source text; none
dispatches a guarded or recovery callback through the root. Correct the
callback declarations or routing semantics so these bootstrap/recovery
callbacks reach their handlers without opening or resuming a prior active
session, and restore real-dispatch tests for root-fallback and explicit-URL
refusal plus recovery-path reachability.

## Recommendations

- Resolve the high finding before closing S53. Derive the root decision solely
  from the selected callback's validated policy, preserve the login/logout and
  repair recovery doors, and prove the behavior at the real root dispatch
  boundary rather than through direct policy-query calls or source inspection.
