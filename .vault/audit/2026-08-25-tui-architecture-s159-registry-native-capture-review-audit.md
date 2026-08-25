---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:110b43d798032660943d955abfdca0353a89d5004c30f8ab69299733ef60c1f7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-25-tui-architecture-workspace-owner-seam-reconciliation-audit]]"
  - "[[2026-08-11-tui-architecture-W03-P20-S159]]"
---
# `tui-architecture` audit: `S159 registry native capture review`

## Scope

Independent current-HEAD review of the combined S159 implementation, facade,
tests, and lifecycle records carried by commits `8c845ab92f` and `d42da6d435`.
The review was grounded in the accepted registry API gate ADR, the reconciled
owner-seam audit and composition references, `W03.P20.S159` and its execution
record, and the always-on registry, dependency-boundary, no-legacy, and quality
rules. Vaultspec RAG semantic discovery landed on the native capture in
`src/cadrumo/domain/calculations/registry/_authority.py`; a current-HEAD exact
census then covered the complete authority, public facade, focused capture
tests, identity-keyed load/cache transitions, reset interactions, and the S167
consumer seam.

The public facade promotion, single production capture home, absence of lower-
layer `ModeloWorkspace` imports, law-selected inspection-versus-graded-snapshot
delegation, deep-copy separation from the authority cache after capture,
monotonic allocation for newly constructed authorities, and explicit-reset
stale-instance refusal passed. The focused capture suite passed with five tests.
Acquisition order inside the reviewed module is consistently process-global
lifecycle lock before per-authority state lock; no in-module inversion or
deadlock was found.

## Findings

### authority-identity | high | Same-root A to B to A transitions leave stale authorities current and reuse the original generation

`ValidatedRegistryAuthority.load` resolves the current `RegistryIdentity` and
keys its LRU by that identity, but the identity is not retained as a currentness
coordinate on the authority (`src/cadrumo/domain/calculations/registry/_authority.py:169`).
`_require_current_capture_incarnation` checks only the explicit-reset epoch
(`src/cadrumo/domain/calculations/registry/_authority.py:419`). Loading changed
same-root tree B therefore creates a later generation while the old A instance
continues to capture and report its earlier generation as current. Restoring A
then hits the still-resident A LRU entry and reuses the original A object and
generation rather than allocating a later A generation. This violates the ADR's
every-owner-transition, A to B to A, no-reuse, and current-generation guarantees
and allows S167's two-pass validation to accept a stale owner instance.

The focused test covers only A to explicit reset to A
(`src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py:106`).
Existing authority tests prove same-root identity replacement without the
global reset, but the native-capture suite never asks the predecessor to refuse
or proves A to B to A generation monotonicity.

### reset-linearization | high | Reset can race an in-flight load and publish pre-reset state afterward

Identity collection and `_load_authority` execute outside the lifecycle lock,
while reset invalidates generations and clears the authority caches under that
lock and then clears compiled-tree and fingerprint caches only after releasing
it (`src/cadrumo/domain/calculations/registry/_authority.py:169`,
`src/cadrumo/domain/calculations/registry/_authority.py:574`, and
`src/cadrumo/domain/calculations/registry/_authority.py:583`). An in-flight load
can cross that boundary, repopulate the LRU after its clear, or construct in the
new reset epoch from inputs obtained before the reset. The unlocked failure-
cache write can likewise repopulate a refusal after reset. The result can be an
apparently current authority over pre-reset inputs or a cached authority that is
already stale when returned. No focused test races reset against load.

### cache-singleflight | medium | Concurrent cold loads can mint multiple current generations for one unchanged tree

`_load_authority` has no single-flight boundary around an LRU miss
(`src/cadrumo/domain/calculations/registry/_authority.py:549`). Standard LRU
memoization permits duplicate underlying calls while the first call is still
computing. Each duplicate constructs an authority and allocates a different
generation, yet both carry the same reset epoch and both pass the currentness
check. Cache warm-up alone can therefore create multiple simultaneously current
generations without an owner-state transition and cause false
`workspace_changed` outcomes. The concurrency test uses one already-created
authority and does not exercise concurrent loading.

### snapshot-isolation | medium | Cached snapshot aliases can mutate or tear a capture without advancing generation

`snapshot` returns its cached `RegistrySnapshot` directly, including mutable
nested mappings (`src/cadrumo/domain/calculations/registry/_authority.py:352`).
The capture deep-copies that object under authority locks, but a caller already
holding the cached alias can mutate a nested mapping without either lock. Such a
mutation can change or race the captured projection without a generation
advance, so the lock does not establish the required immutable or
snapshot-isolated owner value. The focused isolation test proves only that
mutating the returned capture does not mutate the cache; it does not prove the
reverse direction or concurrent mutation safety.

### global-lock-scope | medium | The lifecycle lock serializes all registry validation and snapshot work process-wide

`_AUTHORITY_CAPTURE_LOCK` is process-global (`src/cadrumo/domain/calculations/registry/_authority.py:82`)
and wraps `validate_modelo`, `inspect_revision`, `validate_registry`,
`mark_registry_validated`, and `snapshot` as well as capture and reset
(`src/cadrumo/domain/calculations/registry/_authority.py:200`,
`src/cadrumo/domain/calculations/registry/_authority.py:226`,
`src/cadrumo/domain/calculations/registry/_authority.py:240`,
`src/cadrumo/domain/calculations/registry/_authority.py:264`, and
`src/cadrumo/domain/calculations/registry/_authority.py:352`). Full corpus
validation, snapshot construction, and capture copying for unrelated roots and
authority instances cannot overlap. The concurrency test asserts only equal
results, so a completely serialized implementation passes. Acquisition order is
consistent and no deadlock was found, but the scope is broader than the
generation/reset critical section and introduces process-wide head-of-line
blocking into all existing registry reads.

## Recommendations

- Resolve `authority-identity` with a per-root current-incarnation coordinate:
  retaining A must not let it survive B, and returning to A must allocate a
  generation later than B without invalidating unrelated roots.
- Resolve `reset-linearization` and `cache-singleflight` with one per-root
  load/reset publication protocol. Reset must linearize against identity
  collection, construction, success publication, and failure publication; an
  unchanged cold key must construct one authority generation.
- Resolve `snapshot-isolation` by making cached projections deeply immutable or
  preventing mutable cached aliases from escaping. Prove mutation-before-
  capture and mutation-during-capture cannot alter or tear the native value
  without a generation transition.
- Resolve `global-lock-scope` by separating the short lifecycle/current-
  incarnation critical section from per-authority state locking. Preserve the
  consistent lock order and add an overlap proof for unrelated roots rather
  than an equality-only concurrency test.
- Add real A to B to A, concurrent cold-load, load-versus-reset, cache-alias
  mutation, and unrelated-root overlap tests while retaining the passing public
  facade, one-home, law-selection, no-Workspace, and no-shim/no-alias/no-
  fallback proofs.

## Disposition

FAIL. S159 cannot close as the registry-native owner seam for S167 while
same-root transitions leave old instances current and reuse A's generation and
while reset is not linearized against authority publication. Concurrent cold
loads and mutable cached aliases add false-generation and isolation failures.
The process-global lock has a consistent order and no observed deadlock, but
unnecessarily serializes all registry validation and snapshot work.
