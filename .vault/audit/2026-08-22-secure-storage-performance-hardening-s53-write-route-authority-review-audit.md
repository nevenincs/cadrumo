---
tags:
  - '#audit'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:f135dec1d00d672eb807e667d8caec9c072bdf84699d264e339e550e91894731'
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

### s53-write-route-authority-review | resolved | Recovery and root-refusal dispatch are proven

The five affected session and repair callbacks now declare the import-light
bootstrap-root policy. Exact-set gates reconcile mutating session exemptions
and require a named login-gate justification for bootstrap-root routes outside
that exemption set. A real root invocation now proves `config login` reaches
its target resolver on a fresh store, and two additional real root-dispatch
tests prove callback-attached profile-bound policy refuses both root-fallback
and explicit-database routes before either database file is created. The
focused storage-policy, root-guard, typed-projection, operator-surface, and MCP
parity suites pass with 31 tests; Ruff passes on the corrective surface. The
high finding is closed.

### s53-write-route-authority-review | medium | Deleted leaf-refusal heuristic remains declared in quality metadata

The production `_delegates_to_leaf_refusal` mutation heuristic was deleted,
but `dev/quality/modelo_branch_classification.toml` still declares its former
`storage_write_policy.py` branch and selector. This is a stale consumer of the
retired legacy mechanism and makes the branch-classification authority claim a
live M210 decision site that no longer exists. Delete that complete branch
record and run its owning quality gate so the required legacy deletion is
truthful beyond production imports.

### s53-write-route-authority-review | resolved | Retired heuristic metadata is absent

The complete stale branch-classification row was deleted. Exhaustive searches
find no remaining production or quality references to the retired write-path
catalogue, prefix matcher, mutation heuristic, or leaf-refusal delegation.
Direct reconciliation reports no unclassified, stale, or broken-citation item
for `storage_write_policy.py`; the owning full gate remains red only on eight
unclassified and five stale M303 rows introduced by unrelated shared-tree
work, with zero broken citations. The S53 medium finding is closed on scoped
authoritative evidence; the unrelated branch-ledger drift remains owned by its
concurrent campaign.

## Recommendations

- The high finding was resolved in S53; retain the real-dispatch and exact-set
  reconciliation gates as binding coverage for future callback additions and
  policy changes.
- The retired branch-classification record is removed. Preserve the zero-match
  legacy-symbol search and scoped reconciliation alongside the dispatch gates.
