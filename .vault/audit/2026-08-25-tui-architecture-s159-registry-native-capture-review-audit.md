---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:d12faa966ff5c9ba2f456f17802e4668d8f0b059c65d71bb1306df4d608101c3'
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

## Remediation re-review - 2026-08-25

### Scope and evidence

Fresh independent re-review of the remediated S159 implementation carried by
`d8d47ee410` and the concurrent-reset correction `45b1948b28`, with the final
source reread at current HEAD `57559437ef0`. The later S159-file delta is
formatting-only. The plan Step remains open. This section preserves the
historical FAIL findings above and reports their current disposition; it does
not rewrite the earlier evidence.

Vaultspec RAG semantic discovery initially located the governing Workspace
owner-seam ADR, this audit, the S159 Step and execution record, and the native
authority implementation. At final re-query the `0.4.2` client refused the
shared `0.4.1` daemon rather than silently dropping request fields, while the
available local publication reported zero of its declared 104,579 code points.
The semantic index was therefore treated as lagging discovery evidence only.
Every current-state and absence conclusion below comes from whole-file reads
and an exact committed-source census at current HEAD.

### Prior findings after remediation

- `authority-identity` is resolved. One root-and-source-root state owns the
  current key, authority, failure, generation and transition lock. Every
  observed A to B to A change invalidates the predecessor before construction,
  allocates a strictly later process-local generation, and never revives an
  identity-keyed historical object.
- `reset-linearization` is resolved. The reader/writer barrier covers identity
  collection, construction, success or failure publication, invalidation and
  every registry cache clear. Reset drains in-flight publication and concurrent
  reset writers exclude one another.
- `cache-singleflight` is resolved. The root-scoped transition lock admits one
  construction for one observed key and reuses exactly one published success
  or deterministic failure.
- `snapshot-isolation` is resolved. The authority-private snapshot is the sole
  cache entry; public snapshot reads and native captures return distinct deep
  copies, so mutation of a caller-held public alias before or during capture
  cannot change or tear the captured owner value.
- `global-lock-scope` is resolved in production behavior. Long identity,
  compilation, validation, snapshot and copy work runs under root-scoped or
  per-authority locks. The process-global state lock protects only short
  generation and publication transitions, and unrelated roots reached
  construction concurrently in the reviewer probe.

### unrelated-root-overlap-regression | low | Concurrent-root independence lacks a committed biting regression gate

The remediated production implementation permits unrelated roots to perform
long construction concurrently, and an independent barrier probe proved both
distinct roots entered `_construct_authority` before either was released.
However, no committed S159 test encodes that property. The nine focused native
capture tests can all pass if a future change restores a process-global lock
around long registry work. The earlier audit explicitly required an overlap
proof, and the execution record now claims this behavior. Add the same
two-root barrier proof to
`src/cadrumo/domain/calculations/registry/tests/test_authority_native_capture.py`
so re-serialization makes the durable gate red.

### Verification

- Ruff passed for the authority, facade and both focused authority test files.
- Basedpyright passed the same surface with zero errors and warnings.
- The native capture suite passed 9 tests. The authority, cache-key digest,
  read-parameter invalidation and validation-verdict lanes passed 27 tests.
- Independent probes passed eight physical A/B alternations with generations
  `2` through `9` and predecessor refusal; concurrent same-key failure
  singleflight, replay and reset clearing; reset versus blocked failure
  publication; two-root long-work overlap; and 12 reset writers completing amid
  24 continuous readers without observed deadlock or starvation.
- The exact committed-source census found one production
  `RegistryAuthorityCapture`, `capture_law_selected_projection` and
  `read_current_generation` home in `_authority.py`, one permitted canonical
  package-facade promotion, zero lower-layer `ModeloWorkspace` or producer
  contract references, and no legacy global capture lock, authority LRU,
  detached failure cache, alias, fallback, shim or non-facade re-export bridge.
- The tree-wide import-hygiene checkpoint passed 51 tests and failed 4 on
  concurrent TUI test-only private imports in `test_relocation_parity.py` and a
  component-test import in `test_component_boundary.py`. None names, imports or
  traverses the S159 registry surface; the scoped S159 boundary and exact
  census remain green. These external failures are not absorbed into the S159
  verdict.

### Remediation re-review disposition

CONDITIONAL PASS, NOT CLOSURE. The production implementation resolves every
historical HIGH and MEDIUM finding and no current production defect was found.
S159 must remain unchecked until the LOW unrelated-root overlap proof is a
committed regression test and a focused final verification confirms that gate
bites while all S159 checks remain green.
