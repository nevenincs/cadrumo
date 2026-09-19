---
tags:
  - '#adr'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:de8ecf40484e994f04a8d591e1c24c2db378efe670098b3c6370270326e482fa'
related:
  - "[[2026-08-23-cli-runtime-resource-architecture-convergence-research]]"
  - "[[2026-08-22-secure-storage-performance-hardening-research]]"
  - "[[2026-08-22-secure-storage-performance-hardening-reference]]"
  - '[[2026-08-22-secure-storage-performance-hardening-adr]]'
---

# `secure-storage-performance-hardening` adr: `production-authored CommandSpec authority` | (**status:** `accepted`)

## Problem Statement

The command-loading implementation has diverged from the accepted architecture:
shipped runtime behavior now depends on ignored JSON produced by development
tools, and its two projections form a generation-order dependency across
production and development lanes. The S11 and S14 designs are nonconforming to
the 2026-08-22 rejection of a cache or manifest as command authority. A
corrective decision must restore one production-owned source of executable CLI
structure while preserving demand loading and the secure-storage pure-read
campaign. `2026-08-23-cli-runtime-resource-architecture-convergence-research`

## Considerations

- Every source, build, shipping, and installed-runtime lane needs the same
  command authority without a generation prerequisite.
- Startup remains proportional only if command structure is import-light and
  handler and schema implementations stay deferred.
- A new specification beside decorators, policies, projections, or catalogues
  would increase rather than remove drift authority.
- Development benchmark evidence is useful and may be retained; it differs from
  a resource imported by production.
- The custody, profile-summary, pure-read, refusal, and public-facade decisions
  in the 2026-08-22 record remain stable parents.

## Considered options

- **Commit the generated JSON and strengthen parity gates:** rejected because it
  preserves duplicated structural authority, regeneration churn, and a
  production dependency on development compilation.
- **Generate resources in the build backend:** rejected because editable and
  direct-source execution diverge from packaged execution, the sdist excludes
  the generator, and packaging becomes responsible for authoring behavior.
- **Generate metadata at runtime:** rejected because materializing or shadowing
  the handler tree restores eager cost and the second authority.
- **Add production `CommandSpec` beside existing Typer declarations:** rejected
  because mirrored declarations require permanent parity machinery and cannot
  be the sole authority.
- **Replace every structural declaration with distributed, production-authored,
  import-light `CommandSpec`:** accepted because runtime and all projections can
  consume one tracked authority without loading handlers or generated caches.

## Constraints

`CommandSpec` is the sole executable CLI structural authority. No Typer
decorator, callback attribute, lazy registration table, generated projection,
operator-help row, MCP/HITL catalogue, or verb-path list may independently own a
fact represented by a spec.

Each root, group, and leaf spec owns its operator token and parent/child tree
edge; node kind and invocation behavior; argument and option declarations;
localized translation keys; execution capabilities, side effects, performance
class, write route, and risk flags; lazy public handler target; and lazy schema
target. Help text is resolved from owned translation keys rather than copied
into the spec. Explicitly unavailable implementations are typed states, not
missing registrations or synthetic callbacks.

The specifications live in tracked production Python, distributed beside the
subtree they describe and composed through import-light public boundaries. They
must not import handler, registry, custody, calculation, network, or other heavy
implementation graphs. A production assembler projects specs into Typer/Click
objects; Typer/Click objects cease to be structural declarations.

Production must not import or read a runtime cache, manifest, generated command
JSON, or development artifact. Development and build code may consume and
validate production specs, but production has no dependency on `dev`, build
hooks, generated evidence, or a prior materialization pass.

The cutover is atomic and fail-loud. No JSON reader, fallback, compatibility
shim, dual registration, mirror, transitional catalogue, or legacy path may
remain. The complete live surface must migrate in the same change; partial
subtree coexistence is prohibited.

## Implementation

The authority and projection flow becomes:

```text
tracked production CommandSpec graph
    +-- runtime assembler -> Typer/Click nodes -> deferred public handlers
    +-- schema/operator/MCP/help/suggestion consumers
    +-- dev validators, documentation, benchmarks, and release gates
    `-- cohort identity and installed-behavior verification
```

There is no reverse edge from production to development or build tooling, and
no serialized runtime resource between the spec graph and its consumers.

The complete graph is migrated in one hard cut. The new typed spec primitives
and distributed subtree declarations land with the assembler and every runtime
consumer. Existing structural decorators, callback-attached policy authority,
lazy path tables, registrar reflection, manually reconstructed dependency maps,
generated projections, generated JSON readers and generators, duplicated policy
and verb catalogues, and their cache-parity tests are deleted in that cut.

S11 and S14 execution and review evidence are reopened and corrected: their
latency observations may remain historical evidence, but neither Step may claim
architectural completion or packaged-runtime correctness. Replacement Steps
must prove the same required behavior through the production spec authority.

Clean checkout, editable source, direct wheel, direct sdist, sdist-to-wheel,
immutable Git-archive cohort, and installed-runtime lanes must all resolve the
same complete command identities and localized parameter metadata from tracked
production specs without regeneration. Wheel and sdist contents must include
the spec modules and exclude command cache resources and their generators.
Installed tests materialize every root, group, and leaf, verify public target
resolution, policy and schema identity, locale completeness, and selected-path
import budgets.

The canonical Python cohort builds once from a clean pinned archive. Downstream
smoke, Scoop, Homebrew, MCPB, marketplace, and publish lanes consume that sealed
cohort without rebuilding or regenerating command authority. Promotion binds
the tested cohort identity to installed behavior; missing, duplicate, or
mismatched specs are release-blocking.

Generated profiling distributions under the development benchmark tree may be
retained as reproducible campaign evidence. They never enter a package, runtime
lookup, command-authority digest, or source-of-truth comparison.

Rollback is repository-level reversal of the entire atomic cut before release,
followed by re-execution of the prior source and packaging gates. Runtime
fallback to JSON, coexistence with old declarations, and partial per-subtree
rollback are forbidden because each recreates multiple authorities.

## Rationale

Only replacement by production-authored specs satisfies all knockout criteria:
one structural authority, no development-to-production inversion, equivalent
source and package lanes, demand-loaded handlers, and universal enrollment of
the complete live surface. Deterministic JSON, build hooks, and parity tests can
stabilize a duplicate representation but cannot remove it.
`2026-08-23-cli-runtime-resource-architecture-convergence-research`

This pivots the registration mechanism while preserving the original objective:
command-scoped loading and pure, non-mutating secure-storage reads. The storage
inventory and custody constraints remain exactly as decided and grounded in
`2026-08-22-secure-storage-performance-hardening-research` and
`2026-08-22-secure-storage-performance-hardening-reference`.

## Consequences

Executable CLI structure has one tracked production home. Runtime help, schema
discovery, operator guidance, MCP/HITL policy, completion, suggestions, docs,
and performance enrollment can traverse it without materializing sibling
handlers or reconciling caches.

Adding or changing a command requires one spec declaration plus its deferred
implementation, not synchronized edits to decorators, generated JSON, risk
tables, and path catalogues. Clean and packaged execution become equivalent,
and the release pipeline no longer relies on ignored worktree state.

The migration has a broad atomic blast radius: hundreds of nodes and every
metadata consumer must move together, and review cannot accept a transitional
green state. Import-light specs also require discipline so translation, schema,
or handler imports do not creep into declaration modules. Universal exact-set,
fresh-process import, installed-artifact, and per-path performance gates carry
that obligation.

The 2026-08-22 ADR remains the accepted parent and governing record for
command-scoped loading, pure-read inventory, custody, public-facade, refusal,
side-effect, and calibrated performance constraints. This child decision
operationalizes its already-stated rejection of manifests and replaces only the
nonconforming S11/S14 implementation mechanism; it does not displace or restate
the parent's secure-storage authority.
