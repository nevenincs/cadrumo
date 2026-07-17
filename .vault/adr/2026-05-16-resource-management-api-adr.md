---
tags:
  - '#adr'
  - '#resource-management-api'
date: '2026-05-16'
modified: '2026-07-17'
related:
  - '[[2026-05-16-resource-management-api-research]]'
  - '[[2026-05-16-resource-management-api-audit]]'
  - '[[2026-05-15-corpus-registry-packaging-adr]]'
  - '[[2026-05-19-spanish-stem-terminology-authority-adr]]'
---

# Resource management API | (**status:** `accepted`)

## Decision

`src/cadrumo/core/resources/` is the only API for locating bundled project
resources. It resolves package-owned paths through `importlib.resources`,
provides explicit context-managed materialisation when a filesystem path is
required, and supplies typed repository factories for registry and corpus
consumers.

Resource repositories own validation and bounded caching for their resource
kind. Domain and application code request a repository or packaged resource
through this API; they do not calculate repository roots, walk source trees, or
read package-layout internals.

## Invariants

- Wheel and source-tree execution resolve identical bundled bytes under the
  `cadrumo/_data` package prefix.
- Resource keys and cross-resource references are typed and validated before
  content reaches calculation or filing services.
- The calculation registry remains its own domain authority; the core resource
  API locates bytes but does not duplicate registry semantics.
- Cache identity includes the effective resource revision or content identity,
  and invalidation cannot return a prior revision under a new key.
- Tests use the public resource API against real packaged files.

## Consequences

The former single-file locator, scattered module-relative roots, per-domain
path heuristics, duplicate caches, and import-compatibility wrappers are
deleted. Operator configuration does not expose alternate authoritative corpus
roots; externally supplied evidence enters through explicit reviewed import
boundaries rather than replacing bundled legal resources.
