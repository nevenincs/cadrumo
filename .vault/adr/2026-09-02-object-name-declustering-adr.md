---
tags:
  - '#adr'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6d4235532385e14b64846fe96e4625f47b0629724d257b93134830e2bed57919'
related:
  - "[[2026-09-02-object-name-declustering-research]]"
  - "[[2026-09-02-object-name-declustering-reference]]"
---
# `object-name-declustering` adr: `manifest-governed graph batches with receipt-bound rehearsal` | (**status:** `accepted`)

## Problem Statement

The object-name audit identifies lexical collisions and plural names, but its findings are not safe rename units. Renames can cross directories, layers, dynamic targets, generated artifacts, tests, and shared consumers. The repository needs a fail-closed contract that turns findings into reviewable operations, rehearses the exact current working bytes outside the live tree, and permits live mutation only while reviewed scope and rehearsal evidence remain current. Grounding is in `2026-09-02-object-name-declustering-research` and `2026-09-02-object-name-declustering-reference`.

## Considerations

- Paths provide ownership and test-selection metadata, not atomicity boundaries.
- Finding identity must survive unrelated movement, while execution must refuse concurrent byte changes; these require separate hashes.
- Existing name, import, semantic, and clone analyzers provide complementary evidence, but none owns the complete workflow.
- `2026-07-01-import-centralization-adr` requires one defining module, direct imports, exact dynamic targets, atomic relocation, deletion of old paths, and no aliases, facades, shims, or fallbacks.
- Lexical collision does not establish substitutability, and semantic similarity does not authorize consolidation.

## Considered options

- **Directory batches.** Rejected because imports, shared consumers, generators, and dynamic targets cross directory boundaries.
- **Similarity- or digest-derived batches.** Retained as advisory evidence but rejected as authority because similarity cannot choose canonical ownership.
- **Rope as the execution authority.** Rejected because its published compatibility does not cover Python 3.13; it remains probe-only.
- **Unreviewed LibCST codemods.** Rejected because syntax-aware transforms do not discover arbitrary strings, generated ownership, architecture constraints, or intended scope.
- **Chosen: repository-owned manifest planning, bipartite dependency batches, controlled transforms, and receipt-bound rehearsal.**

## Constraints

- The accepted import-centralization decision remains binding and stable.
- Planning and inventory are read-only.
- Every mutation batch must first run against a verified disposable copy of the current dirty tree, including tracked modifications and untracked inputs but excluding repository metadata and caches.
- The planner refuses ambiguous ownership, duplicate or claimed targets, stale bytes, unresolved dynamic references, generated files without an owning generator, paths outside the allowlist, and new enforced findings.
- Generated outputs change only through their owning generators.
- AST fingerprints, semantic findings, clone evidence, and path proximity are annotations or gates, never rename or merge authority.
- Lexical batches cannot execute `merge-authority`. Consolidation requires a separate approved semantic-consolidation decision and plan.
- Module moves and symbol renames remain distinct operation kinds.

## Implementation

A repository-owned development tool will implement `inventory` -> `plan` -> `rehearse` -> `apply` -> `verify`. It will extend or consume the canonical object-name inventory and compose the existing import graph, import-hygiene surfaces, semantic candidates, clone evidence, and generator authorities.

The reviewed manifest is the sole authority between discovery and mutation. Each operation records its schema and operation ID, stable finding ID, operation kind, old and proposed qualified locators and paths, disposition, owner, rationale, byte preconditions, expected reference classes, exact moves, changed-path allowlist, generator commands, focused gates, and lifecycle state. Its dispositions are `lexical-singular`, `rename-distinct`, `keep-distinct`, and non-executable-in-this-lane `merge-authority`. Bidirectional completeness is mandatory: every selected finding has one disposition, and stale or unmatched rows fail.

The planner constructs a bipartite graph of rename-operation nodes and affected file or generated-surface nodes. Definitions, collision membership, static and type-only imports, exact dynamic targets, exports, shared consumers, and generated artifacts create hard edges. Connected components are indivisible review units. Directory, layer, owner, fan-in, semantic similarity, and clone evidence annotate risk and ordering without establishing authority.

Two SHA-256 families are mandatory. A stable finding ID hashes a canonical schema-versioned tuple of finding kind, object kind, old name, and sorted qualified sites. Execution preconditions hash every affected file's bytes and the canonical baseline inventory. Neither digest establishes semantic equivalence.

`rehearse` creates and verifies a system-temporary copy of the current working bytes, applies exactly one reviewed component, compares actual changed paths with the allowlist, and runs applicable residue, parsing/import, architecture, generator, focused-test, type, lint, object-name delta, semantic-duplication, and clone non-regression gates. It emits a receipt binding the manifest digest, baseline and file digests, tool versions, actual changed-path digest, finding delta, and every gate outcome.

`apply` accepts only a successful matching receipt, rechecks all byte and inventory preconditions, and replays the identical operation sequence in the live worktree. Any drift causes refusal. The same verification then runs against the live result.

LibCST is the controlled formatting-preserving engine for repository-owned symbol transforms. Filesystem moves and non-Python surfaces remain explicit typed operations. Rope may run only as a no-authority probe in disposable rehearsal until detector-teeth fixtures prove Python 3.13 compatibility and exact changed-path containment; it cannot authorize or perform live mutation.

## Rationale

The manifest, not directory proximity or a third-party refactorer's reach, must own intent. The bipartite graph exposes shared surfaces that make operations inseparable. Dual hashes separately preserve stable finding identity and enforce fresh source bytes. Receipt-bound rehearsal makes the temporary-copy safety net a mechanical replay precondition instead of a convention. Repository ownership also lets existing analyzers and accepted architecture boundaries refuse unsafe operations before mutation.

## Consequences

- Rename batches become deterministic, reviewable, stale-input-safe, and bounded by exact changed-path contracts.
- Cross-directory components may be larger than path batches, but their coupling is visible before mutation.
- Highly connected components can be deferred instead of partially renamed.
- The planner and receipt schema introduce repository-owned tooling and detector-teeth maintenance.
- LibCST transforms require operation-specific fixtures; Rope remains unavailable as live authority unless its compatibility gap is closed and proven locally.
- Findings may resolve to `keep-distinct`, preserving adjudication without pretending a rename or merge occurred.
- Semantic consolidation remains separately governed.
- Old paths disappear atomically; consumers move in the same component without a compatibility window.
