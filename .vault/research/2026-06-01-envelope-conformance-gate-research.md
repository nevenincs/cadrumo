---
tags:
  - '#research'
  - '#envelope-conformance-gate'
date: '2026-06-01'
modified: '2026-06-01'
related:
  - "[[2026-05-31-coverage-canonicalisation-audit]]"
---

# `envelope-conformance-gate` research: allowlist vs symmetric-diff for cli json schema coverage

The CLI emits JSON envelopes from every leaf command tagged as
machine-readable. Each leaf's envelope shape is registered as an
`OutputSchema` in `SCHEMA_REGISTRY`. The question: how should the
gate enforce that every JSON-emitting leaf is registered, and that
every registered schema corresponds to a live leaf?

## Findings

### Two enforcement shapes were considered

The allowlist shape carries a list of "known divergences" and
accepts new ones as they appear. This is what
`COVERAGE_GAPS` did for the parallel test-coverage surface, and what
the coverage-canonicalisation audit retired after the list grew to
66 entries. Every divergence absorbed into the list silently
legalised the drift the gate was meant to catch.

The symmetric-diff shape computes both directions of the set
difference between the live CLI leaf-path set and the registered
schema-key set, and asserts both differences are empty. Failures
report the two directions separately so the diagnostic is
actionable. No allowlist parameter exists.

### Prior-art evidence

The `COVERAGE_GAPS` retirement (commit `f36a82118`) demonstrated
that allowlists in this codebase trend monotonically toward "rubber
stamp" once the rate of new entries exceeds the rate of cleanup
campaigns. The symmetric-diff retrofit landed in
`test_every_module_has_test_coverage.py` with a 9-entry rationale-
carrying `_EXEMPTIONS` set, each entry justified on durable
structural grounds (browser-only dependency, `_lazy()` Typer
subcommand, `python -m` entry point). The same shape applied to the
JSON-schema gate is the load-bearing pattern.

### Implementation surface

`src/aeat/entrypoints/cli/test_json_schema_conformance.py` walks
the live Typer `app` tree (via the application factory, so
`_lazy()`-mounted subcommands are included), collects the leaf
command paths as a `set[tuple[str, ...]]`, and asserts equality
against `set(SCHEMA_REGISTRY.keys())`. There is no escape hatch;
adding a new JSON-emitting leaf requires registering its schema in
the same commit.

## Decision

Carried in the related ADR
`2026-06-01-envelope-conformance-gate-adr`. The gate is unconditional
symmetric-diff; no allowlist parameter; the single-step ergonomic
cost is the property that keeps the registry honest.
