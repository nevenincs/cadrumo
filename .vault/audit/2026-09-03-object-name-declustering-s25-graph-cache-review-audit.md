---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:f775d99428f9c475385ed0e27f04cd097188fab7970681ad54f5a55827b0e073'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `S25 graph cache review`

## Scope

Reviewed the S25 receipt-local Grimp cache implementation and focused tests against the
approved plan, execution record, accepted declustering ADR, and the existing graph and
rehearsal safety contracts. The review covered live-to-copy cache identity, all-import versus
runtime-only graph isolation, snapshot byte and metadata races, cache path/link safety,
retained-evidence behavior, cleanup, and whether the tests prove actual cache reuse. No
implementation or test code was modified.

## Findings

### cache-source-identity | medium | Warm cache input is not proven equal to the verified snapshot

Every copied Python file is hash-checked against `baseline_files`, and `copystat` preserves
metadata so Grimp can reuse its live-tree cache. However, the live graph is warmed after the
baseline hashes are captured, and no post-build check proves that Grimp read those same
bytes. A Python file can change between `_snapshot` and the live `build_graph` call and then
return to the snapshotted bytes before `_copy_snapshot`; the copy passes exact hash checks,
while its preserved metadata may still satisfy Grimp's cache invalidation scheme. The copied
graph can therefore be served from evidence derived from bytes other than the verified copy.
Canonical component comparison and the transform's exact changed-path checks limit practical
impact and usually refuse drift, so this is medium rather than high, but the cache reuse
claim lacks an exact content-identity bridge at its authorization boundary.

### cache-reuse-detector-teeth | medium | Tests prove forwarding, not a real warm-cache hit

The amended rehearsal test observes two calls to
`canonical_object_name_component_set`, asserts they receive the same directory, and checks
that the directory is a sibling of the retained repository. It still passes if Grimp ignores
the cache, invalidates every entry, or rebuilds both graphs from the disposable copy. No test
observes cache artifacts or otherwise makes the second graph construction depend on valid
reuse, and no stale-cache test changes bytes while preserving cache-relevant metadata. The
suite therefore cannot distinguish the intended optimization from a no-op cache argument or
detect unsafe metadata-only reuse.

No separate defect was found in all/runtime graph isolation: both option variants are built
through Grimp's public API and independently compared in edge classification. The cache
directory is created inside a freshly allocated, resolved system-temporary parent and outside
the repository copy, so it cannot enter changed-path discovery. The fresh parent prevents a
pre-existing link at creation time; successful rehearsals retain the parent, repository, and
cache together, while failures report that retained root. Existing copy traversal rejects
link-like repository paths, and Python files are included in the exact copy-hash set.

## Recommendations

For `cache-source-identity`, bind the warm graph to the exact snapshot. One safe shape is to
verify all live Python hashes again immediately after warming and refuse if they differ from
the baseline before allowing the copied tree to consume that cache; preserve and verify the
metadata used for reuse as part of the same bounded interval. Alternatively warm the cache
only from the already verified disposable copy and reuse it only within that immutable copy.

For `cache-reuse-detector-teeth`, add a detector that proves the second construction consumes
the first construction's artifacts rather than merely receiving the same path. Pair it with
a same-size, metadata-preserving content mutation that must invalidate or refuse stale cache
evidence, plus an assertion that all-import and runtime-only results cannot contaminate one
another.

## Validation

The complete focused graph and rehearsal suites passed 46 tests in 56.92 seconds. Ruff lint,
Ruff format, and ty passed for all four S25 files. Final review status is two medium findings
and no critical, high, or low findings.
