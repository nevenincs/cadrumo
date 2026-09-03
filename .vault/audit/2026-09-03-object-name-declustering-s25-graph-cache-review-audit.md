---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:a1df0138b0862881f45f514dffe136ca7438885272527c5e28fe1e9ef9d7228c'
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

## Redesign resolution

Resolved: `cache-source-identity` is closed by removing Grimp caching from this workflow.
Rehearsal now snapshots and copies first, requires every copied Python file to match its
captured content digest, scans the copied inventory, and constructs the canonical graph
exactly once from the isolated disposable tree. That graph is compared by component ID,
operation membership, affected paths, and hard edges to the supplied component before any
transformation. No live-tree graph evidence or metadata-based cache artifact crosses into
the authorization decision.

Resolved: `cache-reuse-detector-teeth` is closed by removing the behavior it covered. The
amended detector observes exactly one canonical reconstruction and asserts its root is the
retained disposable repository. The copy-race detector mutates a copied consumer to introduce
a selected reference before graph reconstruction and production refuses the undeclared hard
edge. Existing post-copy corruption coverage verifies that a Python copy changed during
copying is refused before graph use. Link traversal, source disappearance, exact guarded
bytes, copied component equality, changed-path equality, and later replay freshness remain
fail-closed.

### redesigned-format-gate | medium | Current S25 test bytes fail the recorded format check

The focused runtime suite, Ruff lint, and ty pass, but Ruff format currently reports three
`pytest.raises` blocks in `test_object_name_rehearsal.py` that would be reformatted. The S25
execution record says the same format check passes, so the record does not describe the
reviewed bytes and the approved quality gate is not presently green. This is mechanical and
does not weaken the redesigned safety semantics.

## Final re-review validation

The complete graph and rehearsal suites passed 46 tests in 45.43 seconds. Ruff lint and ty
passed. Ruff format failed on the three blocks described above. Final S25 status is one
medium finding and no critical, high, or low findings.

## Final hardening resolution

Resolved: `redesigned-format-gate` is closed. The current S25 implementation and test files
pass Ruff lint, Ruff format, and ty.

The strengthened default and explicit rehearse paths no longer derive a graph from live
bytes. CLI scans the inventory and validates the manifest, then passes `component=None` into
rehearsal. Rehearsal captures the tracked and relevant untracked tree, copies it outside the
worktree, verifies every copied Python file against its captured digest, rescans declarations
from that copy, builds the canonical graph exactly once under isolated import state, and
requires the manifest to resolve to exactly one complete component. Only that copied
component determines generator paths, transform operations, the changed-path allowlist, and
receipt identity. Plan and apply retain their live `_context` boundary; replay additionally
performs its exact disposable preflight with the caller-supplied current component.

This preserves fail-closed behavior under copy and reference races. A Python source changed
during copying fails its exact digest check before graph discovery. A copied reference added
after the copy helper's verification is discovered by the one canonical graph and refused
when outside the reviewed allowlist. Missing or stale selected findings cannot form the
copied manifest component, multiple independent components are refused, and all subsequent
transform output, finding-delta, generator, gate, and changed-path checks remain bounded to
the derived component. The CLI detector asserts rehearsal receives `None`, while the
rehearsal detector asserts the sole canonical reconstruction is rooted in the retained copy.

The combined graph, rehearsal, and CLI suites passed 85 tests in 69.29 seconds. Ruff lint,
Ruff format, and ty passed for all six reviewed implementation/test files. Final S25 status
is no findings at any severity.

## Scoped-copy adjustment

The final implementation deliberately narrows copy-time digest equality to declared inputs
and reviewed changed paths. This supersedes the preceding statement that every copied Python
file must remain equal to the earlier live snapshot. With no cross-tree cache, unrelated
Python metadata is irrelevant: the one disposable graph is built from the bytes actually
copied, so an unrelated concurrent edit is incorporated into that rehearsal rather than
mistaken for earlier evidence. A relevant reference appearing in those bytes changes the
canonical component or violates its changed-path allowlist and is refused. Declared inputs
and mutation targets remain exactly hash-bound; disappearance or corruption of those paths
is rejected before transformation.

This tradeoff remains fail-closed at live mutation time. Rehearsal records the outputs,
finding delta, tools, generators, and gates produced from its copied graph. Replay reconstructs
a fresh disposable graph and requires exact component and evidence agreement before writing,
then retains its immediate transaction race checks and rollback. Unrelated copy races may
therefore coexist without invalidating a leaf operation, while races that affect the selected
component cannot authorize stale mutation.

Focused detector validation passed the scoped receipt, guarded-copy corruption, and
copy-race-added reference cases (3 tests in 8.57 seconds). Ruff lint, Ruff format, and ty
passed for the adjusted rehearsal files. Final S25 status remains no findings at any
severity.
