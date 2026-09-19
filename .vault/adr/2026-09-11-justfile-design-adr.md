---
tags:
  - "#adr"
  - "#justfile-design"
date: '2026-09-11'
related:
  - "[[2026-09-11-justfile-design-research]]"
supersedes:
  - '2026-06-04-just-tooling-bootstrap-adr'
  - '2026-06-09-justfile-redesign-adr'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:149dbe98177c645337131c8436025aec476878b2ec70717bc224ad701bede6cf'
---
# `justfile-design` adr: `Operator-intent command and tooling boundaries` | (**status:** `accepted`)

## Problem Statement

The root command surface conflates operator intent, subject, execution posture, implementation location, and policy composition. Recipe names therefore do not reliably reveal whether an operation observes, verifies, mutates, publishes, provisions, or depends on optional capabilities. The development tooling also permits multiple implementations to assert the same primitive fact.

A replacement taxonomy is required. This decision supersedes the public-command taxonomy of `2026-06-04-just-tooling-bootstrap-adr` and `2026-06-09-justfile-redesign-adr`, including their quality vocabulary and RAG surface mandates.

## Considerations

- Developers need recipe names that communicate intent, subject, and authority without inspecting implementations; see `2026-09-11-justfile-design-research`.
- Portable aggregates must preserve deterministic verdict boundaries and exclude capability-dependent operations.
- Registry operators need distinct answers for validity, generated currentness, publication state, and product-runtime loadability.
- Documentation benefits from a subject namespace spanning explicit execution postures.
- Public names must not expose the internal `dev/` package layout.
- One semantic implementation must own each primitive fact so aggregates compose verdicts rather than reimplement them.
- CI determinism and immutable registry authority remain compatible constraints rather than decisions replaced here.

## Considered options

- Retain the existing surface and rename isolated recipes: rejected because local renames cannot resolve nested aggregation, duplicate ownership, or mixed authority.
- Organize primarily by tool or implementation directory: rejected because tools and `dev/` paths do not express operator intent or verdict semantics.
- Organize exclusively by execution posture: rejected because posture alone obscures the subject of checks, tests, builds, and publications.
- Adopt operator-intent verbs with subject aggregates and explicit authority: accepted because it makes recipes and compositions predictable while preserving justified domain discoverability.

## Constraints

- Blocking `check-*` aggregates may contain only deterministic, read-only verdicts appropriate to their declared environment. A `gate-*` policy aggregate may additionally compose explicitly selected tests and release builds, but never mutations, destructive operations, optional capabilities it does not name, or temporary fixtures.
- Capability-dependent checks and tests remain explicitly qualified and outside portable defaults.
- Pre-commit execution remains verify-only.
- Registry runtime authority remains immutable and artifact-backed; validation, currentness, publication, and runtime loading cannot collapse into repair or compilation.
- The exact product `bundled_authority()` path currently lacks a development-owned loadability verdict and must gain one.
- Documentation retains its `docs-*` exception, but each recipe still discloses posture.
- Removing the justfile RAG surface does not decide whether underlying RAG implementation packages remain.

## Implementation

The root justfile becomes a thin operator interface. Public recipes use stable action contracts and subject names; implementation-location prefixes such as `dev-*`, ambiguous universal `*-all` aggregates, and generic mixed-authority argument forwarders are retired.

Blocking verification uses subject aggregates for code, registry, and repository/control-plane correctness. Tests are grouped by product, registry, tooling, packaging, and explicit capability populations. Builds distinguish release artifacts, temporary test fixtures, and infrastructure images.

`fix-*` is limited to mechanical source repair. Committed-derived-state generation uses explicit generation recipes. Fetching, publication, deployment, migration, and other authority-bearing mutations retain truthful domain verbs.

`audit-*` exposes advisory investigation. `report-*` renders findings or status with an explicit exit contract. Hard verdicts use `check-*`; mandatory security verdicts do not remain disguised as audits.

Setup performs minimal repository convergence. Optional browser, workstation, and other capability provisioning stays separately named. Doctor recipes are read-only and capability-specific.

Documentation remains under `docs-*`, with names distinguishing checking, generation, building, serving, reporting, maintenance, infrastructure provisioning, and publication.

The registry surface explicitly answers whether the registry is valid, whether generated targets and authority artifacts are current, which authority or export target is being published, and whether the shipped artifact loads through the exact product `bundled_authority()` path. Publication commands name their product and authority; no generic update command combines observation with mutation.

Release commands distinguish readiness checks, previews, publication, and rollback planning. Cross-subject policy composition uses `gate-*` rather than a generic `ci` entrypoint.

Release publication remains owned by external automation and has no justfile recipe. Public publication mutations are limited to explicitly named documentation and registry products.

All RAG recipes and their connected doctor probe, semantic check, resident-service test, and resident terminology sweep are removed from the public justfile surface without replacement.

Within `dev/`, each primitive fact has one semantic owner. Alternate implementations are consolidated, delegated to that owner, or retired; public aggregates may compose but do not duplicate the verdict.

### Required public surface

The setup surface is `setup`, `setup-python`, `setup-repository-tools`, `setup-env`, optional `setup-workstation-tools`, optional `setup-browser`, and read-only `setup-check`. Diagnosis is `doctor-product`, `doctor-dev`, `doctor-python`, and `doctor-browser`.

Blocking subjects are `check-code`, `check-registry`, and `check-repository`, with `check-hooks` retained only as non-aggregated hook replay and dependency vulnerabilities exposed as an explicit blocking security check. Registry leaves distinguish validity, oracle bindings, per-target currentness, authority currency, and exact artifact-backed runtime loadability.

Canonical test subjects are `test-product`, `test-registry`, `test-tooling`, packaging preflight/artifact/campaign surfaces, and individually named capability tests. The pytest harness is tooling-owned but precedes the canonical product aggregate. Focused selectors and coverage profiles are not exhaustive populations.

Mechanical repair is `fix-code` plus focused style, import, and format leaves. Advisory scanners compose under `audit-code`; finding and governance products use `report-*`. Release artifacts, temporary packaging cohorts, and infrastructure images use separate build surfaces. Domain mutations use locale, registry, terminology, TUI, and database names rather than `dev-*`.

Documentation is the exception to global action-first naming. Its public namespace contains `docs-check`, `docs-sequences-check`, `docs-build`, `docs-page`, `docs-lang`, `docs-langs`, `docs-site-preview`, `docs-generate-*`, `docs-serve`, `docs-terminology-*`, `docs-stack-provision`, and `docs-publish`, with each posture documented and independently authorized.

Policy entrypoints are `gate-local` and, only when proven against hosted policy,
`gate-per-push`. `gate-local` explicitly requires network access for the blocking
dependency-vulnerability verdict; the subject `check-*` aggregates remain portable and
network-free. There is no public `check-all`, `test-all`, `build-all`, `audit-all`,
unqualified `ci`, generic `registry-update`, mixed-authority `dev-*` pass-through,
release publication/rollback mutation recipe, or RAG surface.

## Rationale

The accepted design communicates both operator intent and exercised authority. It resolves the registry lifecycle into independently observable facts, preserves documentation discoverability, and prevents optional services or platform capabilities from contaminating portable gates.

Subject aggregates align with deterministic CI composition while the single-owner rule removes drift between parallel implementations. Explicit publication and release verbs make mutations reviewable and prevent status inspection from silently changing repository or runtime state.

## Consequences

Developers gain predictable command vocabulary, narrower aggregates, truthful setup and release operations, and a registry status model distinguishing validity, currentness, publication, and runtime loadability.

The redesign requires coordinated changes to the justfile, `dev/` ownership boundaries, workflows, hooks, and contributor documentation. Existing aliases and broad aggregates are removed rather than preserved as compatibility layers.

A registry runtime-load primitive must be implemented. Duplicate environment synchronization, registry rendering, write-path analysis, and mixed quality/audit ownership must be reconciled before replacement recipes can claim authority.

The two earlier justfile ADRs become superseded because this decision replaces their public taxonomy and reverses their RAG and quality-surface mandates. CI determinism and immutable registry authority continue to constrain implementation.
